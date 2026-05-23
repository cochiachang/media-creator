#!/usr/bin/env python3
"""
最終混音器 - 讀取 output/clips/ 和 output/music/，
用 ffmpeg 將 v1 音樂作為背景音疊入影片，保留原始聲音，輸出至 output/final/
"""
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CLIPS_DIR = PROJECT_ROOT / "output" / "clips"
MUSIC_DIR = PROJECT_ROOT / "output" / "music"
FINAL_DIR = PROJECT_ROOT / "output" / "final"

# 原始聲音音量（1.0 = 100%），背景音樂音量（0.1 = 10%）
ORIGINAL_VOLUME = 1.5
BGM_VOLUME = 0.1


def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("錯誤：找不到 ffmpeg，請先安裝：brew install ffmpeg")
        sys.exit(1)


def list_clips():
    if not CLIPS_DIR.exists():
        return []
    return sorted(CLIPS_DIR.glob("*.mp4"))


def find_music_for_clip(clip_path):
    """
    從 clip 檔名取出 segment 編號，對應 segment_<n>_v1.mp3。
    clip_01_00-00-02.mp4 → segment 1 → segment_1_v1.mp3
    找不到對應時，回傳第一個可用的 v1.mp3。
    """
    m = re.search(r"clip_0*(\d+)", clip_path.stem)
    if m:
        n = int(m.group(1))
        candidate = MUSIC_DIR / f"segment_{n}_v1.mp3"
        if candidate.exists():
            return candidate

    # fallback：第一個 v1.mp3
    v1_files = sorted(MUSIC_DIR.glob("*_v1.mp3"))
    return v1_files[0] if v1_files else None


def mix(clip_path, music_path, out_path):
    """ffmpeg：原聲 + 背景音樂，影片串流直接 copy 不重新編碼"""
    filter_complex = (
        f"[0:a]volume={ORIGINAL_VOLUME}[orig];"
        f"[1:a]volume={BGM_VOLUME}[bgm];"
        f"[orig][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", str(clip_path),
        "-i", str(music_path),
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-500:])


def main():
    check_ffmpeg()

    clips = list_clips()
    if not clips:
        print("output/clips/ 中沒有找到 .mp4 檔案")
        print("請先執行 /run-clip-cutter 產生片段")
        sys.exit(1)

    v1_files = list(MUSIC_DIR.glob("*_v1.mp3")) if MUSIC_DIR.exists() else []
    if not v1_files:
        print("output/music/ 中沒有找到 *_v1.mp3 檔案")
        print("請先執行 /run-music-generator 產生音樂")
        sys.exit(1)

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    print(f"找到 {len(clips)} 個片段，開始混音…\n")

    for clip in clips:
        music = find_music_for_clip(clip)
        if not music:
            print(f"[{clip.name}]  ✗ 找不到對應音樂，跳過")
            continue

        out_path = FINAL_DIR / clip.name
        print(f"[{clip.name}]")
        print(f"      + {music.name}  (BGM {int(BGM_VOLUME*100)}%)")
        try:
            mix(clip, music, out_path)
            print(f"      ✓ 已儲存至 output/final/{clip.name}\n")
        except RuntimeError as e:
            print(f"      ✗ ffmpeg 失敗：{e}\n")

    print("完成！最終影片已儲存至：output/final/")


if __name__ == "__main__":
    main()
