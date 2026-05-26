#!/usr/bin/env python3
"""
短影音分鏡設計師
呼叫 GPT-5.5（gpt-5.5-2026-04-23）根據爆紅 CSV、SRT、方法論，
設計 30-60 秒短影音完整分鏡腳本，含前3秒勾子、截圖、JSON 輸出。
"""
import csv
import json
import os
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    print("錯誤：缺少 openai 套件，請執行：pip install openai")
    sys.exit(1)

# ── 路徑設定 ─────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR   = PROJECT_ROOT / "output"
UPLOAD_DIR   = PROJECT_ROOT / "upload"
SHOTS_DIR    = OUTPUT_DIR / "storyboard_screenshots"
METHODOLOGY  = PROJECT_ROOT / "短影音爆紅入門全攻略.md"
MODEL        = "gpt-5.5-2026-04-23"


# ── 工具函數 ──────────────────────────────────────────────────────────────────
def srt_to_seconds(t: str) -> float:
    """HH:MM:SS,mmm or HH:MM:SS.mmm → float seconds"""
    h, m, rest = t.split(":")
    rest = rest.replace(",", ".")
    parts = rest.split(".")
    s = parts[0]
    ms = parts[1] if len(parts) > 1 else "0"
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def select_file(files: list, label: str):
    if not files:
        return None
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


def extract_screenshots_range(video: Path, start: str, end: str, prefix: str) -> list[str]:
    """對時間範圍做逐秒截圖，回傳相對路徑列表"""
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    start_sec = srt_to_seconds(start)
    duration  = srt_to_seconds(end) - start_sec
    pattern   = str(SHOTS_DIR / f"{prefix}_%02d.jpg")

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start_sec:.3f}",
        "-i", str(video),
        "-t", f"{duration:.3f}",
        "-vf", "fps=1",
        "-q:v", "2",
        pattern,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"  ⚠️  截圖失敗：{result.stderr.decode(errors='replace')[:300]}")
        return []

    shots = sorted(SHOTS_DIR.glob(f"{prefix}_*.jpg"))
    return [str(s.relative_to(PROJECT_ROOT)) for s in shots]


def extract_single_shot(video: Path, time_str: str, filename: str) -> str | None:
    """擷取單一幀截圖，回傳相對路徑"""
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    out = SHOTS_DIR / filename
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{srt_to_seconds(time_str):.3f}",
        "-i", str(video),
        "-frames:v", "1",
        "-q:v", "2",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and out.exists():
        return str(out.relative_to(PROJECT_ROOT))
    return None


def extract_json(text: str) -> dict:
    """從 GPT 回應中提取 JSON（處理 markdown code block 等情況）"""
    # 嘗試直接 parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 嘗試從 ```json ... ``` 提取
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 嘗試找第一個 { ... } 區塊
    m = re.search(r"(\{.*\})", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"無法解析 GPT 回應為 JSON：\n{text[:500]}")


def parse_srt(srt_content: str) -> list[dict]:
    """
    解析 SRT 為結構化列表，每條：
      {"idx": 1, "start": "00:00:05,000", "end": "00:00:12,000", "text": "..."}
    idx 從 1 開始，與 SRT 序號對應。
    """
    entries = []
    blocks = re.split(r"\n\s*\n", srt_content.strip())
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue
        time_line = lines[1].strip()
        m = re.match(r"([\d:,]+)\s*-->\s*([\d:,]+)", time_line)
        if not m:
            continue
        text = " ".join(l.strip() for l in lines[2:] if l.strip())
        entries.append({"idx": idx, "start": m.group(1), "end": m.group(2), "text": text})
    return entries


def build_srt_index_table(entries: list[dict]) -> str:
    """
    把 SRT 條目轉成給 AI 看的編號列表，含每條秒數：
    [1]  0.5s  00:00:00,000→00:00:05,000  好
    [2]  7.0s  00:00:05,000→00:00:12,000  我要去哥斯大黎加...
    ...
    """
    lines = []
    for e in entries:
        dur = srt_to_seconds(e["end"]) - srt_to_seconds(e["start"])
        lines.append(f"[{e['idx']}] {dur:4.1f}s  {e['start']}→{e['end']}  {e['text']}")
    return "\n".join(lines)


