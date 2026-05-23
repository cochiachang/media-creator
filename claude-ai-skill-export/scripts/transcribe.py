#!/usr/bin/env python3
"""
Transcribe video/audio to SRT using OpenAI Whisper API.
Usage: python transcribe.py <input_file> [output.srt]
"""
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from openai import OpenAI

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".aac"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".ts"}
MAX_BYTES  = 25 * 1024 * 1024

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def extract_audio(video_path: Path, dest: Path) -> Path:
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

    output_srt.parent.mkdir(parents=True, exist_ok=True)
    output_srt.write_text(srt_text, encoding="utf-8")
    print(f"SRT saved to: {output_srt}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <input_file> [output.srt]")
        sys.exit(1)

    input_path = Path(sys.argv[1]).resolve()
    if not input_path.exists():
        sys.exit(f"File not found: {input_path}")

    if len(sys.argv) >= 3:
        output_srt = Path(sys.argv[2]).resolve()
    else:
        output_srt = input_path.with_suffix(".srt")

    transcribe(input_path, output_srt)


if __name__ == "__main__":
    main()
