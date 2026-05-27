#!/usr/bin/env python3
"""
精華短片剪輯器
- 優先讀取 *_storyboard.json 的 storyboard 陣列剪輯各 scene
  （end_time 自動延長 0.3 秒，最後 0.3 秒做音量淡出）
- 若無 storyboard，fallback 讀取 *_viral_segments.csv
- 萃取對應時間段的 SRT，燒錄字幕
- 輸出至 output/clips/
"""
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FADE_DURATION = 0.5   # 末尾延長秒數 & 音量淡出時長

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
UPLOAD_DIR = PROJECT_ROOT / "upload"
CLIPS_DIR = OUTPUT_DIR / "clips"


# ─── SRT 萃取與字幕燒錄 ──────────────────────────────────────────────────────

def extract_segment_srt(full_srt_path: Path, start_s: float, end_s: float) -> str:
    """
    從完整 SRT 萃取 [start_s, end_s+0.5] 範圍內的字幕，時移為從 0 開始。
    回傳 SRT 格式字串；無字幕則回傳空字串。
    """
    import re as _re

    def _ts_to_s(ts: str) -> float:
        ts = ts.replace(",", ".")
        h, m, s = ts.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    def _s_to_ts(s: float) -> str:
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = s % 60
        ms = round((sec % 1) * 1000)
        return f"{h:02d}:{m:02d}:{int(sec):02d},{ms:03d}"

    content = full_srt_path.read_text(encoding="utf-8-sig")
    blocks = _re.split(r"\n{2,}", content.strip())
    out, new_idx = [], 1

    for block in blocks:
        lines = block.strip().splitlines()
        ts_idx = next(
            (i for i, l in enumerate(lines)
             if _re.match(r"\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3}", l)),
            None,
        )
        if ts_idx is None:
            continue
        m = _re.match(
            r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})",
            lines[ts_idx],
        )
        if not m:
            continue

        sub_s = _ts_to_s(m.group(1))
        sub_e = _ts_to_s(m.group(2))

        if sub_e <= start_s or sub_s >= end_s + FADE_DURATION:
            continue

        new_s = max(0.0, sub_s - start_s)
        new_e = min(end_s - start_s + FADE_DURATION, sub_e - start_s)
        text = "\n".join(lines[ts_idx + 1:]).strip()
        if not text:
            continue

        out.append(f"{new_idx}\n{_s_to_ts(new_s)} --> {_s_to_ts(new_e)}\n{text}")
        new_idx += 1

    return "\n\n".join(out)


def burn_subtitle(video_path: Path, srt_path: Path, output_path: Path) -> bool:
    """
    將時移後的 SRT 字幕燒錄進影片。
    SRT 和字型複製至無特殊字元的暫存目錄，避免路徑轉義問題。
    失敗時回傳 False。
    """
    with tempfile.TemporaryDirectory() as burn_tmp:
        burn_p = Path(burn_tmp)
        tmp_srt = burn_p / "segment.srt"
        shutil.copy2(srt_path, tmp_srt)

        font_src = SKILL_DIR / "微軟正黑體.ttf"
        if font_src.exists():
            shutil.copy2(font_src, burn_p / "微軟正黑體.ttf")

        srt_esc = str(tmp_srt).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        dir_esc = str(burn_p).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

        vf = (
            f"subtitles='{srt_esc}'"
            f":fontsdir='{dir_esc}'"
            f":force_style='FontName=Microsoft JhengHei"
            f",FontSize=16,PrimaryColour=&HFFFFFF"
            f",OutlineColour=&H000000,Outline=2"
            f",Alignment=2,MarginV=30'"
        )

        result = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "copy",
            str(output_path),
        ], capture_output=True, text=True)

        if result.returncode != 0:
            print("  [警告] 字幕燒錄失敗，跳過字幕：")
            print(result.stderr[-400:])
            return False
    return True


def find_srt(source_video: Path) -> Path | None:
    """尋找對應原始影片的 SRT 字幕檔。"""
    candidate = OUTPUT_DIR / (source_video.stem + ".srt")
    if candidate.exists():
        return candidate
    srts = sorted(OUTPUT_DIR.glob("*.srt"))
    return srts[0] if srts else None


# ─── 影片資訊 ─────────────────────────────────────────────────────────────────

def get_video_info(video_path):
    import re as _re
    result = subprocess.run(
        ["ffmpeg", "-i", str(video_path), "-hide_banner"],
        capture_output=True, text=True,
    )
    width, height, has_audio = 720, 1280, False
    for line in result.stderr.splitlines():
        m = _re.search(r"(\d{3,5})x(\d{3,5})", line)
        if m and "Video" in line:
            width, height = int(m.group(1)), int(m.group(2))
        if "Audio" in line:
            has_audio = True
    return width, height, has_audio


