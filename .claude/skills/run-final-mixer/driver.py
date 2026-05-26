#!/usr/bin/env python3
"""
最終混音器 - 從 scene_00 開始，依數字順序合併 output/clips/ 所有影片，
再搭配 output/music/ 的 v1 音樂混音，輸出至 output/final/
"""
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CLIPS_DIR = PROJECT_ROOT / "output" / "clips"
MUSIC_DIR = PROJECT_ROOT / "output" / "music"
FINAL_DIR = PROJECT_ROOT / "output" / "final"
CTA_CLIP  = CLIPS_DIR / "cta_scene.mp4"

# 原始聲音音量（1.0 = 100%），背景音樂音量（0.2 = 20%）
ORIGINAL_VOLUME = 1.5
BGM_VOLUME = 0.2

MERGED_NAME = "merged_scenes.mp4"


def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("錯誤：找不到 ffmpeg，請先安裝：brew install ffmpeg")
        sys.exit(1)


def list_scene_clips():
    """收集 output/clips/scene_*.mp4，依數字從小到大排序（從 scene_00 開始）"""
    if not CLIPS_DIR.exists():
        return []
    clips = []
    for f in CLIPS_DIR.glob("scene_*.mp4"):
        m = re.search(r"scene_(\d+)", f.stem)
        if m:
            clips.append((int(m.group(1)), f))
    clips.sort(key=lambda x: x[0])
    return [f for _, f in clips]


def concat_clips(clips, out_path):
    """用 ffmpeg filter_complex concat 合併影片（重新編碼，正確處理時間戳）"""
    inputs = []
    for clip in clips:
        inputs += ["-i", str(clip)]

    n = len(clips)
    # 每個輸入的 [v][a] 串接後送進 concat filter
    stream_labels = "".join(f"[{i}:v][{i}:a]" for i in range(n))
    filter_complex = f"{stream_labels}concat=n={n}:v=1:a=1[v][a]"

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-800:])


def find_music():
    """取得第一個 v1 音樂（依檔名排序）"""
    if not MUSIC_DIR.exists():
        return None
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
        raise RuntimeError(result.stderr[-800:])


def embed_cover(video_path: Path) -> None:
    """擷取第1秒的幀作為封面縮圖，嵌入 MP4 metadata，讓 Finder / 播放器顯示預覽畫面。"""
    cover_path = video_path.with_suffix(".cover.jpg")
    tmp_path   = video_path.with_suffix(".tmp.mp4")

    # Step A：擷取第 1 秒幀
    extract_cmd = [
        "ffmpeg", "-y",
        "-ss", "1",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(cover_path),
    ]
    r = subprocess.run(extract_cmd, capture_output=True, text=True)
    if r.returncode != 0 or not cover_path.exists():
        print("  （跳過封面嵌入：無法擷取第1秒幀）")
        return

    # Step B：重新封裝，嵌入封面
    mux_cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(cover_path),
        "-map", "0",
        "-map", "1",
        "-c", "copy",
        "-c:v:1", "mjpeg",
        "-disposition:v:1", "attached_pic",
        str(tmp_path),
    ]
    r = subprocess.run(mux_cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  （跳過封面嵌入：{r.stderr[-300:]}）")
        cover_path.unlink(missing_ok=True)
        return

    # 替換原檔
    video_path.unlink()
    tmp_path.rename(video_path)
    cover_path.unlink(missing_ok=True)
    print("  ✓ 封面縮圖已嵌入（取第 1 秒幀）")


def main():
    check_ffmpeg()

    # ── Step 1：收集 scene 片段 ──────────────────────────────────────────
    clips = list_scene_clips()
    if not clips:
        print("output/clips/ 中沒有找到 scene_*.mp4 檔案")
        print("請先確認 output/clips/ 已有 scene_00.mp4、scene_01.mp4 等檔案")
        sys.exit(1)

    print(f"找到 {len(clips)} 個場景片段（從 scene_00 開始，依數字排序）：")
    for c in clips:
        print(f"  {c.name}")

    # ── 自動附加 CTA 片尾 ────────────────────────────────────────────────
    if CTA_CLIP.exists():
        clips.append(CTA_CLIP)
        print(f"  {CTA_CLIP.name}  ← CTA 片尾（自動附加）")
    else:
        print(f"  （未找到 {CTA_CLIP.name}，跳過 CTA 片尾）")
    print()

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    merged_path = FINAL_DIR / MERGED_NAME

    # ── Step 2：合併所有片段（scene + CTA）──────────────────────────────
    print(f"Step 1／2  合併 {len(clips)} 個片段 → {MERGED_NAME} …")
    try:
        concat_clips(clips, merged_path)
        print(f"      ✓ 合併完成：output/final/{MERGED_NAME}\n")
    except RuntimeError as e:
        print(f"      ✗ 合併失敗：{e}")
        sys.exit(1)

    # ── Step 3：疊入 BGM ─────────────────────────────────────────────────
    music = find_music()
    if not music:
        print("output/music/ 中沒有找到 *_v1.mp3，跳過混音步驟。")
        print(f"最終影片（無 BGM）：output/final/{MERGED_NAME}")
        print("嵌入封面縮圖 …")
        embed_cover(merged_path)
        return

    final_name = "merged_scenes_final.mp4"
    final_path = FINAL_DIR / final_name

    print(f"Step 2／2  混音：{MERGED_NAME} + {music.name}  (BGM {int(BGM_VOLUME * 100)}%)")
    try:
        mix(merged_path, music, final_path)
        print(f"      ✓ 完成！最終影片：output/final/{final_name}")
    except RuntimeError as e:
        print(f"      ✗ 混音失敗：{e}")
        sys.exit(1)

    # ── Step 4：嵌入封面縮圖（取第 1 秒幀）────────────────────────────────
    print("Step 3／3  嵌入封面縮圖 …")
    embed_cover(final_path)


if __name__ == "__main__":
    main()