def resolve_srt_time(entries: list[dict], idx: int, use_end: bool = False) -> str:
    """根據 SRT 索引查出真實時間戳"""
    idx = max(1, min(idx, len(entries)))
    e = entries[idx - 1]
    return e["end"] if use_end else e["start"]


def resolve_storyboard_times(raw: dict, srt_entries: list[dict]) -> dict:
    """
    把 GPT 回傳的 srt_start / srt_end 索引
    替換成真實的 start_time / end_time，
    並計算 duration_seconds。
    """
    def fix(obj: dict) -> dict:
        si = obj.get("srt_start")
        ei = obj.get("srt_end")
        if si is not None and ei is not None:
            start_t = resolve_srt_time(srt_entries, int(si), use_end=False)
            end_t   = resolve_srt_time(srt_entries, int(ei), use_end=True)
            obj["start_time"] = start_t
            obj["end_time"]   = end_t
            obj["duration_seconds"] = max(1, round(
                srt_to_seconds(end_t) - srt_to_seconds(start_t)
            ))
        return obj

    if "hook" in raw:
        raw["hook"] = fix(raw["hook"])
    raw["storyboard"] = [fix(s) for s in raw.get("storyboard", [])]
    if "cta_scene" in raw:
        raw["cta_scene"] = fix(raw["cta_scene"])
    return raw


