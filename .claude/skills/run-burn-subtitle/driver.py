#!/usr/bin/env python3
"""
字幕燒錄器 - 將 upload/ 的影片燒入 output/ 的 SRT 字幕，輸出至 output/
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = PROJECT_ROOT / "upload"
OUTPUT_DIR = PROJECT_ROOT / "output"
FONT_DIR = PROJECT_ROOT / ".claude" / "skills" / "run-clip-cutter"

FONT_SIZE = 16
MARGIN_V = 30


def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        print("錯誤：找不到 ffmpeg，請安裝：brew install ffmpeg 或 choco install ffmpeg")
        sys.exit(1)


def find_font():
    local_font = FONT_DIR / "微軟正黑體.ttf"
    if local_font.exists():
        return local_font
    return None


def escape_filter_path(path: Path) -> str:
    """Escape a path for use inside an ffmpeg filter value (Windows-safe)."""
    return str(path).replace("\\", "/").replace(":", "\\:")


def list_videos():
    exts = [".mp4", ".mov", ".mkv", ".avi", ".webm"]
    videos = []
    for ext in exts:
        videos.extend(UPLOAD_DIR.glob(f"*{ext}"))
    return sorted(videos)


def list_srts():
    return sorted(OUTPUT_DIR.glob("*.srt"))


def select_file(files, label):
    if len(files) == 1:
        print(f"使用{label}：{files[0].name}")
        return files[0]
    print(f"找到多個{label}：")
    for i, f in enumerate(files, 1):
        print(f"  {i}. {f.name}")
    while True:
        try:
            choice = input(f"請選擇{label}（輸入編號）：").strip()
        except EOFError:
            return files[0]
        if choice.isdigit() and 1 <= int(choice) <= len(files):
            return files[int(choice) - 1]
        print("請輸入有效的編號")


def find_matching_srt(video_path: Path, srts: list) -> Path | None:
    for srt in srts:
        if srt.stem == video_path.stem:
            return srt
    return None


def has_audio_stream(video_path: Path) -> bool:
    result = subprocess.run(
        ["ffmpeg", "-i", str(video_path), "-hide_banner"],
        capture_output=True, text=True,
    )
    return "Audio:" in result.stderr


def burn_subtitles(video_path: Path, srt_path: Path, font_path: Path | None, out_path: Path):
    """Burn SRT into video using ffmpeg subtitles filter with libass."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_srt = Path(tmpdir) / "subtitle.srt"
        shutil.copy2(srt_path, tmp_srt)

        srt_escaped = escape_filter_path(tmp_srt)
        force_style = f"FontSize={FONT_SIZE},Alignment=2,MarginV={MARGIN_V},Outline=2,OutlineColour=&H000000,PrimaryColour=&Hffffff"

        if font_path:
            fontsdir_escaped = escape_filter_path(font_path.parent)
            vf = (
                f"subtitles='{srt_escaped}'"
                f":fontsdir='{fontsdir_escaped}'"
                f":force_style='FontName=Microsoft JhengHei,{force_style}'"
            )
        else:
            vf = f"subtitles='{srt_escaped}':force_style='{force_style}'"

        audio_codec = "copy" if has_audio_stream(video_path) else "an"
        audio_args = ["-c:a", "copy"] if audio_codec == "copy" else ["-an"]

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast",
            *audio_args,
            str(out_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-1000:])


def main():
    check_ffmpeg()

    videos = list_videos()
    if not videos:
        print("錯誤：upload/ 中找不到影片檔案（mp4/mov/mkv/avi/webm）")
        sys.exit(1)

    srts = list_srts()
    if not srts:
        print("錯誤：output/ 中找不到 .srt 字幕檔案")
        print("請先執行 /run-transcribe 產生字幕")
        sys.exit(1)

    video = select_file(videos, "影片")

    matched_srt = find_matching_srt(video, srts)
    if matched_srt:
        print(f"自動配對字幕：{matched_srt.name}")
        srt = matched_srt
    else:
        srt = select_file(srts, "字幕檔案")

    font_path = find_font()
    font_name = font_path.name if font_path else "(系統預設)"
    print(f"使用字型：{font_name}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{video.stem}.mp4"

    print(f"\n開始燒錄字幕…")
    print(f"  影片：{video.name}")
    print(f"  字幕：{srt.name}")
    print(f"  輸出：output/{out_path.name}")

    try:
        burn_subtitles(video, srt, font_path, out_path)
        print(f"\n✓ 完成！已儲存至 output/{out_path.name}")
    except RuntimeError as e:
        print(f"\n✗ ffmpeg 失敗：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
