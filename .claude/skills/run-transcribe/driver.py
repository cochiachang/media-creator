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


def merge_videos(video_paths: list[Path], dest_dir: Path) -> Path:
    """Merge multiple video files into a single MP4 using ffmpeg concat demuxer.

    Files are merged in the order given (caller should sort them first).
    Returns the path to the merged MP4 inside dest_dir.
    """
    out = dest_dir / "merged.mp4"
    list_file = dest_dir / "concat_list.txt"

    with open(list_file, "w", encoding="utf-8") as f:
        for p in video_paths:
            # ffmpeg concat list uses forward slashes and requires the path
            # to be quoted with single quotes when it contains spaces.
            f.write(f"file '{p}'\n")

    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(list_file), "-c", "copy", str(out)],
        check=True, capture_output=True,
    )
    return out


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


def merge_duplicate_srt(srt_text: str) -> str:
    """
    合併連續重複的字幕段落：
    若相鄰兩段（或多段）的字幕文字完全相同，保留第一段的開始時間、
    最後一段的結束時間，其餘段落移除，並重新編號。
    """
    import re

    SEG_RE = re.compile(
        r"(\d+)\s*\n"                                          # 編號
        r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\s*\n"  # 時間戳
        r"(.*?)"                                               # 字幕文字（可多行）
        r"(?=\n\s*\n|\Z)",                                     # 以空白行或字串尾結束
        re.DOTALL,
    )

    segments = [
        {"start": m.group(2), "end": m.group(3), "text": m.group(4).strip()}
        for m in SEG_RE.finditer(srt_text)
    ]

    if not segments:
        return srt_text

    merged: list[dict] = []
    cur = segments[0].copy()

    for seg in segments[1:]:
        if seg["text"] == cur["text"]:
            # 相同文字 → 延長結束時間
            cur["end"] = seg["end"]
        else:
            merged.append(cur)
            cur = seg.copy()
    merged.append(cur)

    removed = len(segments) - len(merged)
    if removed:
        print(f"合併連續重複字幕：移除 {removed} 段（剩餘 {len(merged)} 段）")

    lines = []
    for i, seg in enumerate(merged, 1):
        lines.append(f"{i}\n{seg['start']} --> {seg['end']}\n{seg['text']}\n")
    return "\n".join(lines)


def correct_srt_with_llm(srt_text: str, background: str) -> str:
    """
    Use GPT-5.5 to fix homophones and segmentation errors in the SRT,
    preserving all timestamps exactly. Also translates English text to Chinese.
    """
    print("使用 GPT-5.5 校正同音字與斷句錯誤（含英文翻中文）…")

    background_section = f"影片背景：{background}\n\n" if background else ""

    response = client.chat.completions.create(
        model="gpt-5.5-2026-04-23",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是專業的繁體中文字幕校稿員，專門修正語音轉錄（Whisper）產生的同音字錯誤，並將英文字幕翻譯為繁體中文。\n\n"
                    "規則：\n"
                    "1. 根據上下文語意修正同音字或音近字錯誤，例如「質地」→「之一」、「已經」→「一定」等\n"
                    "2. 若字幕內容為英文（或混有英文句子），將英文部分翻譯為自然流暢的繁體中文\n"
                    "3. SRT 時間戳（如 00:00:28,600 --> 00:00:30,900）完全不可修改\n"
                    "4. 字幕編號不可修改\n"
                    "5. 只修改文字內容，不合併或拆分字幕段落\n"
                    "6. 若原文正確或不確定，保留原文不動\n"
                    "7. 直接輸出修正後的完整 SRT 內容，不加任何說明或 markdown"
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
    )

    corrected = response.choices[0].message.content.strip()

    # Safety checks: validate the corrected SRT looks like real subtitles
    import re
    original_ts_count = len(re.findall(r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}", srt_text))
    corrected_ts_count = len(re.findall(r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}", corrected))

    # Check 1: corrected must not be much shorter
    if len(corrected) < len(srt_text) * 0.5:
        print("⚠️  GPT-4o 回傳內容過短，保留 Whisper 原始輸出。")
        return srt_text

    # Check 2: corrected must have at least 80% of the original timestamp count
    if original_ts_count > 0 and corrected_ts_count < original_ts_count * 0.8:
        print(f"⚠️  GPT-4o 時間戳數量不符（原始 {original_ts_count} 段，校正後 {corrected_ts_count} 段），保留 Whisper 原始輸出。")
        return srt_text

    # Check 3: detect if GPT replaced content with background text (repetitive lines)
    lines = [l.strip() for l in corrected.splitlines() if l.strip() and not re.match(r"^\d+$", l) and "-->" not in l]
    if lines and len(set(lines)) == 1:
        print("⚠️  GPT-4o 回傳內容全部相同（疑似以背景資訊覆寫字幕），保留 Whisper 原始輸出。")
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

        print(f"送交 Whisper API（language=zh）：{audio_path.name}")
        with open(audio_path, "rb") as f:
            srt_text = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="srt",
                language="zh",          # 明確指定繁體/簡體中文，跳過語言偵測
            )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step A2: fill gaps — extend each segment end to the next segment start
    srt_text = fill_srt_gaps(srt_text)

    # Step A3: merge consecutive duplicate subtitles
    srt_text = merge_duplicate_srt(srt_text)

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
    originals_to_delete: list[Path] = []   # original segment files to delete after success

    if not args.input_file:
        # Auto-pick from upload/; merge automatically when multiple files exist
        # Sort by filename (alphabetical) to ensure correct segment order
        candidates = sorted(
            [f for f in UPLOAD_DIR.glob("*") if f.suffix.lower() in AUDIO_EXTS | VIDEO_EXTS],
            key=lambda p: p.name,
        )
        if not candidates:
            sys.exit(f"找不到 upload/ 內的影片或音訊檔案。")
        if len(candidates) == 1:
            input_path = candidates[0]
            print(f"自動選取：{input_path.name}")
        else:
            # Multiple files → merge into upload/merged.mp4, then transcribe
            print(f"找到 {len(candidates)} 個影片，依檔名順序合併為 merged.mp4：")
            for f in candidates:
                print(f"  - {f.name}")
            print("合併中（ffmpeg concat）…")
            try:
                input_path = merge_videos(candidates, UPLOAD_DIR)
            except subprocess.CalledProcessError as e:
                sys.exit(f"❌ ffmpeg 合併失敗：{e.stderr.decode(errors='replace')}")
            print(f"✅ 合併完成：{input_path.name}（{input_path.stat().st_size // 1024 // 1024} MB）")
            # 記錄原始檔案，轉錄成功後刪除
            originals_to_delete = [f for f in candidates if f != input_path]
    else:
        input_path = Path(args.input_file)
        if not input_path.is_absolute():
            input_path = UPLOAD_DIR / args.input_file

    if not input_path.exists():
        sys.exit(f"找不到檔案：{input_path}")

    # Resolve output path
    if args.output_srt:
        output_srt = Path(args.output_srt)
        if not output_srt.is_absolute():
            output_srt = OUTPUT_DIR / args.output_srt
    else:
        output_srt = OUTPUT_DIR / (input_path.stem + ".srt")

    transcribe(input_path, output_srt, background=args.background, do_correct=False)

    # 轉錄成功後刪除原始分段檔案
    if originals_to_delete:
        print(f"🗑️  刪除原始分段檔案（共 {len(originals_to_delete)} 個）…")
        for f in originals_to_delete:
            f.unlink()
            print(f"   刪除：{f.name}")
        print("✅ 原始檔案已清除，upload/ 僅保留 merged.mp4")


if __name__ == "__main__":
    main()
