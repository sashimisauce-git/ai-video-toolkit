#!/usr/bin/env python3
"""
face-swap/swap.py — Lock a consistent face onto AI-generated video.

Generative video models drift faces toward generic priors. This script
post-processes: detect faces per frame with InsightFace buffalo_l, swap a
locked source face on with inswapper_128, preserve original audio.

Usage:
    python swap.py --source /path/to/face-ref.png --target /path/to/in.mp4 --output /path/to/out.mp4

Models expected in ./models/ (relative to this script):
    models/buffalo_l/        (unzipped buffalo_l.zip: detection + recognition)
    models/inswapper_128.onnx
    models/dfl_xseg.onnx      (optional: XSeg occlusion mask for edge-free blends;
                               falls back to landmark-hull mask when absent)

Blend: inswapper generates the swapped 128x128 crop; it is warped back with the
INVERSE of the alignment matrix (M maps frame->crop), masked by the XSeg face
contour (eroded + feathered), color-matched to scene lighting (Reinhard LAB),
then blended. The mask boundary follows the true jawline/hairline, which is
what kills the visible swap edge.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

import cv2
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(SCRIPT_DIR, "models")


def load_models():
    import insightface
    from insightface.app import FaceAnalysis
    from insightface.model_zoo import get_model

    print("[faceswap] loading buffalo_l (detection)...", flush=True)
    app = FaceAnalysis(name="buffalo_l", root=MODELS_DIR)
    app.prepare(ctx_id=0, det_size=(640, 640))  # ctx_id=0 -> CPU

    swapper_path = os.path.join(MODELS_DIR, "inswapper_128.onnx")
    if not os.path.exists(swapper_path):
        sys.exit(f"[faceswap] missing model: {swapper_path}")
    print("[faceswap] loading inswapper_128...", flush=True)
    swapper = get_model(swapper_path, download=False, download_zip=False)

    # XSeg occlusion model: true face-contour mask (kills the visible swap edge).
    # Optional — falls back to the landmark-hull mask when absent.
    xseg = None
    xseg_path = os.path.join(MODELS_DIR, "dfl_xseg.onnx")
    if os.path.exists(xseg_path):
        try:
            import onnxruntime as ort
            xseg = ort.InferenceSession(xseg_path, providers=["CPUExecutionProvider"])
            print("[faceswap] xseg occlusion mask loaded", flush=True)
        except Exception as e:
            print(f"[faceswap] xseg load failed ({e}); using hull mask", flush=True)
    else:
        print("[faceswap] no dfl_xseg.onnx; using hull mask", flush=True)
    return app, swapper, xseg


def get_source_face(app, source_path):
    img = cv2.imread(source_path)
    if img is None:
        sys.exit(f"[faceswap] cannot read source image: {source_path}")
    faces = app.get(img)
    if not faces:
        sys.exit("[faceswap] no face detected in source image")
    # largest face = the subject
    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    print(f"[faceswap] source face locked (bbox {face.bbox.astype(int).tolist()})", flush=True)
    return face


def create_face_mask(shape, face, feather=21, expand=1.15):
    """Feathered mask from face landmarks (convex hull), blurred for soft edges."""
    h, w = shape[:2]
    mask = np.zeros((h, w), dtype=np.float32)
    # use 5-point landmarks if available, else fall back to bbox ellipse
    try:
        pts = face["kps"] if isinstance(face, dict) else face.kps
        # expand hull outward from centroid to cover jawline/forehead
        pts = np.array(pts, dtype=np.float32)
        c = pts.mean(axis=0)
        pts = c + (pts - c) * expand
        hull = cv2.convexHull(pts.astype(np.int32))
        cv2.fillConvexPoly(mask, hull, 1.0)
    except Exception:
        x1, y1, x2, y2 = face.bbox.astype(int)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        axes = (int((x2 - x1) * expand / 2), int((y2 - y1) * expand / 2))
        cv2.ellipse(mask, (cx, cy), axes, 0, 0, 360, 1.0, -1)
    # erode slightly so the mask sits INSIDE the swapped region, then feather
    k = max(3, feather // 3)
    mask = cv2.erode(mask, np.ones((k, k), np.uint8))
    mask = cv2.GaussianBlur(mask, (feather | 1, feather | 1), 0)
    return mask[..., None]


def color_match(src, dst, mask):
    """Reinhard color transfer (LAB): match swapped face to target lighting."""
    m = mask[..., 0] > 0.5
    if m.sum() < 100:
        return src
    src_lab = cv2.cvtColor(src, cv2.COLOR_BGR2LAB).astype(np.float32)
    dst_lab = cv2.cvtColor(dst, cv2.COLOR_BGR2LAB).astype(np.float32)
    out = src_lab.copy()
    for ch in range(3):
        s = src_lab[..., ch][m]
        d = dst_lab[..., ch][m]
        s_mean, s_std = s.mean(), s.std() + 1e-6
        d_mean, d_std = d.mean(), d.std() + 1e-6
        out[..., ch][m] = np.clip((s - s_mean) * (d_std / s_std) + d_mean, 0, 255)
    return cv2.cvtColor(out.astype(np.uint8), cv2.COLOR_LAB2BGR)


def xseg_face_mask(bgr_fake_128, IM, frame_shape, xseg):
    """True face-contour mask via XSeg occlusion model.

    Runs on the swapped aligned crop (128x128 -> 256 for the model), then the
    mask is resized back to the crop's own 128x128 coordinate space and warped
    to full-frame with IM (the aligned->frame inverse transform). The boundary
    follows the real jawline/hairline instead of cutting mid-cheek, which is
    what made the old hull mask's edge visible.
    """
    crop256 = cv2.resize(bgr_fake_128, (256, 256), interpolation=cv2.INTER_LINEAR)
    inp = np.expand_dims(crop256.astype(np.float32) / 255.0, 0)
    out = xseg.run(None, {"input": inp})[0][0, :, :, 0]
    m = (out > 0.5).astype(np.uint8) * 255
    m = cv2.resize(m, (128, 128), interpolation=cv2.INTER_NEAREST)
    m = cv2.erode(m, np.ones((3, 3), np.uint8))      # stay inside generated face
    m = cv2.GaussianBlur(m, (9, 9), 0).astype(np.float32) / 255.0
    h, w = frame_shape[:2]
    full = cv2.warpAffine(m, IM, (w, h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return full[..., None]


def swap_frame_custom(app, swapper, xseg, frame, target, source_face):
    """Swap with occlusion-mask blend instead of InsightFace's hard paste-back."""
    # get swapped face crop (128x128) + forward warp matrix, no paste
    bgr_fake, M = swapper.get(frame, target, source_face, paste_back=False)
    # M maps frame -> aligned crop; the back-warp needs its inverse
    IM = cv2.invertAffineTransform(M)
    h, w = frame.shape[:2]
    # warp swapped face back to full-frame coordinates
    swapped_full = cv2.warpAffine(
        bgr_fake, IM, (w, h),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
    )
    # occlusion mask (true face contour) with hull-mask fallback
    if xseg is not None:
        try:
            mask = xseg_face_mask(bgr_fake, IM, frame.shape, xseg)
        except Exception as e:
            print(f"[faceswap] xseg mask failed ({e}); hull fallback", flush=True)
            mask = create_face_mask(frame.shape, target)
    else:
        mask = create_face_mask(frame.shape, target)
    # color-match to scene lighting, then feathered blend
    swapped_full = color_match(swapped_full, frame, mask)
    blended = (swapped_full.astype(np.float32) * mask
               + frame.astype(np.float32) * (1.0 - mask))
    return np.clip(blended, 0, 255).astype(np.uint8)


