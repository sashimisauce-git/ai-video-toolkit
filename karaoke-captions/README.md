# Karaoke captions — word-by-word subtitles for vertical video

## Why

Word-by-word highlighted captions (the "karaoke" effect) are the standard
for talking-head reels, Shorts, and TikToks. Viewers watch with sound off;
captions keep them watching. This tool generates them from any voiceover
audio with precise per-word timing.

## Requirements

- Python 3.8+
- `pip install faster-whisper numpy`
- `ffmpeg` on your PATH (used for audio decode and subtitle burn-in)

## Usage

```bash
python make_karaoke.py --input voiceover.mp3 --output karaoke.ass
```

Options:

| Flag | Default | What it does |
|---|---|---|
| `--input` | (required) | Audio file to transcribe |
| `--output` | `karaoke.ass` | Output subtitle file |
| `--model-path` | none | Local faster-whisper model dir (skips download) |
| `--model-size` | `small` | Model size when downloading (`tiny`/`base`/`small`/`medium`) |
| `--words-per-line` | `6` | Max words per caption line |

Then burn into your video:

```bash
ffmpeg -i input.mp4 -vf "ass=karaoke.ass" -c:a copy output.mp4
```

## How it works

1. Audio is decoded to 16kHz mono via ffmpeg (robust to odd containers).
2. faster-whisper transcribes with `word_timestamps=True`.
3. Words are grouped into short lines (default 6 words).
4. Each word gets a `\k` timing tag; silence gaps between words get their
   own tags so highlighting stays in sync with the audio.
5. Output is a standard ASS file styled for 1080×1920 (yellow highlight,
   white upcoming text, bottom-center).

## Tips

- `small` is the sweet spot for accuracy vs speed on CPU. `tiny` is fast
  but mangles names and uncommon words — proofread the output.
- If the transcription mishears a recurring word (brand names, etc.), fix
  it with `sed` on the `.ass` file before burn-in.
- The style block at the top of the script sets font, size, and colors —
  tweak `Fontsize` (60) and `PrimaryColour` (highlight) to match your brand.
