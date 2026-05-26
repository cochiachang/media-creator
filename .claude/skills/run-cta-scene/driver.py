#!/usr/bin/env python3
"""
CTA 片尾靜態畫面生成器 v8
流程：
  1. 讀取 output/*_storyboard.json 的 cta_scene 區塊
  2. 用 ffmpeg 在 start_time 截取一張參考圖
  3. 用 ffmpeg drawtext 燒入 text_overlay 文字（白字黑邊）→ cta_scene.png
     ※ 畫面只顯示 text_overlay，不顯示 voiceover 文字
  4. 用 OpenAI TTS（tts-1-hd, nova, 1.25x）唸 voiceover → cta_scene_tts.mp3
  5. 用 ffmpeg 將 PNG + TTS MP3 合成 5 秒 H.264 影片
  6. 輸出 output/cta_scene.png + output/cta_scene_tts.mp3 + output/clips/cta_scene.mp4
"""
import json
import os
import sys
import subprocess
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("錯誤：缺少 openai 套件，請執行：pip install openai")
    sys.exit(1)

# ── 路徑設定 ─────────────────────────────────────────────────────────────────
PROJECT_ROOT  = Path(__file__).resolve().parents[3]
OUTPUT_DIR    = PROJECT_ROOT / "output"
UPLOAD_DIR    = PROJECT_ROOT / "upload"
FRAMES_DIR    = OUTPUT_DIR / "cta_scene_frames"
REF_FRAME     = FRAMES_DIR / "cta_ref.jpg"
OUTPUT_PNG    = OUTPUT_DIR / "cta_scene.png"
OUTPUT_TTS    = OUTPUT_DIR / "cta_scene_tts.mp3"
OUTPUT_CLIP   = OUTPUT_DIR / "clips" / "cta_scene.mp4"

TTS_MODEL        = "gpt-4o-mini-tts"   # 支援 instructions，可指定台灣腔
TTS_VOICE        = "nova"
TTS_SPEED        = 1.5
TTS_INSTRUCTIONS = "請用台灣腔繁體中文朗讀，語氣自然親切，像在對觀眾說話。"
CLIP_DURATION    = 5

# 字體候選（優先使用專案內建微軟正黑體，確保跨平台中文顯示）
_BUNDLED_FONT = Path(__file__).resolve().parents[2] / "微軟正黑體.ttf"
FONT_CANDIDATES = [
    str(_BUNDLED_FONT),                                              # 專案內建（跨平台首選）
    "/System/Library/Fonts/PingFang.ttc",                           # macOS
    "/System/Library/Fonts/STHeiti Medium.ttc",                     # macOS
    "/System/Library/Fonts/STHeiti Light.ttc",                      # macOS
    "/System/Library/Fonts/Supplemental/Arial Unicode MS.ttf",      # macOS
    "/Library/Fonts/Arial Unicode MS.ttf",                          # macOS
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",       # Linux Noto
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",       # Linux Noto (alt)
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",                 # Linux WQY
]


# ── 工具函數 ──────────────────────────────────────────────────────────────────
def srt_to_seconds(t: str) -> float:
    t = t.strip()
    h, m, rest = t.split(":")
    rest = rest.replace(",", ".")
    s, *ms_part = rest.split(".")
    ms = ms_part[0] if ms_part else "0"
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def select_file(files: list, label: str):
    if not files:
        return None
    if len(files) == 1:
        print(f"使用{label}：{files[0].name}")
        return files[0]
    print(f"\n找到多個{label}：")
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


def find_font() -> str:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    print("  ⚠️  找不到中文字體，ffmpeg drawtext 可能無法顯示中文")
    return ""


def ffmpeg_escape(text: str) -> str:
    """
    Escape text for ffmpeg drawtext text= value.
    ffmpeg filter parser special chars: \  '  :
    """
    text = text.replace("\\", "\\\\")   # backslash 先處理
    text = text.replace("'",  "’") # 直接換成彎引號，避免引號脫逸地獄
    text = text.replace(":",  "\\:")    # colon
    text = text.replace("%",  "%%")     # percent
    return text


def wrap_lines(text: str, max_chars: int = 14) -> list[str]:
    """依 max_chars 分行（純字元數切割）。"""
    lines = []
    while len(text) > max_chars:
        lines.append(text[:max_chars])
        text = text[max_chars:]
    if text:
        lines.append(text)
    return lines


# ── Step 1：讀取 storyboard JSON ──────────────────────────────────────────────
def load_storyboard() -> tuple[Path, dict]:
    jsons = sorted(OUTPUT_DIR.glob("*_storyboard.json"))
    if not jsons:
        print("錯誤：output/ 找不到 *_storyboard.json，請先執行 /run-viral-storyboard")
        sys.exit(1)
    path = select_file(jsons, "分鏡腳本 JSON")
    return path, json.loads(path.read_text(encoding="utf-8"))


