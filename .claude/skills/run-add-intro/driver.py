#!/usr/bin/env python3
"""
片頭合併器
- 讀取 output/clips/*.mp4 與 CSV 建議標題
- 用 Remotion 生成彈跳字幕片頭
- 合併後覆寫原片段
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
REMOTION_DIR = SKILL_DIR / "intro-remotion"
OUTPUT_DIR = PROJECT_ROOT / "output"
CLIPS_DIR = OUTPUT_DIR / "clips"


# ─── 標題分行 ────────────────────────────────────────────────────────────────

def split_title_into_lines(title: str, max_per_line: int = 13) -> list:
    """將標題拆成 1–3 行，優先在標點 / 空白附近斷行。"""
    if "\n" in title:
        return [l.strip() for l in title.split("\n") if l.strip()][:3]
    if len(title) <= max_per_line:
        return [title]
    mid = len(title) // 2
    punct = set("，。！？、；： ")
    for d in range(min(mid, 6)):
        for i in (mid + d, mid - d):
            if 0 < i < len(title):
                ch = title[i]
                if ch == " ":
                    return [title[:i].strip(), title[i + 1:].strip()]
                elif ch in punct:
                    line1 = title[: i + 1].strip()
                    line2 = title[i + 1:].strip()
                    if line1 and line2:
                        return [line1, line2]
    return [title[:mid], title[mid:]]


# ─── Root.tsx 動態產生 ────────────────────────────────────────────────────────

def generate_root_tsx(lines_json: str, theme: str, video_w: int, video_h: int, font_size: int) -> str:
    return f"""// 此檔案由 driver.py 在每次渲染前自動產生，請勿手動修改。
import {{ Composition }} from "remotion";
import React from "react";
import {{ IntroVideo, calcIntroDurationFrames }} from "./IntroVideo";

const LINES: string[] = {lines_json};
const FPS = 30;
const CHAR_DELAY = 3;

const DURATION = calcIntroDurationFrames({{
  lines: LINES,
  charDelay: CHAR_DELAY,
  fps: FPS,
  holdSeconds: 1,
}});

