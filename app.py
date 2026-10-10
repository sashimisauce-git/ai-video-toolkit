#!/usr/bin/env python3
"""
AI Video Toolkit — one-click web UI.

Run:  python app.py        (or double-click start.sh / start.bat)
Then open the URL it prints (usually http://127.0.0.1:7860).

Two tools:
  1. Face Swap      — lock a consistent face onto AI-generated video
  2. Karaoke Captions — word-by-word highlighted subtitles, burned into video

First run downloads AI models automatically (~700MB, one time).
No coding required — everything happens in your browser.
"""
import os
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

OUTPUT_DIR = os.path.join(SCRIPT_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def ensure_models():
    """Download required models on first run (with visible progress)."""
    from download_models import main as dl_main
    missing = dl_main(check_only=True)
    if missing:
        print(f"[app] downloading {len(missing)} missing model(s)...", flush=True)
        dl_main()
    else:
        print("[app] all models present", flush=True)


def run_faceswap(source_img, target_vid, progress=None):
    """Swap the face from source_img onto every frame of target_vid."""
    if source_img is None:
        raise ValueError("Upload a source face photo first.")
    if target_vid is None:
        raise ValueError("Upload a target video first.")

    sys.path.insert(0, os.path.join(SCRIPT_DIR, "face-swap"))
    import swap

    out_path = os.path.join(OUTPUT_DIR, "faceswap_output.mp4")
    app, swapper, xseg = swap.load_models()
    source_face = swap.get_source_face(app, source_img)

    # frame-accurate progress via a wrapped writer loop
    import cv2
    cap = cv2.VideoCapture(target_vid)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    cap.release()

    with tempfile.TemporaryDirectory() as tmp:
        silent = os.path.join(tmp, "swapped_silent.mp4")
        # monkey-patch the per-25-frame print into gradio progress
        orig_print = print
        def prog_print(*a, **k):
            import builtins
            msg = " ".join(str(x) for x in a)
            if msg.startswith("[faceswap] frame ") and "/" in msg:
                try:
                    done = int(msg.split()[1].split("/")[0])
                    if progress is not None:
                        progress(done / total, desc=f"Swapping frame {done}/{total}")
                except Exception:
                    pass
            orig_print(*a, **k)
        import builtins
        builtins.print = prog_print
        try:
            swap.swap_video(app, swapper, xseg, source_face, target_vid, silent)
        finally:
            builtins.print = orig_print
        swap.mux_audio(silent, target_vid, out_path)
    return out_path


def run_karaoke(audio, video, words_per_line, progress=None):
    """Transcribe audio -> karaoke ASS; optionally burn into video."""
    if audio is None:
        raise ValueError("Upload a voiceover audio file first.")

    sys.path.insert(0, os.path.join(SCRIPT_DIR, "karaoke-captions"))
    import make_karaoke

    ass_path = os.path.join(OUTPUT_DIR, "karaoke.ass")
    if progress is not None:
        progress(0.1, desc="Transcribing audio...")
    segments = make_karaoke.transcribe(audio, None, "small")
    if progress is not None:
        progress(0.7, desc="Building karaoke timing...")
    lines = make_karaoke.build_lines(segments, int(words_per_line))
    with open(ass_path, "w") as f:
        f.write(make_karaoke.ASS_HEADER)
        for start, end, ktext in lines:
            f.write(f"Dialogue: 0,{make_karaoke.ts(start)},{make_karaoke.ts(end)},"
                    f"Karaoke,,0,0,0,,{ktext}\n")
    print(f"[karaoke] wrote {ass_path} ({len(lines)} lines)", flush=True)

    if video:
        if progress is not None:
            progress(0.85, desc="Burning captions into video...")
        out_path = os.path.join(OUTPUT_DIR, "captioned_output.mp4")
        # escape for ffmpeg ass filter
        ass_escaped = ass_path.replace(":", "\\:").replace("'", "'\\''")
        cmd = ["ffmpeg", "-y", "-v", "error",
               "-i", video, "-vf", f"ass='{ass_escaped}'",
               "-c:a", "copy", out_path]
        subprocess.run(cmd, check=True)
        if progress is not None:
            progress(1.0, desc="Done")
        return ass_path, out_path
    if progress is not None:
        progress(1.0, desc="Done")
    return ass_path, None


def build_ui():
    import gradio as gr

    with gr.Blocks(title="AI Video Toolkit") as demo:
        gr.Markdown(
            "# 🎬 AI Video Toolkit\n"
            "Lock a consistent face onto AI-generated video, and burn "
            "word-by-word karaoke captions. Runs 100% on your computer."
        )
        with gr.Tab("Face Swap"):
            gr.Markdown(
                "Upload a clear front-facing **photo** and a **video**. "
                "The face from the photo is locked onto every frame. "
                "Motion and expressions come from the video."
            )
            with gr.Row():
                src_img = gr.Image(label="Source face photo", type="filepath")
                tgt_vid = gr.Video(label="Target video")
            swap_btn = gr.Button("🔄 Swap Face", variant="primary")
            swap_out = gr.Video(label="Result")
            swap_btn.click(run_faceswap, inputs=[src_img, tgt_vid], outputs=swap_out)

        with gr.Tab("Karaoke Captions"):
            gr.Markdown(
                "Upload **voiceover audio** to get word-by-word karaoke subtitles. "
                "Optionally add a **video** to burn the captions straight in."
            )
            with gr.Row():
                audio_in = gr.Audio(label="Voiceover audio", type="filepath")
                vid_in = gr.Video(label="Video to caption (optional)")
            wpl = gr.Slider(3, 10, value=6, step=1,
                            label="Max words per caption line")
            cap_btn = gr.Button("✨ Generate Captions", variant="primary")
            with gr.Row():
                ass_out = gr.File(label="Subtitle file (.ass)")
                cap_vid_out = gr.Video(label="Captioned video")
            cap_btn.click(run_karaoke,
                          inputs=[audio_in, vid_in, wpl],
                          outputs=[ass_out, cap_vid_out])

        gr.Markdown(
            "---\n*Tip: face-swap runs ~5s/frame on CPU. A 10-second clip takes "
            "a few minutes — grab a coffee. Karaoke captions take under a minute.*"
        )
    return demo


if __name__ == "__main__":
    print("[app] checking models...", flush=True)
    ensure_models()
    demo = build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7860,
                inbrowser=True, show_error=True)
