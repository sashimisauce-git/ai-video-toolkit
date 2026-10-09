#!/usr/bin/env python3
"""
face-swap/swap.py — Lock a consistent face onto AI-generated video.

Generative video models drift faces toward generic priors. This script
post-processes: detect faces per frame with InsightFace buffalo_l, swap a
locked source face on with inswapper_128, preserve original audio.

Identity comes from the source photo; motion and expression come from the
target video — so the swapped face talks, blinks, and smiles with the
video's own acting.

Usage:
    python swap.py --source /path/to/face-ref.png --target /path/to/in.mp4 --output /path/to/out.mp4

Models expected in ./models/ (relative to this script):
    models/buffalo_l/        (unzipped buffalo_l.zip: detection + recognition)
    models/inswapper_128.onnx
"""
import argparse
import os
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
    app.prepare(ctx_id=-1, det_size=(640, 640))  # ctx_id=-1 -> CPU; use 0 for GPU

    swapper_path = os.path.join(MODELS_DIR, "inswapper_128.onnx")
    if not os.path.exists(swapper_path):
        sys.exit(f"[faceswap] missing model: {swapper_path}\n"
                 f"Download it — see README.md for links.")
    print("[faceswap] loading inswapper_128...", flush=True)
    swapper = get_model(swapper_path, download=False, download_zip=False)
    return app, swapper


def get_source_face(app, source_path):
    img = cv2.imread(source_path)
    if img is None:
        sys.exit(f"[faceswap] cannot read source image: {source_path}")
    faces = app.get(img)
    if not faces:
        sys.exit("[faceswap] no face detected in source image "
                 "(use a clear, front-facing photo)")
    # largest face = the subject
    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    print(f"[faceswap] source face locked (bbox {face.bbox.astype(int).tolist()})", flush=True)
    return face


def swap_video(app, swapper, source_face, target_path, silent_out_path):
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
            # largest detected face = the subject
            target = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            try:
                frame = swapper.get(frame, target, source_face, paste_back=True)
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
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", target_path],
        capture_output=True, text=True,
    )
    if not probe.stdout.strip():
        print("[faceswap] no audio stream in target; copying video only", flush=True)
        os.replace(silent_video, output_path)
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
    ap = argparse.ArgumentParser(description="Swap a locked face onto video (InsightFace)")
    ap.add_argument("--source", required=True,
                    help="source face image (clear, front-facing photo)")
    ap.add_argument("--target", required=True, help="target video")
    ap.add_argument("--output", required=True, help="output video path")
    args = ap.parse_args()

    app, swapper = load_models()
    source_face = get_source_face(app, args.source)

    with tempfile.TemporaryDirectory() as tmp:
        silent = os.path.join(tmp, "swapped_silent.mp4")
        swap_video(app, swapper, source_face, args.target, silent)
        mux_audio(silent, args.target, args.output)
    print(f"[faceswap] SUCCESS: {args.output}", flush=True)


if __name__ == "__main__":
    main()
