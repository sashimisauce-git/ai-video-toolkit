# AI Video Toolkit 🎬

Open-source tools for AI video creators: keep a consistent face across
generated clips, burn word-by-word karaoke captions, and publish one reel
to every platform with a single command.

**No coding required.** Double-click one file and everything runs in your
browser.

---

## 🚀 Easiest start (no coding)

**You need:** Python 3 (from [python.org](https://www.python.org/downloads/))
and ffmpeg (`brew install ffmpeg` on Mac, `winget install ffmpeg` on Windows).

| System | What to do |
|---|---|
| Mac / Linux | Download this repo (green **Code** button → **Download ZIP**), unzip, double-click **`start.sh`** |
| Windows | Download ZIP, unzip, double-click **`start.bat`** |

That's it. The launcher installs everything, downloads the AI models once
(~700MB, first run only), and opens the toolkit in your browser at
`http://127.0.0.1:7860`.

In the browser you get two tools:

1. **Face Swap** — upload a clear photo of a face + a video. The face gets
   locked onto every frame. Motion and expressions come from the video.
2. **Karaoke Captions** — upload voiceover audio, get word-by-word
   highlighted subtitles. Add a video to burn them straight in.

Everything runs 100% on your computer. No uploads, no accounts, no fees.

---

## 🛠 Command-line usage (for developers)

```bash
pip install -r requirements.txt
python download_models.py   # one-time model download

# 1. Lock the face
python face-swap/swap.py \
  --source face-ref.png --target generated.mp4 --output locked.mp4

# 2. Caption it
python karaoke-captions/make_karaoke.py \
  --input voiceover.mp3 --output karaoke.ass
ffmpeg -i locked.mp4 -vf "ass=karaoke.ass" -c:a copy captioned.mp4

# 3. Publish it
cd reel-publisher && ./publish.sh captioned.mp4 caption.txt
```

## Tools

| Tool | What it does |
|---|---|
| [face-swap](face-swap/) | Lock a consistent face onto AI-generated video (InsightFace). Generate for motion/background, swap the reference face onto every frame. Edge-free blending: inverse-warp + XSeg occlusion mask + color matching. |
| [karaoke-captions](karaoke-captions/) | Word-by-word highlighted subtitles from any voiceover audio (faster-whisper → ASS). Burn in with ffmpeg. |
| [reel-publisher](reel-publisher/) | One-command publishing: validate video, post to Instagram via API, stage TikTok/YouTube uploads with a manifest, log everything. |

## Requirements

- Python 3.8+
- `ffmpeg` + `ffprobe` on your PATH
- ~1.5GB disk for AI models (auto-downloaded on first run)

## Pipeline tips

- **Static camera wins.** AI-generated video with a locked-off camera
  (no auto-zoom, no drift) reads as real phone footage. Zoom is the #1
  AI tell.
- **Direct the base video with big, clear motion.** Face-swap preserves
  the target's expressions — subtle motion in means subtle motion out.
- **Disclose AI-generated content** per each platform's rules (Instagram's
  AI label, TikTok's AI-content toggle, YouTube's synthetic-content
  disclosure).

## License

MIT — use it, fork it, sell what you make with it.
