# Face-swap — lock a consistent face onto AI-generated video

## Why

Generative video models drift faces toward generic priors — every clip looks
like a different person. This pipeline fixes it: generate any scene for
motion and background, then swap a locked reference face onto every frame.

Identity comes from your source photo; motion and expression come from the
target video. The swapped face talks, blinks, and smiles with the video's
own acting. Only the face is replaced — hair, clothing, and background are
untouched.

## Requirements

- Python 3.8+
- `pip install insightface onnxruntime opencv-python numpy`
- `ffmpeg` + `ffprobe` on your PATH

## Models (download once into `./models/`)

The models are ~600MB total and are **not** included in this repo. Download:

| File | Where it goes | Download |
|---|---|---|
| `buffalo_l.zip` | unzip to `models/buffalo_l/` | https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip |
| `inswapper_128.onnx` | `models/inswapper_128.onnx` | https://github.com/deepinsight/insightface/releases/download/v0.7/inswapper_128.onnx |

```bash
mkdir -p models && cd models
curl -L -o buffalo_l.zip https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip
unzip buffalo_l.zip -d buffalo_l
curl -L -o inswapper_128.onnx https://github.com/deepinsight/insightface/releases/download/v0.7/inswapper_128.onnx
```

## Usage

```bash
python swap.py \
  --source /path/to/face-reference.png \
  --target /path/to/generated-video.mp4 \
  --output /path/to/output.mp4
```

The source image should be a clear, front-facing photo — the better the
reference, the better the lock.

## Notes

- Swaps the **largest detected face** per frame (assumes a solo subject).
  Frames with no detected face are kept as-is, never dropped.
- Original audio is preserved — extracted from the target and muxed onto
  the output with ffmpeg.
- Speed on CPU: ~5s/frame (~20 min for a 10s clip at 24fps). Set
  `ctx_id=0` in `load_models()` to use GPU.
- For best results, direct the base video with **clear, expressive motion**
  (big smiles, open mouth when eating/talking). The swap can only preserve
  the motion the video gives it.
- For talking-head scenes, consider driving the mouth with real voiceover
  audio via a lip-sync tool after swapping.
