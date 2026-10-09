#!/usr/bin/env python3
"""
make_karaoke.py — Word-by-word karaoke subtitles for vertical video.

Transcribes audio with faster-whisper (word timestamps), groups words into
short lines, and writes an ASS subtitle file with \\k timing tags for the
classic karaoke highlight effect. Burn into video with ffmpeg:

    ffmpeg -i input.mp4 -vf "ass=karaoke.ass" -c:a copy output.mp4

Usage:
    python make_karaoke.py --input voiceover.mp3 --output karaoke.ass
"""
import argparse
import subprocess

import numpy as np


def transcribe(audio_path, model_path, model_size="small"):
    from faster_whisper import WhisperModel

    # decode to 16kHz mono float32 via ffmpeg (robust to odd containers)
    cmd = ["ffmpeg", "-v", "error", "-i", audio_path,
           "-ar", "16000", "-ac", "1", "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    audio = np.frombuffer(raw, dtype=np.float32)

    if model_path:
        model = WhisperModel(model_path, device="cpu",
                             compute_type="int8", local_files_only=True)
    else:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio, word_timestamps=True)
    return segments


def ts(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h}:{m:02d}:{sec:05.2f}"


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,DejaVu Sans,60,&H0000FFFF,&H00FFFFFF,&H90000000,&H90000000,-1,0,0,0,100,100,1,0,1,3,0,2,60,60,760,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_lines(segments, words_per_line=6):
    lines = []
    for seg in segments:
        words = [w for w in seg.words if w.word.strip()]
        for i in range(0, len(words), words_per_line):
            chunk = words[i:i + words_per_line]
            start = chunk[0].start
            end = chunk[-1].end
            ktext = ""
            prev_end = start
            for w in chunk:
                # silence gap before the word keeps sync honest
                gap_cs = int(round((w.start - prev_end) * 100))
                if gap_cs > 2:
                    ktext += f"{{\\k{gap_cs}}}"
                dur_cs = max(1, int(round((w.end - w.start) * 100)))
                ktext += f"{{\\k{dur_cs}}}{w.word.strip()} "
                prev_end = w.end
            lines.append((start, end, ktext.strip()))
    return lines


def main():
    ap = argparse.ArgumentParser(description="Word-by-word karaoke ASS subtitles")
    ap.add_argument("--input", required=True, help="input audio file (mp3/wav)")
    ap.add_argument("--output", default="karaoke.ass", help="output .ass file")
    ap.add_argument("--model-path", default=None,
                    help="local faster-whisper model dir (else downloads)")
    ap.add_argument("--model-size", default="small",
                    help="model size if downloading (tiny/base/small/medium)")
    ap.add_argument("--words-per-line", type=int, default=6)
    args = ap.parse_args()

    segments = transcribe(args.input, args.model_path, args.model_size)
    lines = build_lines(segments, args.words_per_line)

    with open(args.output, "w") as f:
        f.write(ASS_HEADER)
        for start, end, ktext in lines:
            f.write(f"Dialogue: 0,{ts(start)},{ts(end)},Karaoke,,0,0,0,,{ktext}\n")

    print(f"Wrote {args.output} with {len(lines)} lines")
    for s, e, t in lines[:8]:
        print(f"{s:.2f}-{e:.2f}: {t[:70]}")


if __name__ == "__main__":
    main()
