#!/bin/bash
# publish.sh — one-command reel publisher
# Usage: ./publish.sh <video.mp4> <caption.txt> [platforms]
#   platforms: comma-separated subset of ig,tiktok,youtube (default: all)
#
# Does: validates the video (1080x1920, duration, audio), extracts a cover
# frame, posts to Instagram via API, stages TikTok/YouTube packages + a JSON
# manifest for manual/browser upload, and logs everything.
#
# Requirements: ffmpeg, ffprobe, python3.
# Instagram posting needs IG_ACCOUNT_ID set and an `instagram-cli` on PATH
# (or swap in your own posting command in section 5).
# TikTok/YouTube have no reliable pure-API upload path — the manifest they
# get here is designed for manual or automated browser upload.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

VIDEO="${1:?Usage: publish.sh <video.mp4> <caption.txt> [platforms]}"
CAPTION_FILE="${2:?Usage: publish.sh <video.mp4> <caption.txt> [platforms]}"
PLATFORMS="${3:-ig,tiktok,youtube}"

STAGE_DIR="$SCRIPT_DIR/staging"
LOG_FILE="$SCRIPT_DIR/posting-log.md"
mkdir -p "$STAGE_DIR"

echo "=== Reel Publisher ==="

# ---- 1. Validate ----
[ -f "$VIDEO" ] || { echo "ERROR: video not found: $VIDEO"; exit 1; }
[ -f "$CAPTION_FILE" ] || { echo "ERROR: caption file not found: $CAPTION_FILE"; exit 1; }

DIMS=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$VIDEO")
WIDTH=$(echo "$DIMS" | cut -d, -f1); HEIGHT=$(echo "$DIMS" | cut -d, -f2)
DUR=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO" | cut -d. -f1)
HAS_AUDIO=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$VIDEO")

[ "$WIDTH" = "1080" ] && [ "$HEIGHT" = "1920" ] || echo "WARN: not 1080x1920 (got ${WIDTH}x${HEIGHT})"
[ "$DUR" -le 90 ] || echo "WARN: duration ${DUR}s — long for Shorts/Reels"
[ -n "$HAS_AUDIO" ] || { echo "ERROR: no audio stream"; exit 1; }
echo "OK: ${WIDTH}x${HEIGHT}, ${DUR}s, audio present"

# ---- 2. Caption ----
CAPTION=$(cat "$CAPTION_FILE")
[ -n "$CAPTION" ] || { echo "ERROR: empty caption"; exit 1; }
echo "OK: caption $(wc -c < "$CAPTION_FILE") bytes"

# ---- 3. Cover frame ----
BASENAME=$(basename "$VIDEO" .mp4)
COVER="$STAGE_DIR/${BASENAME}-cover.jpg"
ffmpeg -v error -y -ss 1 -i "$VIDEO" -frames:v 1 -q:v 3 "$COVER"
echo "OK: cover $COVER"

# ---- 4. Stage a copy ----
STAGED_VIDEO="$STAGE_DIR/${BASENAME}.mp4"
cp "$VIDEO" "$STAGED_VIDEO"
cp "$CAPTION_FILE" "$STAGE_DIR/${BASENAME}-caption.txt"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
MANIFEST="$STAGE_DIR/${BASENAME}-manifest.json"

# ---- 5. Instagram (direct API) ----
IG_ID=""
if [[ "$PLATFORMS" == *"ig"* ]]; then
  if [ -z "${IG_ACCOUNT_ID:-}" ]; then
    echo "WARN: IG_ACCOUNT_ID not set — skipping Instagram post"
  elif ! command -v instagram-cli >/dev/null 2>&1; then
    echo "WARN: instagram-cli not found — skipping Instagram post"
  else
    echo "--- Posting to Instagram ---"
    RESULT=$(instagram-cli post-feed --account-id "$IG_ACCOUNT_ID" \
      --file "$STAGED_VIDEO" --cover "$COVER" --caption "$CAPTION" 2>&1)
    echo "$RESULT" | head -3
    IG_ID=$(echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('media_fbid',''))" 2>/dev/null || echo "")
    [ -n "$IG_ID" ] && echo "OK: Instagram media_fbid=$IG_ID" || echo "WARN: no media_fbid parsed"
  fi
fi

# ---- 6. Manifest for TikTok/YouTube uploads ----
python3 - "$MANIFEST" "$BASENAME" "$TIMESTAMP" "$IG_ID" "$PLATFORMS" "$CAPTION_FILE" << 'EOF'
import json, sys
manifest_path, basename, ts, ig_id, platforms, caption_file = sys.argv[1:7]
with open(caption_file) as f:
    caption = f.read()
manifest = {
    "video": basename,
    "created_utc": ts,
    "caption": caption,
    "instagram": {"posted": bool(ig_id), "media_fbid": ig_id},
    "tiktok": {"needs_upload": "tiktok" in platforms,
               "caption": caption,
               "ai_content_label": True},
    "youtube": {"needs_upload": "youtube" in platforms,
                "title": caption.split("\n")[0][:100],
                "description": caption + " #shorts",
                "audience": "not made for kids",
                "ai_disclosure": True,
                "visibility": "Public"},
}
with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)
print(f"OK: manifest {manifest_path}")
EOF

# ---- 7. Log ----
if [ ! -f "$LOG_FILE" ]; then
  echo "# Posting Log" > "$LOG_FILE"
  echo "" >> "$LOG_FILE"
  echo "| Date (UTC) | Video | Instagram | TikTok | YouTube | Notes |" >> "$LOG_FILE"
  echo "|---|---|---|---|---|---|" >> "$LOG_FILE"
fi
echo "| $TIMESTAMP | $BASENAME | ${IG_ID:-pending} | pending | pending | manifest: ${BASENAME}-manifest.json |" >> "$LOG_FILE"
echo "OK: logged to posting-log.md"

echo ""
echo "=== Done ==="
echo "Instagram: $([ -n "$IG_ID" ] && echo "POSTED ($IG_ID)" || echo "skipped")"
echo "TikTok/YouTube: staged — upload from $MANIFEST"
