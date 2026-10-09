# Reel publisher — one command from finished video to everywhere

## Why

Posting a reel to three platforms means three upload flows, three caption
pastes, and a spreadsheet to track what went where. This script compresses
all of it: validate the video, grab a cover frame, post to Instagram via
API, stage TikTok/YouTube packages with a JSON manifest, and log the run.

## Requirements

- `ffmpeg` + `ffprobe`, `python3`
- For Instagram auto-posting: set `IG_ACCOUNT_ID` and have an
  `instagram-cli` on your PATH (Meta's official CLI or your own wrapper).
  Without it, Instagram is skipped gracefully and everything else still runs.
- TikTok and YouTube have no reliable pure-API upload path — they get
  staged files + a manifest for manual or browser-automated upload.

## Usage

```bash
export IG_ACCOUNT_ID="your-instagram-account-id"
./publish.sh /path/to/video.mp4 /path/to/caption.txt
./publish.sh /path/to/video.mp4 /path/to/caption.txt ig,tiktok   # subset
```

## What it does

1. **Validates** — checks 1080×1920, duration ≤ 90s, audio stream present.
   Warns (doesn't fail) on dimension/duration mismatches.
2. **Caption** — reads the caption file, fails on empty.
3. **Cover** — extracts a frame at 1s as the thumbnail.
4. **Stages** — copies video + caption into `staging/` so the originals
   are never touched by upload tooling.
5. **Instagram** — posts via API when credentials are configured.
6. **Manifest** — writes `<name>-manifest.json` with per-platform upload
   details: TikTok caption + AI-label flag, YouTube title/description/
   audience/AI-disclosure settings.
7. **Logs** — appends a row to `posting-log.md`.

## Output layout

```
reel-publisher/
  staging/
    <name>.mp4                  # staged copy
    <name>-caption.txt
    <name>-cover.jpg
    <name>-manifest.json        # TikTok/YouTube upload instructions
  posting-log.md                # every run, one row
```
