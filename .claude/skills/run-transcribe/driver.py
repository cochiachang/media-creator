#!/usr/bin/env python3
"""
Transcribe video/audio to SRT using OpenAI Whisper API,
then correct homophones and segmentation with GPT-4o.

Usage: python driver.py <input_file> [output.srt] [--background TEXT] [--no-correct]

Input  : any file in upload/ (mp4, mov, mp3, wav, m4a, webm, ogg, flac …)
Output : SRT file in output/ (default: same stem as input + .srt)
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from openai import OpenAI

BASE = Path(__file__).resolve().parents[3]   # repo root
UPLOAD_DIR = BASE / "upload"
OUTPUT_DIR = BASE / "output"

AUDIO_EXTS  = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".aac"}
VIDEO_EXTS  = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".ts"}
MAX_BYTES   = 25 * 1024 * 1024   # Whisper hard limit

client: OpenAI = None  # initialised in main() after arg parsing


def extract_audio(video_path: Path, dest: Path) -> Path:
    """Extract mono 16-kHz MP3 from a video — small enough for the API."""
    out = dest / (video_path.stem + "_audio.mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path),
         "-vn", "-ac", "1", "-ar", "16000", "-q:a", "4", str(out)],
        check=True, capture_output=True,
    )
    return out


def build_whisper_prompt(background: str) -> str:
    """
    Build a Whisper prompt that injects domain vocabulary.
    Whisper uses the last ~224 tokens of the prompt as prior context,
    which steers the language model toward these terms.
    """
    base = "繁體中文口語轉錄。常見詞彙：之一、之中、也是、而是、還是、就是、都是、只是、但是、所以、因為、然後、其實、可以、沒有、大家、我們、他們、這樣、那麼、雖然、如果、應該、一定、當然、比賽、評審、國際、評選、精品、咖啡、產區。"
    if background:
        return base + f" 影片背景：{background}"
    return base


def fill_srt_gaps(srt_text: str) -> str:
    """
    Extend each segment's end time to the next segment's start time,
    eliminating silent gaps that Whisper leaves between segments.
    Only fills gaps; never shortens a segment or overlaps with the next.
    """
    import re

    TIME_RE = re.compile(
        r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})"
    )

    def to_ms(ts: str) -> int:
        h, m, rest = ts.split(":")
        s, ms = rest.split(",")
        return int(h) * 3_600_000 + int(m) * 60_000 + int(s) * 1_000 + int(ms)

    def to_ts(ms: int) -> str:
        h = ms // 3_600_000; ms %= 3_600_000
        m = ms // 60_000;    ms %= 60_000
        s = ms // 1_000;     ms %= 1_000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = srt_text.splitlines()
    # Collect positions of all timestamp lines and their parsed values
    ts_lines: list[tuple[int, int, int]] = []   # (line_idx, start_ms, end_ms)
    for i, line in enumerate(lines):
        m = TIME_RE.fullmatch(line.strip())
        if m:
            ts_lines.append((i, to_ms(m.group(1)), to_ms(m.group(2))))

    # For each segment, if its end < next segment's start → extend to next start
    for idx in range(len(ts_lines) - 1):
        i, start_ms, end_ms   = ts_lines[idx]
        _, next_start_ms, _   = ts_lines[idx + 1]
        if end_ms < next_start_ms:
            new_end = next_start_ms
            lines[i] = f"{to_ts(start_ms)} --> {to_ts(new_end)}"
            ts_lines[idx] = (i, start_ms, new_end)

    return "\n".join(lines)


def correct_srt_with_llm(srt_text: str, background: str) -> str:
    """
    Use GPT-4o to fix homophones and segmentation errors in the SRT,
    preserving all timestamps exactly.
    """
    print("使用 GPT-4o 校正同音字與斷句錯誤…")

    background_section = f"影片背景：{background}\n\n" if background else ""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是專業的繁體中文字幕校稿員，專門修正語音轉錄（Whisper）產生的同音字錯誤。\n\n"
                    "規則：\n"
                    "1. 根據上下文語意修正同音字或音近字錯誤，例如「質地」→「之一」、「已經」→「一定」等\n"
                    "2. SRT 時間戳（如 00:00:28,600 --> 00:00:30,900）完全不可修改\n"
                    "3. 字幕編號不可修改\n"
                    "4. 只修改文字內容，不合併或拆分字幕段落\n"
                    "5. 若原文正確或不確定，保留原文不動\n"
                    "6. 直接輸出修正後的完整 SRT 內容，不加任何說明或 markdown"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{background_section}"
                    f"以下是 Whisper 轉錄的字幕，請校正同音字錯誤：\n\n{srt_text}"
                ),
            },
        ],
        temperature=0,
    )

    corrected = response.choices[0].message.content.strip()
    # Safety: if the response is clearly malformed (e.g., much shorter than original), keep original
    if len(corrected) < len(srt_text) * 0.5:
        print("⚠️  GPT-4o 回傳內容異常，保留 Whisper 原始輸出。")
        return srt_text
    return corrected


def transcribe(input_path: Path, output_srt: Path, background: str, do_correct: bool) -> None:
    ext = input_path.suffix.lower()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        if ext in VIDEO_EXTS:
            print(f"從影片萃取音訊：{input_path.name}")
            audio_path = extract_audio(input_path, tmp_path)
        elif ext in AUDIO_EXTS:
            audio_path = input_path
        else:
            sys.exit(f"不支援的檔案格式：{ext}")

        if audio_path.stat().st_size > MAX_BYTES:
            sys.exit(f"檔案超過 {MAX_BYTES // 1024 // 1024} MB 限制，請先用 ffmpeg 切段。")

        whisper_prompt = build_whisper_prompt(background)
        print(f"送交 Whisper API（language=zh）：{audio_path.name}")
        with open(audio_path, "rb") as f:
            srt_text = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="srt",
                language="zh",          # 明確指定繁體/簡體中文，跳過語言偵測
                prompt=whisper_prompt,  # 注入 domain 詞彙，降低同音字誤轉
            )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step A2: fill gaps — extend each segment end to the next segment start
    srt_text = fill_srt_gaps(srt_text)

    # Step B: GPT-4o correction
    if do_correct:
        srt_text = correct_srt_with_llm(srt_text, background)

    output_srt.write_text(srt_text, encoding="utf-8")
    print(f"✅ SRT 已儲存：{output_srt}")


def main():
    parser = argparse.ArgumentParser(description="Transcribe video/audio to SRT with homophone correction.")
    parser.add_argument("input_file", nargs="?", help="Input file (relative to upload/ or absolute)")
    parser.add_argument("output_srt", nargs="?", help="Output SRT path (optional)")
    parser.add_argument("--background", "-b", default="", help="影片背景資訊（主角、主題、品牌等），提升同音字準確度")
    parser.add_argument("--no-correct", action="store_true", help="跳過 GPT-4o 校正步驟，只跑 Whisper")

    args = parser.parse_args()

    # Init OpenAI client
    global client
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("❌ 請先設定 OPENAI_API_KEY：export OPENAI_API_KEY=<your-key>")
    client = OpenAI(api_key=api_key)

    # Resolve input file
    if not args.input_file:
        # Auto-pick if only one file in upload/
        candidates = sorted(UPLOAD_DIR.glob("*"))
        candidates = [f for f in candidates if f.suffix.lower() in AUDIO_EXTS | VIDEO_EXTS]
        if not candidates:
            sys.exit(f"找不到 upload/ 內的影片或音訊檔案。")
        if len(candidates) == 1:
            input_path = candidates[0]
            print(f"自動選取：{input_path.name}")
        else:
            print("找到多個檔案，請選擇：")
            for i, f in enumerate(candidates, 1):
                print(f"  {i}. {f.name}")
            choice = input("請輸入編號：").strip()
            try:
                input_path = candidates[int(choice) - 1]
            except (ValueError, IndexError):
                sys.exit("無效的選擇。")
    else:
        input_path = Path(args.input_file)
        if not input_path.is_absolute():
            input_path = UPLOAD_DIR / input_path

    if not input_path.exists():
        sys.exit(f"找不到檔案：{input_path}")

    # Resolve output path
    if args.output_srt:
        output_srt = Path(args.output_srt)
        if not output_srt.is_absolute():
            output_srt = OUTPUT_DIR / output_srt
    else:
        output_srt = OUTPUT_DIR / (input_path.stem + ".srt")

    # Ask for background if not provided and correction is enabled
    background = args.background
    if not background and not args.no_correct:
        print("\n💡 提供影片背景資訊可提升同音字辨識準確度（可直接按 Enter 跳過）")
        background = input("影片背景（主角、主題、品牌、專有名詞等）：").strip()

    transcribe(input_path, output_srt, background, do_correct=not args.no_correct)


if __name__ == "__main__":
    main()
