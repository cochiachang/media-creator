#!/usr/bin/env python3
"""
Transcribe video/audio to SRT using OpenAI Whisper API.
Usage: python driver.py <input_file> [output.srt]

Input  : any file in upload/ (mp4, mov, mp3, wav, m4a, webm, ogg, flac …)
Output : SRT file in output/ (default: same stem as input + .srt)
"""
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from openai import OpenAI

BASE = Path(__file__).resolve().parents[3]   # repo root
UPLOAD_DIR = BASE / "upload"
OUTPUT_DIR = BASE / "output"

AUDIO_EXTS  = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".aac"}
VIDEO_EXTS  = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".ts"}
MAX_BYTES   = 25 * 1024 * 1024   # Whisper hard limit

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def extract_audio(video_path: Path, dest: Path) -> Path:
    """Extract mono 16-kHz MP3 from a video — small enough for the API."""
    out = dest / (video_path.stem + "_audio.mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path),
         "-vn", "-ac", "1", "-ar", "16000", "-q:a", "4", str(out)],
        check=True, capture_output=True,
    )
    return out


def transcribe(input_path: Path, output_srt: Path) -> None:
    ext = input_path.suffix.lower()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        if ext in VIDEO_EXTS:
            print(f"Extracting audio from video: {input_path.name}")
            audio_path = extract_audio(input_path, tmp_path)
        elif ext in AUDIO_EXTS:
            audio_path = input_path
        else:
            sys.exit(f"Unsupported file type: {ext}")

        if audio_path.stat().st_size > MAX_BYTES:
            sys.exit(f"File too large (>{MAX_BYTES // 1024 // 1024} MB). Split it first.")

        print(f"Sending to Whisper API: {audio_path.name}")
        with open(audio_path, "rb") as f:
            srt_text = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="srt",
            )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_srt.write_text(srt_text, encoding="utf-8")
    print(f"SRT saved to: {output_srt}")


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python driver.py <input_file> [output.srt]")
        print(f"  Input looked up relative to {UPLOAD_DIR} if not absolute.")
        sys.exit(1)

    input_arg = Path(sys.argv[1])
    if not input_arg.is_absolute():
        input_arg = UPLOAD_DIR / input_arg

    if not input_arg.exists():
        sys.exit(f"File not found: {input_arg}")

    if len(sys.argv) >= 3:
        output_srt = Path(sys.argv[2])
        if not output_srt.is_absolute():
            output_srt = OUTPUT_DIR / output_srt
    else:
        output_srt = OUTPUT_DIR / (input_arg.stem + ".srt")

    transcribe(input_arg, output_srt)


if __name__ == "__main__":
    main()