# ── Step 2：解析 cta_scene ────────────────────────────────────────────────────
def parse_cta_scene(storyboard: dict) -> dict:
    cta = storyboard.get("cta_scene")
    if not cta:
        print("錯誤：storyboard JSON 缺少 cta_scene 區塊")
        sys.exit(1)

    start_raw = cta.get("start_time", "00:00:00,000")
    end_raw   = cta.get("end_time",   "00:00:05,000")
    start_sec = srt_to_seconds(start_raw)
    end_sec   = srt_to_seconds(end_raw)
    if end_sec <= start_sec:
        end_sec = start_sec + 5.0

    print(f"  📍 CTA 片段：{start_raw} → {end_raw}（{end_sec - start_sec:.1f} 秒）")
    print(f"  🔤 text_overlay：{cta.get('text_overlay', '')}")
    print(f"  🎙️  voiceover   ：{cta.get('voiceover', '')}")
    print(f"  📢 cta_action  ：{cta.get('cta_action', '')}")

    return {
        "start_sec":    start_sec,
        "end_sec":      end_sec,
        "text_overlay": cta.get("text_overlay", cta.get("cta_action", "")),
        "voiceover":    cta.get("voiceover", ""),
        "cta_action":   cta.get("cta_action", ""),
    }


# ── Step 3：ffmpeg 截取 start_time 單幀 ──────────────────────────────────────
def extract_start_frame(video_path: Path, start_sec: float) -> Path:
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", "2",
        str(REF_FRAME),
    ]
    print(f"  🎬 ffmpeg 截取 {start_sec:.1f}s…")
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0 or not REF_FRAME.exists():
        raise RuntimeError(result.stderr.decode(errors="replace")[-300:])
    print(f"  ✅ 參考圖：{REF_FRAME.name}（{REF_FRAME.stat().st_size // 1024} KB）")
    return REF_FRAME


# ── Step 4：ffmpeg drawtext 燒入文字 ─────────────────────────────────────────
def get_frame_width(frame: Path) -> int:
    """用 ffprobe 取得圖片寬度（px），失敗回傳 854。"""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width", "-of", "csv=p=0", str(frame)],
        capture_output=True, text=True,
    )
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 854


def burn_text_ffmpeg(frame: Path, cta: dict, out: Path) -> None:
    """
    用 ffmpeg drawtext 在截圖上燒入 text_overlay（大字，置中）。
    字型大小依最長行字數自動縮放，確保不超出畫面寬度。
    不顯示 voiceover 文字。白字 + 黑描邊。
    """
    font     = find_font()
    font_opt = f"fontfile='{font}':" if font else ""

    text_overlay = cta.get("text_overlay", "").strip()

    filters = []

    # ── 大字：text_overlay ────────────────────────────────────────────────────
    if text_overlay:
        # 每行最多 6 字，避免初始斷行過長
        big_lines = wrap_lines(text_overlay, max_chars=6)
        max_line_len = max(len(l) for l in big_lines)

        # 動態計算字型大小：讓最長行佔畫面寬的 80%
        # 中文字寬 ≈ font_size（方塊字），加上描邊 borderw=5 兩側共 10px
        frame_w  = get_frame_width(frame)
        max_fs   = frame_w // 7                            # 上限：舊行為
        auto_fs  = int(frame_w * 0.80 / max(max_line_len, 1))
        font_size = min(max_fs, auto_fs)
        line_h   = font_size + 14

        n = len(big_lines)
        for i, line in enumerate(big_lines):
            escaped = ffmpeg_escape(line)
            y_expr  = f"h*0.65 - ({n}/2.0 - {i})*{line_h}"
            filters.append(
                f"drawtext={font_opt}"
                f"text='{escaped}':"
                f"fontsize={font_size}:"
                f"fontcolor=white:"
                f"borderw=5:"
                f"bordercolor=black@0.9:"
                f"x=(w-text_w)/2:"
                f"y={y_expr}"
            )
        print(f"  📝 text_overlay：{'｜'.join(big_lines)}（{font_size}px, {frame_w}px寬）")

    if not filters:
        # 沒有文字，直接複製圖片
        import shutil
        shutil.copy2(frame, out)
        print("  ⚠️  無文字，直接複製截圖")
        return

    vf = ",".join(filters)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(frame),
        "-vf", vf,
        "-frames:v", "1",
        str(out),
    ]
    print(f"  🖊️  ffmpeg drawtext 燒字…")
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and out.exists():
        print(f"  ✅ 燒字完成 → {out.name}（{out.stat().st_size // 1024} KB）")
    else:
        err = result.stderr.decode(errors="replace")
        print(f"  ❌ drawtext 失敗：{err[-400:]}")
        raise RuntimeError("ffmpeg drawtext 失敗")