def swap_video(app, swapper, xseg, source_face, target_path, silent_out_path):
    cap = cv2.VideoCapture(target_path)
    if not cap.isOpened():
        sys.exit(f"[faceswap] cannot open video: {target_path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(silent_out_path, fourcc, fps, (w, h))

    swapped, skipped = 0, 0
    i = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        i += 1
        try:
            faces = app.get(frame)
        except Exception as e:
            print(f"[faceswap] frame {i}: detection error ({e}), keeping original", flush=True)
            faces = []
        if faces:
            target = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            try:
                frame = swap_frame_custom(app, swapper, xseg, frame, target, source_face)
                swapped += 1
            except Exception as e:
                print(f"[faceswap] frame {i}: swap error ({e}), keeping original", flush=True)
                skipped += 1
        else:
            skipped += 1
        writer.write(frame)
        if i % 25 == 0 or i == total:
            print(f"[faceswap] frame {i}/{total} (swapped {swapped}, kept {skipped})", flush=True)
    cap.release()
    writer.release()
    print(f"[faceswap] done: {swapped} swapped, {skipped} kept original", flush=True)
    return fps


def mux_audio(silent_video, target_path, output_path):
    """Copy original audio onto the swapped (silent) video."""
    # check target has audio
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", target_path],
        capture_output=True, text=True,
    )
    if not probe.stdout.strip():
        print("[faceswap] no audio stream in target; copying video only", flush=True)
        shutil.move(silent_video, output_path)
        return
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", silent_video,
        "-i", target_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-shortest",
        output_path,
    ]
    subprocess.run(cmd, check=True)
    print(f"[faceswap] audio muxed -> {output_path}", flush=True)


def main():
    ap = argparse.ArgumentParser(description="Swap locked face onto video (InsightFace)")
    ap.add_argument("--source", required=True, help="source face image (clear, front-facing photo)")
    ap.add_argument("--target", required=True, help="target video")
    ap.add_argument("--output", required=True, help="output video path")
    args = ap.parse_args()

    app, swapper, xseg = load_models()
    source_face = get_source_face(app, args.source)

    with tempfile.TemporaryDirectory() as tmp:
        silent = os.path.join(tmp, "swapped_silent.mp4")
        swap_video(app, swapper, xseg, source_face, args.target, silent)
        mux_audio(silent, args.target, args.output)
    print(f"[faceswap] SUCCESS: {args.output}", flush=True)


if __name__ == "__main__":
    main()
