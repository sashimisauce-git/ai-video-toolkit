# AI Video Toolkit

Open-source tools for AI video creators: keep a consistent face across
generated clips, burn word-by-word karaoke captions, and publish one reel
to every platform with a single command.

Built for the AI-UGC workflow — generate the scene, lock the face, caption
it, ship it.

## Tools

| Tool | What it does |
|---|---|
| [face-swap](face-swap/) | Lock a consistent face onto AI-generated video (InsightFace). Generate for motion/background, swap the reference face onto every frame. |
| [karaoke-captions](karaoke-captions/) | Word-by-word highlighted subtitles from any voiceover audio (faster-whisper → ASS). Burn in with ffmpeg. |
| [reel-publisher](reel-publisher/) | One-command publishing: validate video, post to Instagram via API, stage TikTok/YouTube uploads with a manifest, log everything. |

## Quickstart

```bash
# 1. Lock the face
cd face-swap
# (download models first — see face-swap/README.md)
python swap.py --source face-ref.png --target generated.mp4 --output locked.mp4

# 2. Caption it
cd ../karaoke-captions
python make_karaoke.py --input voiceover.mp3 --output karaoke.ass
ffmpeg -i locked.mp4 -vf "ass=karaoke.ass" -c:a copy captioned.mp4

# 3. Publish it
cd ../reel-publisher
./publish.sh captioned.mp4 caption.txt
```

## Requirements

- Python 3.8+
- `ffmpeg` + `ffprobe`
- See each tool's README for its Python packages and model downloads.

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