# ─── 時間工具 ─────────────────────────────────────────────────────────────────

def hms_to_s(hms):
    hms = hms.replace(",", ".")
    parts = hms.split(":")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


# ─── 剪輯片段 ─────────────────────────────────────────────────────────────────

def cut_raw(source_video, start, end, has_audio, output_path):
    """剪輯指定時間段（含降噪），末尾延長 FADE_DURATION 秒並做音量淡出。"""
    start = start.replace(",", ".")
    end = end.replace(",", ".")
    raw_s = hms_to_s(end) - hms_to_s(start)
    total_s = raw_s + FADE_DURATION
    fade_st = total_s - FADE_DURATION
    dur_str = f"{total_s:.3f}"
    fd = f"{FADE_DURATION:.3f}"

    if has_audio:
        cmd = [
            "ffmpeg", "-y",
            "-ss", start, "-i", str(source_video),
            "-t", dur_str,
            "-c:v", "libx264", "-preset", "fast",
            "-af", f"afftdn=nf=-25:tn=1,afade=t=out:st={fade_st:.3f}:d={fd}",
            "-c:a", "aac",
            str(output_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-ss", start, "-i", str(source_video),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", dur_str,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast",
            "-af", f"afade=t=out:st={fade_st:.3f}:d={fd}",
            "-c:a", "aac",
            str(output_path),
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("  [錯誤] 剪輯失敗：")
        print(result.stderr[-400:])
        return False
    return True


# ─── 靜態字幕 SRT 生成 ───────────────────────────────────────────────────────

def make_static_srt(text: str, duration_s: float) -> str:
    """
    產生一條覆蓋整段片段的 SRT：文字從 0 秒顯示到片段結束。
    """
    def _s_to_ts(s: float) -> str:
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = s % 60
        ms = round((sec % 1) * 1000)
        return f"{h:02d}:{m:02d}:{int(sec):02d},{ms:03d}"

    return f"1\n{_s_to_ts(0.0)} --> {_s_to_ts(duration_s)}\n{text}"


# ─── 單一片段完整流程 ─────────────────────────────────────────────────────────

def process_segment(source_video, srt_path, start, end, idx, has_audio, prefix="scene",
                    static_subtitle: str | None = None):
    CLIPS_DIR.mkdir(exist_ok=True)
    output_path = CLIPS_DIR / f"{prefix}_{idx:02d}.mp4"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        raw_path = tmp / "raw.mp4"

        # ① 決定字幕來源
        #    - static_subtitle 有值：用 voiceover 文字靜態掛滿整段
        #    - 否則：從原始 SRT 萃取對應時間段
        seg_srt_path = None
        start_s = hms_to_s(start.replace(",", "."))
        end_s = hms_to_s(end.replace(",", "."))
        duration_s = end_s - start_s + FADE_DURATION

        if static_subtitle and static_subtitle.strip():
            srt_content = make_static_srt(static_subtitle.strip(), duration_s)
            seg_srt_path = tmp / "segment.srt"
            seg_srt_path.write_text(srt_content, encoding="utf-8")
        elif srt_path and srt_path.exists():
            srt_content = extract_segment_srt(srt_path, start_s, end_s)
            if srt_content.strip():
                seg_srt_path = tmp / "segment.srt"
                seg_srt_path.write_text(srt_content, encoding="utf-8")

        has_sub = seg_srt_path is not None
        print(f"      → 剪輯片段（降噪{'＋字幕' if has_sub else ''}）…")
        if not cut_raw(source_video, start, end, has_audio, raw_path):
            return None

        # ② 字幕燒錄或直接輸出
        if has_sub:
            if not burn_subtitle(raw_path, seg_srt_path, output_path):
                shutil.copy2(raw_path, output_path)   # fallback 無字幕
        else:
            shutil.copy2(raw_path, output_path)

    return output_path


# ─── Storyboard JSON 讀取 ────────────────────────────────────────────────────

def load_storyboard_segments() -> tuple[list[dict], Path | None]:
    """
    讀取 output/*_storyboard.json 的 storyboard 陣列。
    回傳 (segments, storyboard_path)；找不到則回傳 ([], None)。
    每個 segment dict：
      idx, start, end, title, label, transition_out
    """
    jsons = sorted(OUTPUT_DIR.glob("*_storyboard.json"))
    if not jsons:
        return [], None

    sb_path = jsons[0]
    if len(jsons) > 1:
        print("找到多個 storyboard：")
        for i, j in enumerate(jsons, 1):
            print(f"  {i}. {j.name}")
        try:
            idx = int(input(f"請選擇（1~{len(jsons)}）：") or "1") - 1
            sb_path = jsons[max(0, idx)]
        except (ValueError, IndexError):
            pass

    sb = json.loads(sb_path.read_text(encoding="utf-8"))
    segments = []
    for scene in sb.get("storyboard", []):
        if scene.get("label", "").lower() == "cta":
            continue   # CTA 由 cta_scene 另外處理，不在此剪輯
        segments.append({
            "idx":            scene.get("scene_number", 0),
            "start":          scene.get("start_time", ""),
            "end":            scene.get("end_time", ""),
            "title":          scene.get("text_overlay") or scene.get("visual", "")[:30],
            "label":          scene.get("label", ""),
            "transition_out": scene.get("transition_out", "cut"),
            "voiceover":      scene.get("voiceover", ""),
        })
    return segments, sb_path


# ─── CSV 選擇 ─────────────────────────────────────────────────────────────────

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


# ─── 原始影片搜尋 ─────────────────────────────────────────────────────────────

def find_source_video(csv_stem):
    base = csv_stem.replace("_viral_segments", "")
    exts = [".mp4", ".mov", ".mkv", ".avi", ".webm"]

    for ext in exts:
        p = OUTPUT_DIR / (base + ext)
        if p.exists():
            return p

    for ext in exts:
        p = UPLOAD_DIR / (base + ext)
        if p.exists():
            dest = OUTPUT_DIR / p.name
            print(f"output/ 中找不到 {p.name}，從 upload/ 複製至 output/…")
            shutil.copy2(p, dest)
            return dest

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


# ─── 主程式 ───────────────────────────────────────────────────────────────────

def main():
    if not shutil.which("ffmpeg"):
        print("錯誤：找不到 ffmpeg，請安裝：brew install ffmpeg")
        sys.exit(1)

    # ── 決定片段來源：優先 storyboard JSON，fallback CSV ──────────────────────
    sb_segments, sb_path = load_storyboard_segments()

    if sb_segments:
        print(f"📋 讀取 storyboard：{sb_path.name}（{len(sb_segments)} 個 scene）")
        # 從 storyboard 推斷原始影片
        stem = sb_path.stem.replace("_storyboard", "")
        source_video = find_source_video(stem)
        use_storyboard = True
    else:
        print("⚠️  找不到 storyboard JSON，改用 CSV 模式")
        csv_files = list_csv_files()
        csv_file = select_csv(csv_files)
        source_video = find_source_video(csv_file.stem)
        use_storyboard = False

    if not source_video:
        print("錯誤：找不到對應的原始影片（output/ 和 upload/ 中均無影片）")
        sys.exit(1)
    print(f"🎥 原始影片：{source_video.name}")

    srt_path = find_srt(source_video)
    print(f"📝 字幕檔：{srt_path.name}" if srt_path else "⚠️  未找到字幕檔，跳過字幕燒錄")

    video_w, video_h, has_audio = get_video_info(source_video)
    print(f"📐 解析度：{video_w}x{video_h}，{'有' if has_audio else '無'}音訊")
    print(f"⏱️  末尾延長 {FADE_DURATION}s + 音量淡出 {FADE_DURATION}s\n")

    # ── 組合 segments ─────────────────────────────────────────────────────────
    if use_storyboard:
        segments = sb_segments
        prefix = "scene"
    else:
        segments = []
        with open(csv_file, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                segments.append({
                    "idx":   int(row["片段編號"]),
                    "start": row["開始時間"],
                    "end":   row["結束時間"],
                    "title": row["建議標題"],
                    "label": "",
                    "transition_out": "cut",
                })
        prefix = "clip"

    print(f"開始剪輯 {len(segments)} 個片段，儲存至 output/clips/\n")

    success = []
    for seg in segments:
        idx   = seg["idx"]
        start = seg["start"]
        end   = seg["end"]
        title = seg["title"]
        label = f"[{seg['label']}] " if seg.get("label") else ""
        trans = seg.get("transition_out", "cut")
        print(f"[{idx:02d}] {label}{start} → {end}  {title[:20]}{'…' if len(title) > 20 else ''}  (→{trans})")
        voiceover = seg.get("voiceover", "") if use_storyboard else None
        out = process_segment(
            source_video, srt_path, start, end,
            idx, has_audio, prefix=prefix,
            static_subtitle=voiceover,
        )
        if out:
            success.append(out)
            print(f"      ✓ {out.name}")

    print(f"\n✅ 完成！共產出 {len(success)}/{len(segments)} 個片段")
    print(f"   儲存位置：{CLIPS_DIR}/")
    if use_storyboard:
        print("   下一步：執行 /run-storyboard-assembler 串接完整影片")
    else:
        print("   下一步：執行 /run-add-intro 加上片頭")


if __name__ == "__main__":
    main()