def design_storyboard(
    client: OpenAI,
    srt_content: str,
    csv_content: str,
    methodology: str,
    cta: str,
) -> dict:
    """呼叫 GPT-5.5 設計完整分鏡腳本"""

    # 解析 SRT，建立索引表
    srt_entries = parse_srt(srt_content)
    srt_table   = build_srt_index_table(srt_entries)
    total_srt   = len(srt_entries)

    system = (
        "你是一位頂尖短影音導演與內容策略師，擅長為 TikTok / IG Reels / YouTube Shorts 設計爆紅短影音。"
        "你深諳「前3秒勾子」法則，能從素材中挑選最強爆點，設計讓觀眾停止滑動的開場。"
        "你的輸出是嚴格合法的 JSON，不含任何額外說明文字或 markdown。"
    )

    user = f"""
請根據下方資料，設計一支 **30-60 秒**爆紅短影音的完整分鏡腳本。

## 短影音爆紅方法論（節錄）
{methodology[:4000]}

## 爆紅片段分析 CSV
{csv_content}

## 字幕索引表（共 {total_srt} 條，格式：[序號] 開始時間→結束時間  字幕文字）
{srt_table}

## 使用者指定片尾 CTA
{cta}

---
設計要求：
1. **前3秒勾子**：從 CSV 爆紅評分最高的片段取材，製造懸念、驚喜或強烈情緒。
   說明：① 畫面構圖（特寫/中景） ② 疊加文字（≤10字） ③ 旁白/原聲 ④ 為何能留住觀眾。
2. **完整分鏡**：從字幕索引表中挑選最佳組合，依「勾子→情境交代→高潮揭露」結構，
   每個場景附：視覺描述、字幕提詞、轉場方式（cut/fade/zoom/slide）。
   ⚠️ `storyboard` 陣列**絕對不可以**出現 `"label": "cta"` 的場景，CTA 只放在 `cta_scene`。
3. **片尾 CTA**：只填在 `cta_scene` 欄位，設計引導使用者完成指定行動的畫面與語音。不要在 `storyboard` 裡重複放 CTA。

⚠️ 時間戳規則（重要）：
- **不要自己填寫任何時間戳字串**
- 每個場景只需填 `srt_start` 和 `srt_end`，填入字幕索引表的**序號整數**（1 ~ {total_srt}）
- `srt_start`：該場景從第幾條字幕開始（取該條的開始時間）
- `srt_end`：該場景到第幾條字幕結束（取該條的結束時間）
- 例：想用第2條字幕的開始到第3條的結束 → `"srt_start": 2, "srt_end": 3`

⚠️ 時長預算（硬性限制）：
- **所有 storyboard 場景的秒數加總必須在 30～60 秒之間**，這是最重要的約束
- 字幕索引表每條都標示了秒數（如 `7.0s`），選 srt_start→srt_end 時請自己加總確認
- 每個 label 建議上限：hook ≤5s、intro ≤8s、story ≤10s、climax ≤8s、extra ≤8s、cta ≤5s
- 若某段素材太長（>10s），只選其中幾條字幕（縮短 srt_end），不要整段全選
- 場景數建議 5～9 個，過多會讓每段太碎

輸出格式（嚴格 JSON，無任何 markdown 或說明）：
{{
  "total_duration_seconds": <整數>,
  "narrative_strategy": "<整體敘事策略，100字以內>",
  "hook": {{
    "source_segment": "<CSV 片段編號>",
    "srt_start": <字幕序號整數>,
    "srt_end": <字幕序號整數>,
    "visual": "<畫面構圖描述>",
    "text_overlay": "<疊加文字，≤10字>",
    "voiceover": "<旁白或原聲片段內容>",
    "composition": "<特寫/中景/遠景>",
    "design_rationale": "<為何這3秒能留住觀眾，50字以內>"
  }},
  "storyboard": [
    {{
      "scene_number": <從1開始的整數>,
      "label": "<hook/intro/story/climax/extra>",
      "source_segment": "<CSV 片段編號>",
      "srt_start": <字幕序號整數>,
      "srt_end": <字幕序號整數>,
      "visual": "<畫面描述>",
      "text_overlay": "<字幕或提詞，可空字串>",
      "voiceover": "<旁白或原聲>",
      "transition_in": "<cut/fade/zoom/slide>",
      "transition_out": "<cut/fade/zoom/slide>",
      "viral_score": <數字，來自 CSV>,
      "purpose": "<此場景在整支影片的作用>"
    }}
  ],
  "cta_scene": {{
    "srt_start": <字幕序號整數>,
    "srt_end": <字幕序號整數>,
    "duration_seconds": <整數>,
    "visual": "<畫面描述>",
    "text_overlay": "<CTA 文字>",
    "voiceover": "<引導語音>",
    "cta_action": "<具體行動指令>"
  }}
}}"""

    kwargs = dict(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    try:
        kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
    except Exception:
        del kwargs["response_format"]
        resp = client.chat.completions.create(**kwargs)

    raw = resp.choices[0].message.content.strip()
    result = extract_json(raw)

    # 把 srt_start/srt_end 索引 → 真實時間戳
    result = resolve_storyboard_times(result, srt_entries)
    return result


# ── 主流程 ────────────────────────────────────────────────────────────────────
def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("錯誤：請設定 OPENAI_API_KEY 環境變數")
        sys.exit(1)
    client = OpenAI(api_key=api_key)

    # 1. 選擇來源檔案
    csv_file = select_file(sorted(OUTPUT_DIR.glob("*_viral_segments.csv")), "爆紅分析 CSV")
    if not csv_file:
        print("錯誤：output/ 找不到 *_viral_segments.csv，請先執行 /run-viral-analyzer")
        sys.exit(1)

    srt_file = select_file(sorted(OUTPUT_DIR.glob("*.srt")), "SRT 字幕檔")
    if not srt_file:
        print("錯誤：output/ 找不到 .srt 字幕檔，請先執行 /run-transcribe")
        sys.exit(1)

    video_file = select_file(
        sorted(UPLOAD_DIR.glob("*.mp4")) + sorted(UPLOAD_DIR.glob("*.mov")),
        "影片（可略過截圖）",
    )

    # 2. 詢問 CTA
    print("\n請輸入片尾 CTA（例如：追蹤帳號 @hwccoffee / 點擊連結訂閱 / 留言告訴我你的想法）")
    try:
        cta = input("CTA > ").strip() or "追蹤我們獲取更多精品咖啡好內容"
    except EOFError:
        cta = "追蹤我們獲取更多精品咖啡好內容"

    # 3. 讀取內容
    print("\n📖 讀取分析資料…")
    csv_content  = csv_file.read_text(encoding="utf-8-sig")
    srt_content  = srt_file.read_text(encoding="utf-8")
    methodology  = METHODOLOGY.read_text(encoding="utf-8") if METHODOLOGY.exists() else ""

    # 找最高爆紅評分片段（用於截圖）
    segments = []
    with open(csv_file, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            segments.append(row)
    top = max(segments, key=lambda x: int(x.get("爆紅潛力評分", 0)))
    print(f"🎯 最高評分片段：片段 {top['片段編號']}（評分 {top['爆紅潛力評分']}）"
          f"  {top['開始時間']} → {top['結束時間']}")

    # 4. 對最高評分片段做逐秒截圖
    hook_screenshots: list[str] = []
    if video_file:
        print("\n📸 對最高評分片段做逐秒截圖…")
        hook_screenshots = extract_screenshots_range(
            video_file,
            top["開始時間"],
            top["結束時間"],
            "hook",
        )
        print(f"   截取 {len(hook_screenshots)} 張截圖 → output/storyboard_screenshots/")
    else:
        print("\n⚠️  未找到影片，跳過截圖步驟")

    # 5. 呼叫 GPT-5.5 設計分鏡
    print(f"\n🤖 呼叫 {MODEL} 設計分鏡腳本…")
    try:
        storyboard = design_storyboard(client, srt_content, csv_content, methodology, cta)
    except Exception as e:
        print(f"錯誤：GPT 呼叫失敗 — {e}")
        sys.exit(1)
    scenes = [s for s in storyboard.get("storyboard", [])
              if s.get("label", "").lower() != "cta"]
    actual_total = sum(s.get("duration_seconds", 0) for s in scenes)
    print(f"   ✓ 分鏡設計完成，共 {len(scenes)} 個場景（CTA 另存於 cta_scene）")
    print(f"   ✓ 各場景秒數：{' + '.join(str(s.get('duration_seconds',0)) for s in scenes)} = {actual_total}s")
    if actual_total < 30:
        print(f"   ⚠️  總時長 {actual_total}s 低於 30s，建議補充場景")
    elif actual_total > 60:
        print(f"   ⚠️  總時長 {actual_total}s 超過 60s（目標 30-60s），建議縮短各場景的 srt 範圍")

    # 6. 對各分鏡節點提取代表截圖
    scene_shots: dict[int, str] = {}
    if video_file:
        print("\n📸 提取各分鏡代表截圖…")
        for scene in storyboard.get("storyboard", []):
            n = scene.get("scene_number", 0)
            t = scene.get("start_time", "")
            if t:
                shot = extract_single_shot(video_file, t, f"scene_{n:02d}.jpg")
                if shot:
                    scene_shots[n] = shot
                    print(f"   場景 {n:02d} ✓")

    # 7. 組合最終 JSON
    stem = csv_file.stem.replace("_viral_segments", "")
    out_path = OUTPUT_DIR / f"{stem}_storyboard.json"

    final = {
        "meta": {
            "generated_at":           datetime.now().isoformat(),
            "source_srt":             srt_file.name,
            "source_csv":             csv_file.name,
            "model":                  MODEL,
            "cta":                    cta,
            "total_duration_seconds": storyboard.get("total_duration_seconds", 0),
            "narrative_strategy":     storyboard.get("narrative_strategy", ""),
        },
        "hook": {
            **storyboard.get("hook", {}),
            "screenshots": hook_screenshots,
        },
        "storyboard": [
            {
                **scene,
                "screenshot": scene_shots.get(scene.get("scene_number")),
            }
            for scene in storyboard.get("storyboard", [])
            if scene.get("label", "").lower() != "cta"   # CTA 只在 cta_scene
        ],
        "cta_scene": storyboard.get("cta_scene", {}),
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 分鏡腳本已儲存：output/{out_path.name}")
    print(f"   場景總數：{len(final['storyboard'])} 個分鏡")
    print(f"   預計時長：{final['meta']['total_duration_seconds']} 秒")
    if hook_screenshots:
        print(f"   勾子截圖：{len(hook_screenshots)} 張（逐秒）")


if __name__ == "__main__":
    main()
