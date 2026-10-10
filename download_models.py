#!/usr/bin/env python3
"""
download_models.py — fetch all AI models once, with progress bars.

Usage:
    python download_models.py              # download anything missing
    python download_models.py --check-only # exit 0 if all present, 1 if missing

Models (~700MB total) land in face-swap/models/ and are never re-downloaded.
faster-whisper's transcription model downloads itself on first use (~500MB).
"""
import argparse
import os
import sys
import urllib.request
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(SCRIPT_DIR, "face-swap", "models")

FILES = [
    {
        "name": "buffalo_l.zip",
        "url": "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip",
        "dest": os.path.join(MODELS_DIR, "buffalo_l.zip"),
        "unzip_to": os.path.join(MODELS_DIR, "buffalo_l"),
        "size_mb": 325,
    },
    {
        "name": "inswapper_128.onnx",
        "url": "https://github.com/deepinsight/insightface/releases/download/v0.7/inswapper_128.onnx",
        "dest": os.path.join(MODELS_DIR, "inswapper_128.onnx"),
        "size_mb": 554,
    },
    # Optional: XSeg occlusion mask for edge-free blends (true face contour).
    # Falls back to landmark-hull mask when absent — safe to skip.
    {
        "name": "dfl_xseg.onnx (optional)",
        "url": "https://github.com/yakhyo/face-segmentation/releases/download/weights/xseg.onnx",
        "dest": os.path.join(MODELS_DIR, "dfl_xseg.onnx"),
        "optional": True,
        "size_mb": 70,
    },
]


def _progress(name, size_mb):
    downloaded = [0]

    def hook(blocks, block_size, total):
        downloaded[0] = blocks * block_size
        pct = min(100, downloaded[0] / total * 100) if total > 0 else 0
        bar = "#" * int(pct / 2) + "-" * (50 - int(pct / 2))
        sys.stdout.write(f"\r  {name}: [{bar}] {pct:5.1f}%")
        sys.stdout.flush()

    return hook


def download_one(spec):
    dest = spec["dest"]
    if os.path.exists(dest) or (
        spec.get("unzip_to") and os.path.isdir(spec["unzip_to"])
    ):
        print(f"  ✓ {spec['name']} (already present)")
        return True
    if spec.get("optional"):
        print(f"  · {spec['name']} — optional, attempting...")
    else:
        print(f"  ↓ {spec['name']} (~{spec['size_mb']}MB)...")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        urllib.request.urlretrieve(
            spec["url"], dest, reporthook=_progress(spec["name"], spec["size_mb"])
        )
        sys.stdout.write("\n")
    except Exception as e:
        sys.stdout.write("\n")
        print(f"  ✗ failed: {e}")
        if spec.get("optional"):
            print("    (optional — continuing without it)")
            return True
        return False
    unzip_to = spec.get("unzip_to")
    if unzip_to:
        print(f"    unzipping to {unzip_to}...")
        with zipfile.ZipFile(dest, "r") as z:
            z.extractall(unzip_to)
        os.remove(dest)
    print(f"  ✓ {spec['name']}")
    return True


def missing():
    out = []
    for spec in FILES:
        if spec.get("optional"):
            continue
        dest = spec["dest"]
        present = os.path.exists(dest) or (
            spec.get("unzip_to") and os.path.isdir(spec["unzip_to"])
        )
        if not present:
            out.append(spec["name"])
    return out


def main(check_only=False):
    if check_only:
        return missing()
    print("[models] checking face-swap/models/ ...")
    ok = True
    for spec in FILES:
        if not download_one(spec):
            ok = False
    if not ok:
        sys.exit("\n[models] some required models failed to download. "
                 "Check your connection and retry.")
    print("\n[models] all models ready ✓")
    print("[models] note: faster-whisper downloads its transcription model "
          "on first caption use (~500MB, automatic).")
    return []


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()
    if args.check_only:
        sys.exit(0 if not missing() else 1)
    main()
