#!/usr/bin/env python3
"""
精華短片剪輯器 - 製作3秒彈出片頭 + 降噪剪輯片段，合併輸出
"""
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
UPLOAD_DIR = PROJECT_ROOT / "upload"
CLIPS_DIR = OUTPUT_DIR / "clips"

FONTSIZE = 32
INTRO_DURATION = 3
LINE_SPACING = 8


def find_font():
    local_font = SKILL_DIR / "微軟正黑體.ttf"
    if local_font.exists():
        return str(local_font)
    for path in [
        "/Library/Fonts/Microsoft/Microsoft JhengHei.ttf",
        "/Library/Fonts/Microsoft/Microsoft JhengHei Bold.ttf",
        "/Users/Shared/Microsoft/Office365/Microsoft JhengHei.ttf",
    ]:
        if Path(path).exists():
            return path
    try:
        result = subprocess.run(
            ["fc-list", ":lang=zh-tw"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "PingFang" in line and "TC" in line and "Regular" in line:
                font_path = line.split(":")[0].strip()
                if Path(font_path).exists():
                    return font_path
    except Exception:
        pass
    fallback = "/System/Library/Fonts/STHeiti Medium.ttc"
    if Path(fallback).exists():
        return fallback
    return None


def get_video_info(video_path):
    result = subprocess.run(
        ["ffmpeg", "-i", str(video_path), "-hide_banner"],
        capture_output=True, text=True,
    )
    import re as _re
    width, height, has_audio = 720, 1280, False
    for line in result.stderr.splitlines():
        m = _re.search(r"(\d{3,5})x(\d{3,5})", line)
        if m and "Video" in line:
            width, height = int(m.group(1)), int(m.group(2))
        if "Audio" in line:
            has_audio = True
    return width, height, has_audio


def text_display_width(text):
    """CJK chars = 1 unit, ASCII = 0.5 unit."""
    w = 0.0
    for ch in text:
        cp = ord(ch)
        if 0x4E00 <= cp <= 0x9FFF or 0x3000 <= cp <= 0x303F or 0xFF00 <= cp <= 0xFFEF:
            w += 1.0
        else:
            w += 0.5
    return w


def wrap_text(text, video_width, margin=120):
    """Return list of lines that each fit within (video_width - margin) at FONTSIZE."""
    max_units = (video_width - margin) / FONTSIZE
    if text_display_width(text) <= max_units:
        return [text]
    lines, current, cur_w = [], [], 0.0
    for ch in text:
        ch_w = 1.0 if text_display_width(ch) >= 0.9 else 0.5
        if cur_w + ch_w > max_units and current:
            lines.append("".join(current))
            current, cur_w = [ch], ch_w
        else:
            current.append(ch)
            cur_w += ch_w
    if current:
        lines.append("".join(current))
    return lines


def escape_for_text(s):
    """Escape a single line for use in drawtext text='...' (single-quoted value)."""
    return (
        s
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


def hms_to_s(hms):
    # Support both HH:MM:SS and HH:MM:SS,mmm (SRT format)
    hms = hms.replace(",", ".")
    parts = hms.split(":")
    h, m = int(parts[0]), int(parts[1])
    s = float(parts[2])
    return h * 3600 + m * 60 + s


def s_to_hms(s):
    s = int(s)
    h, r = divmod(s, 3600)
    m, sec = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def create_intro(title, font_path, video_w, video_h, output_path):
    """3-second black intro: each text line is independently centred, pop-in over 0.5s."""
    lines = wrap_text(title, video_w, margin=120)
    n = len(lines)

    # Pre-compute the vertical centre of each line at final font size.
    # The text block is vertically centred; y='{cy}-th/2' keeps each line
    # centred at cy regardless of the current (animated) font size.
    total_h = n * FONTSIZE + (n - 1) * LINE_SPACING
    y_block_top = (video_h - total_h) // 2

    font_arg = f"fontfile='{font_path}'" if font_path else "font='STHeiti'"
    # Linear grow 1px → FONTSIZE over 0.5s; never exceeds FONTSIZE (no overshoot).
    fs_expr = f"max(1,{FONTSIZE}*min(1,t/0.5))"

    # One drawtext filter per line so x=(w-tw)/2 centres THAT line independently.
    parts = []
    for i, line in enumerate(lines):
        cy = y_block_top + i * (FONTSIZE + LINE_SPACING) + FONTSIZE // 2
        safe = escape_for_text(line)
        parts.append(
            f"drawtext={font_arg}"
            f":text='{safe}'"
            f":fontsize='{fs_expr}'"
            f":fontcolor=white"
            f":x=(w-tw)/2"
            f":y='{cy}-th/2'"
            f":box=1:boxcolor=black@0.5:boxborderw=8"
        )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={video_w}x{video_h}:r=30",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", str(INTRO_DURATION),
        "-vf", ",".join(parts),
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [錯誤] 片頭製作失敗：")
        print(result.stderr[-400:])
        return None
    return output_path


def cut_raw(source_video, start, end, has_audio, output_path):
    """Cut clip with background noise reduction (afftdn). Add silent audio if needed."""
    # ffmpeg expects dot notation for milliseconds, not comma (SRT format)
    start = start.replace(",", ".")
    end = end.replace(",", ".")
    duration = s_to_hms(hms_to_s(end) - hms_to_s(start))

    if has_audio:
        cmd = [
            "ffmpeg", "-y",
            "-ss", start, "-i", str(source_video),
            "-t", duration,
            "-c:v", "libx264", "-preset", "fast",
            "-af", "afftdn=nf=-25:tn=1",
            "-c:a", "aac",
            str(output_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-ss", start, "-i", str(source_video),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", duration,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac",
            str(output_path),
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [錯誤] 剪輯失敗：")
        print(result.stderr[-400:])
        return None
    return output_path


def concat_clips(intro_path, clip_path, output_path):
    """Concatenate intro + main clip into final video."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(intro_path),
        "-i", str(clip_path),
        "-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [錯誤] 合併失敗：")
        print(result.stderr[-400:])
        return None
    return output_path


def process_segment(source_video, start, end, title, idx, font_path, video_w, video_h, has_audio):
    CLIPS_DIR.mkdir(exist_ok=True)
    safe_start = start.replace(":", "-")
    output_path = CLIPS_DIR / f"clip_{idx:02d}_{safe_start}.mp4"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        intro_path = tmp / "intro.mp4"
        raw_path = tmp / "raw.mp4"

        print(f"      → 製作片頭…")
        if not create_intro(title, font_path, video_w, video_h, intro_path):
            return None

        print(f"      → 剪輯片段（降噪）…")
        if not cut_raw(source_video, start, end, has_audio, raw_path):
            return None

        print(f"      → 合併片頭 + 片段…")
        if not concat_clips(intro_path, raw_path, output_path):
            return None

    return output_path


def list_csv_files():
    return sorted(OUTPUT_DIR.glob("*_viral_segments.csv"))


def select_csv(csv_files):
    if not csv_files:
        print("output/ 中沒有找到 *_viral_segments.csv 檔案")
        print("請先執行 /run-viral-analyzer 產生分析結果")
        sys.exit(1)
    if len(csv_files) == 1:
        print(f"使用分析檔案：{csv_files[0].name}")
        return csv_files[0]
    print("找到多個分析檔案：")
    for i, f in enumerate(csv_files, 1):
        print(f"  {i}. {f.name}")
    while True:
        try:
            choice = input("請選擇要處理的檔案（輸入編號）：").strip()
        except EOFError:
            return csv_files[0]
        if choice.isdigit() and 1 <= int(choice) <= len(csv_files):
            return csv_files[int(choice) - 1]
        print("請輸入有效的編號")


def find_source_video(csv_stem):
    base = csv_stem.replace("_viral_segments", "")
    exts = [".mp4", ".mov", ".mkv", ".avi", ".webm"]

    # 1. 優先使用 output/ 裡已有的同名影片
    for ext in exts:
        p = OUTPUT_DIR / (base + ext)
        if p.exists():
            return p

    # 2. 從 upload/ 找同名影片，複製至 output/ 後使用
    for ext in exts:
        p = UPLOAD_DIR / (base + ext)
        if p.exists():
            dest = OUTPUT_DIR / p.name
            print(f"output/ 中找不到 {p.name}，從 upload/ 複製至 output/…")
            shutil.copy2(p, dest)
            return dest

    # 3. 萬用字元 fallback：upload/ 裡第一支影片，複製至 output/
    for ext in exts:
        videos = list(UPLOAD_DIR.glob(f"*{ext}"))
        if videos:
            src = videos[0]
            dest = OUTPUT_DIR / src.name
            if not dest.exists():
                print(f"output/ 中找不到對應影片，從 upload/{src.name} 複製至 output/…")
                shutil.copy2(src, dest)
            return dest

    return None


def main():
    if not shutil.which("ffmpeg"):
        print("錯誤：找不到 ffmpeg，請安裝：brew install ffmpeg")
        sys.exit(1)

    csv_files = list_csv_files()
    csv_file = select_csv(csv_files)

    source_video = find_source_video(csv_file.stem)
    if not source_video:
        print("錯誤：找不到對應的原始影片（output/ 和 upload/ 中均無影片）")
        sys.exit(1)
    print(f"原始影片：{source_video.name}")

    font_path = find_font()
    font_name = Path(font_path).name if font_path else "(系統預設)"
    print(f"使用字型：{font_name}")
    if not font_path:
        print("警告：找不到任何中文字型，字幕可能顯示方塊")

    video_w, video_h, has_audio = get_video_info(source_video)
    print(f"影片解析度：{video_w}x{video_h}，{'有' if has_audio else '無'}音訊")

    segments = []
    with open(csv_file, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            segments.append(row)

    print(f"\n開始處理 {len(segments)} 個片段（3秒片頭 + 降噪片段），儲存至 output/clips/\n")

    success = []
    for seg in segments:
        idx = int(seg["片段編號"])
        start = seg["開始時間"]
        end = seg["結束時間"]
        title = seg["建議標題"]
        print(f"[{idx:02d}] {start} → {end}  {title[:25]}{'…' if len(title)>25 else ''}")
        out = process_segment(source_video, start, end, title, idx, font_path, video_w, video_h, has_audio)
        if out:
            success.append(out)
            print(f"      ✓ {out.name}")

    print(f"\n完成！共產出 {len(success)}/{len(segments)} 個片段")
    print(f"儲存位置：{CLIPS_DIR}/")


if __name__ == "__main__":
    main()