# ── Step 5：OpenAI TTS 生成旁白音訊（唸 voiceover，不顯示在畫面）────────────
def generate_tts(client: OpenAI, voiceover: str, out: Path) -> bool:
    text = voiceover.strip()
    if not text:
        print("  ⚠️  voiceover 為空，跳過 TTS")
        return False
    if text[-1] not in "！!？?。.，,":
        text += "！"
    print(f"  🎙️  TTS：『{text}』（{TTS_MODEL}, {TTS_VOICE}, {TTS_SPEED}x, 台灣腔）")
    try:
        resp = client.audio.speech.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=text,
            instructions=TTS_INSTRUCTIONS,
            response_format="mp3",
            speed=TTS_SPEED,
        )
        out.write_bytes(resp.content)
        print(f"  ✅ TTS → {out.name}（{out.stat().st_size // 1024} KB）")
        return True
    except Exception as e:
        print(f"  ❌ TTS 失敗：{e}")
        return False


# ── Step 6：PNG + TTS MP3 → 5 秒影片 ────────────────────────────────────────
def make_cta_clip(png: Path, mp3: Path | None, out: Path, duration: int = 5) -> bool:
    out.parent.mkdir(parents=True, exist_ok=True)
    if mp3 and mp3.exists():
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", "30", "-i", str(png),
            "-i", str(mp3),
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", str(duration), "-shortest",
            str(out),
        ]
        print(f"  🎬 ffmpeg：靜態圖 + TTS → {duration}s…")
    else:
        # 加 anullsrc 靜音軌，確保 concat filter 能找到音訊流
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", "30", "-i", str(png),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-t", str(duration), "-shortest",
            str(out),
        ]
        print(f"  🎬 ffmpeg：靜態圖 + 靜音軌 → {duration}s…")

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and out.exists():
        print(f"  ✅ 影片 → {out.name}（{out.stat().st_size // 1024} KB）")
        return True
    print(f"  ❌ 合成失敗：{result.stderr.decode(errors='replace')[-300:]}")
    return False


# ── 主流程 ────────────────────────────────────────────────────────────────────
def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("錯誤：請設定 OPENAI_API_KEY")
        sys.exit(1)
    client = OpenAI(api_key=api_key)

    # Step 1
    print("\n📄 Step 1 — 讀取分鏡 JSON…")
    sb_path, storyboard = load_storyboard()
    print(f"  ✅ {sb_path.name}")

    # Step 2
    print("\n🎯 Step 2 — 解析 cta_scene…")
    cta = parse_cta_scene(storyboard)

    # Step 3
    print("\n🎬 Step 3 — 選來源影片…")
    videos = sorted(UPLOAD_DIR.glob("*.mp4"))
    if not videos:
        print("錯誤：upload/ 找不到 .mp4，請先放入影片")
        sys.exit(1)
    video = select_file(videos, "來源影片")
    print(f"  ✅ {video.name}")

    # Step 4
    print("\n🖼️  Step 4 — ffmpeg 截取 start_time 參考圖…")
    try:
        ref = extract_start_frame(video, cta["start_sec"])
    except RuntimeError as e:
        print(f"錯誤：{e}")
        sys.exit(1)

    # Step 5
    print("\n✍️  Step 5 — ffmpeg drawtext 燒入 CTA 文字…")
    try:
        burn_text_ffmpeg(ref, cta, OUTPUT_PNG)
    except RuntimeError as e:
        print(f"  ⚠️  燒字失敗（{e}），直接使用截圖")
        import shutil
        shutil.copy2(ref, OUTPUT_PNG)

    # Step 6 — TTS 唸 voiceover（不顯示在畫面，只作為音軌）
    print(f"\n🎙️  Step 6 — TTS 旁白（{TTS_VOICE}, {TTS_SPEED}x）…")
    tts_ok = generate_tts(client, cta["voiceover"], OUTPUT_TTS)

    # Step 7 — 合成片尾影片
    print(f"\n🎞️  Step 7 — 合成 {CLIP_DURATION}s 片尾影片…")
    clip_ok = make_cta_clip(
        png=OUTPUT_PNG,
        mp3=OUTPUT_TTS if tts_ok else None,
        out=OUTPUT_CLIP,
        duration=CLIP_DURATION,
    )

    # 完成摘要
    size_kb = OUTPUT_PNG.stat().st_size // 1024
    print(f"\n{'='*55}")
    print(f"✅  完成！")
    print(f"   片尾靜態圖：output/cta_scene.png（{size_kb} KB）")
    if tts_ok:
        print(f"   CTA 旁白  ：output/cta_scene_tts.mp3（{OUTPUT_TTS.stat().st_size // 1024} KB）")
    if clip_ok:
        clip_label = "含 TTS" if tts_ok else "靜音"
        print(f"   片尾影片  ：output/clips/cta_scene.mp4（{OUTPUT_CLIP.stat().st_size // 1024} KB，{CLIP_DURATION}s，{clip_label}）")
    print(f"   參考截圖  ：output/cta_scene_frames/cta_ref.jpg")
    print(f"   CTA 行動  ：{cta['cta_action']}")
    print(f"   畫面文字  ：{cta['text_overlay']}")
    print(f"   旁白音訊  ：{cta['voiceover']}")
    print(f"{'='*55}")
    print(f"\n💡 下一步：執行 /run-final-mixer 合併所有場景（含 clips/cta_scene.mp4）")


if __name__ == "__main__":
    main()