export const RemotionRoot: React.FC = () => {{
  return (
    <Composition
      id="Intro"
      component={{IntroVideo}}
      durationInFrames={{DURATION}}
      fps={{FPS}}
      width={{{video_w}}}
      height={{{video_h}}}
      defaultProps={{{{
        lines: LINES,
        theme: "{theme}",
        charDelay: CHAR_DELAY,
        fontSize: {font_size},
      }}}}
    />
  );
}};
"""


# ─── Remotion 片頭製作 ───────────────────────────────────────────────────────

def ensure_remotion_deps():
    node_modules = REMOTION_DIR / "node_modules"
    if not node_modules.exists():
        print("      → 首次執行：安裝 Remotion 依賴（約需 1–3 分鐘）…")
        result = subprocess.run(
            ["npm", "install"],
            capture_output=True, text=True,
            cwd=str(REMOTION_DIR), timeout=300,
        )
        if result.returncode != 0:
            print("  [錯誤] npm install 失敗：")
            print(result.stderr[-600:])
            return False
    return True


def create_intro_remotion(title: str, video_w: int, video_h: int, output_path: Path) -> bool:
    lines = split_title_into_lines(title)
    lines_json = json.dumps(lines, ensure_ascii=False)
    font_size = max(48, min(96, min(video_w, video_h) // 15))

    root_path = REMOTION_DIR / "src" / "Root.tsx"
    root_path.write_text(
        generate_root_tsx(lines_json, "dark", video_w, video_h, font_size),
        encoding="utf-8",
    )

    if not ensure_remotion_deps():
        return False

    remotion_bin = REMOTION_DIR / "node_modules" / ".bin" / "remotion"
    raw_intro = output_path.parent / "intro_raw.mp4"

    result = subprocess.run(
        [str(remotion_bin), "render", "Intro", str(raw_intro.absolute()), "--overwrite"],
        capture_output=True, text=True,
        cwd=str(REMOTION_DIR), timeout=180,
    )
    if result.returncode != 0:
        print("  [錯誤] Remotion 渲染失敗：")
        print(result.stderr[-600:])
        return False

    # 加入靜音立體聲音軌（concat 需要相容音軌）
    result = subprocess.run([
        "ffmpeg", "-y",
        "-i", str(raw_intro),
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        str(output_path),
    ], capture_output=True, text=True)

    raw_intro.unlink(missing_ok=True)

    if result.returncode != 0:
        print("  [錯誤] 加入靜音音軌失敗：")
        print(result.stderr[-400:])
        return False
    return True


# ─── 合併片頭 + 片段 ──────────────────────────────────────────────────────────

def concat_clips(intro_path: Path, clip_path: Path, output_path: Path) -> bool:
    result = subprocess.run([
        "ffmpeg", "-y",
        "-i", str(intro_path),
        "-i", str(clip_path),
        "-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac",
        str(output_path),
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print("  [錯誤] 合併失敗：")
        print(result.stderr[-400:])
        return False
    return True


# ─── 影片資訊 ─────────────────────────────────────────────────────────────────

def get_video_info(video_path: Path):
    import re as _re
    result = subprocess.run(
        ["ffmpeg", "-i", str(video_path), "-hide_banner"],
        capture_output=True, text=True,
    )
    width, height = 720, 1280
    for line in result.stderr.splitlines():
        m = _re.search(r"(\d{3,5})x(\d{3,5})", line)
        if m and "Video" in line:
            width, height = int(m.group(1)), int(m.group(2))
    return width, height


# ─── CSV 工具 ─────────────────────────────────────────────────────────────────

def find_csv():
    csv_files = sorted(OUTPUT_DIR.glob("*_viral_segments.csv"))
    if not csv_files:
        print("找不到 *_viral_segments.csv，請先執行 /run-viral-analyzer")
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


def load_title_map(csv_file: Path) -> dict:
    title_map = {}
    with open(csv_file, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            title_map[int(row["片段編號"])] = row["建議標題"]
    return title_map


# ─── 主程式 ───────────────────────────────────────────────────────────────────

def main():
    for tool, hint in [
        ("ffmpeg", "brew install ffmpeg"),
        ("node",   "brew install node"),
        ("npm",    "brew install node"),
    ]:
        if not shutil.which(tool):
            print(f"錯誤：找不到 {tool}，請安裝：{hint}")
            sys.exit(1)

    csv_file = find_csv()
    title_map = load_title_map(csv_file)

    clips = sorted(CLIPS_DIR.glob("clip_*.mp4"))
    if not clips:
        print("找不到 output/clips/ 中的片段，請先執行 /run-clip-cutter")
        sys.exit(1)

    print(f"\n找到 {len(clips)} 個片段，開始生成 Remotion 片頭…\n")

    success = []
    for clip_path in clips:
        parts = clip_path.stem.split("_")
        try:
            idx = int(parts[1])
        except (IndexError, ValueError):
            print(f"  [跳過] 無法解析編號：{clip_path.name}")
            continue

        title = title_map.get(idx, f"片段 {idx}")
        video_w, video_h = get_video_info(clip_path)

        print(f"[{idx:02d}] {clip_path.name}")
        print(f"      標題：{title[:30]}{'…' if len(title) > 30 else ''}")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            intro_path = tmp / "intro.mp4"
            merged_path = tmp / "merged.mp4"

            print("      → 製作 Remotion 彈跳片頭…")
            if not create_intro_remotion(title, video_w, video_h, intro_path):
                print(f"      ✗ 片頭生成失敗，跳過")
                continue

            print("      → 合併片頭 + 片段…")
            if not concat_clips(intro_path, clip_path, merged_path):
                print(f"      ✗ 合併失敗，跳過")
                continue

            # 覆寫原片段
            shutil.copy2(merged_path, clip_path)

        success.append(clip_path)
        print(f"      ✓ {clip_path.name}\n")

    print(f"完成！共處理 {len(success)}/{len(clips)} 個片段")
    print(f"儲存位置：{CLIPS_DIR}/")


if __name__ == "__main__":
    main()
