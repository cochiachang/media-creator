#!/usr/bin/env python3
"""
Veo3 Hook 生成器 v4
流程：
  1. 讀取 *_storyboard.json
  2. 列出所有 scene_XX.jpg 截圖
  3. 全部傳給 GPT-4o Vision →
       a. 選出最吸睛的一張作為 Veo3 起始幀
       b. 根據該圖與分鏡策略，生成繁體中文 hook 字幕（≤2行）
       c. 生成英文 Veo3 visual prompt（純視覺，無人物說話、無名字）
  4. 用選出的截圖呼叫 Veo3 image-to-video
  5. ffmpeg 燒入繁體中文字幕
  6. ffmpeg 2x 加速（去除原音）
  7. OpenAI TTS nova 1.25x 生成旁白（字幕加驚嘆號，語氣興奮）
  8. ffmpeg 合入 TTS 音訊
  9. 輸出 output/veo3_hook_final.mp4
"""
import base64
import json
import os
import sys
import time
import subprocess
import requests
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("錯誤：缺少 openai，請執行：pip install openai")
    sys.exit(1)

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("錯誤：缺少 google-genai，請執行：pip install google-genai")
    sys.exit(1)

# ── 設定 ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT       = Path(__file__).resolve().parents[3]
OUTPUT_DIR         = PROJECT_ROOT / "output"
SHOTS_DIR          = OUTPUT_DIR / "storyboard_screenshots"
VEO_MODEL          = "veo-3.0-generate-001"
VEO_FALLBACK_MODEL = "veo-3.0-fast-generate-001"
GPT_MODEL          = "gpt-4o"
POLL_INTERVAL      = 20


# ── Step 1：列出 scene 截圖 ────────────────────────────────────────────────────
def list_scene_shots() -> list[Path]:
    shots = sorted(SHOTS_DIR.glob("scene_*.jpg"))
    if not shots:
        shots = sorted(SHOTS_DIR.glob("scene_*.png"))
    return shots


# ── Step 2：GPT-4o Vision 看圖，選幀 + 生字幕 + 生 prompt ─────────────────────
def gpt_vision_plan(
    oai_client: OpenAI,
    storyboard: dict,
    scene_shots: list[Path],
) -> dict:
    """
    把所有 scene 截圖 + storyboard JSON 傳給 GPT-4o Vision。
    回傳 {"best_image": "scene_08.jpg", "subtitle": "...", "veo_prompt": "..."}
    """
    sb_summary = {
        "narrative_strategy": storyboard.get("meta", {}).get("narrative_strategy", ""),
        "hook": {k: v for k, v in storyboard.get("hook", {}).items()
                 if k in ("visual", "composition", "design_rationale", "text_overlay")},
        "cta": storyboard.get("meta", {}).get("cta", ""),
    }
    sb_json = json.dumps(sb_summary, ensure_ascii=False, indent=2)

    # 組合 vision messages：文字 + 每張圖片
    content = []

    # 先說明任務
    content.append({
        "type": "text",
        "text": f"""你是一位頂尖短影音導演。以下是這支短影音的分鏡策略：

{sb_json}

以下是從影片中截取的 {len(scene_shots)} 張場景截圖（scene_01.jpg ~ scene_{len(scene_shots):02d}.jpg）。
請完成三件事：

1. **選出最適合作為 hook 起始畫面的截圖**
   - 最視覺衝擊、最能引發好奇心
   - 不要選人物正在說話或嘴巴張開的幀
   - 要能配合上字幕後讓觀眾停止滑動

2. **設計繁體中文 hook 字幕**（最多 2 行，每行最多 12 字，換行用 \\n）
   - 純文字就能吸引人，不依賴聲音
   - 搭配你選的那張圖，製造強烈好奇或情緒衝擊

3. **設計英文 Veo3 image-to-video prompt**
   - 以你選的圖為起始幀，描述接下來的視覺動態（鏡頭運動、光線變化、物件動作）
   - **嚴格禁止**：不寫任何人名、不描述人物說話或對鏡頭講話、不提任何對話或旁白
   - 可以有人物動作（手部、轉身、走動），但不能有說話相關描述
   - 可以有音效/氛圍（ambient sounds, dramatic music sting），但不能提 voice/dialogue
   - 約 80-100 字，英文

輸出格式（嚴格 JSON，不含任何 markdown）：
{{
  "best_image": "<截圖檔名，例如 scene_08.jpg>",
  "subtitle": "<繁體中文，換行用 \\\\n>",
  "veo_prompt": "<英文 Veo3 prompt>"
}}"""
    })

    # 加入所有截圖
    for shot in scene_shots:
        img_b64 = base64.b64encode(shot.read_bytes()).decode()
        content.append({
            "type": "text",
            "text": f"[{shot.name}]"
        })
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img_b64}",
                "detail": "low",   # 省 token，場景識別用 low 就夠
            }
        })

    resp = oai_client.chat.completions.create(
        model=GPT_MODEL,
        messages=[{"role": "user", "content": content}],
        temperature=0.8,
        max_tokens=500,
        response_format={"type": "json_object"},
    )

    raw = resp.choices[0].message.content.strip()
    data = json.loads(raw)
    return data


# ── Step 3：Veo3 image-to-video ───────────────────────────────────────────────
def _run_veo(client: genai.Client, model: str, prompt: str, image_obj) -> "operation":
    config = types.GenerateVideosConfig(
        aspect_ratio="9:16",
        number_of_videos=1,
    )
    try:
        op = client.models.generate_videos(
            model=model, prompt=prompt, image=image_obj, config=config
        )
    except Exception as e:
        err = str(e).lower()
        if "image" in err or "unsupported" in err:
            print(f"  ⚠️  image-to-video 不支援，改用 text-only…")
            op = client.models.generate_videos(model=model, prompt=prompt, config=config)
        elif "duration" in err or "invalid" in err:
            print(f"  ⚠️  自動加 duration_seconds=5…")
            config2 = types.GenerateVideosConfig(aspect_ratio="9:16", duration_seconds=5, number_of_videos=1)
            op = client.models.generate_videos(model=model, prompt=prompt, image=image_obj, config=config2)
        else:
            raise

    print(f"  ⏳ 等待渲染（每 {POLL_INTERVAL}s 確認一次）…")
    elapsed = 0
    while not op.done:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        op = client.operations.get(op)
        print(f"     {elapsed}s 已過…")
    return op


def generate_veo3_video(client: genai.Client, prompt: str, ref_image: Path) -> Path | None:
    image_obj = types.Image(image_bytes=ref_image.read_bytes(), mime_type="image/jpeg")

    for model in [VEO_MODEL, VEO_FALLBACK_MODEL]:
        print(f"  🚀 送出生成請求（{model}）…")
        try:
            op = _run_veo(client, model, prompt, image_obj)
        except Exception as e:
            print(f"  ❌ {model} 呼叫失敗：{e}")
            continue

        resp     = op.response
        filtered = getattr(resp, "rai_media_filtered_count", 0) or 0
        vids     = getattr(resp, "generated_videos", [])

        if filtered and not vids:
            reasons = getattr(resp, "rai_media_filtered_reasons", [])
            print(f"  ⚠️  被安全過濾（{reasons}）")
            if model != VEO_FALLBACK_MODEL:
                print(f"  🔄 切換 fallback 模型…")
            continue

        if not vids:
            print(f"  ❌ 無影片輸出")
            continue

        uri = getattr(vids[0].video, "uri", None)
        if not uri:
            continue

        out_path = OUTPUT_DIR / "veo3_hook_raw.mp4"
        print("  ⬇️  下載影片…")
        r = requests.get(uri, params={"key": client._api_client.api_key}, stream=True, timeout=120)
        if r.status_code == 200:
            out_path.write_bytes(r.content)
            print(f"  💾 {out_path.name}（{out_path.stat().st_size/1024:.0f} KB）[{model}]")
            return out_path
        else:
            print(f"  ❌ 下載失敗 HTTP {r.status_code}")

    return None


# ── Step 4：ffmpeg 燒入繁體中文字幕 ──────────────────────────────────────────
def burn_subtitle(src: Path, subtitle: str, out_path: Path) -> bool:
    font_candidates = [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode MS.ttf",
        "/Library/Fonts/Arial Unicode MS.ttf",
    ]
    font = next((f for f in font_candidates if Path(f).exists()), None)
    if not font:
        print("  ⚠️  找不到中文字體，字幕可能顯示為方框")
        font = "default"

    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(src)],
        capture_output=True, text=True,
    )
    dims = probe.stdout.strip().split(",")
    w, h = (int(dims[0]), int(dims[1])) if len(dims) == 2 else (1080, 1920)

    lines     = subtitle.replace("\\n", "\n").split("\n")
    font_size = max(64, w // 11)
    line_h    = font_size + 14
    total_h   = line_h * len(lines)
    start_y   = int(h * 0.70) - total_h // 2

    filters = []
    for i, line in enumerate(lines):
        escaped = line.replace("'", "\\'").replace(":", "\\:")
        y = start_y + i * line_h
        filters.append(
            f"drawtext=fontfile='{font}'"
            f":text='{escaped}'"
            f":fontsize={font_size}"
            f":fontcolor=white"
            f":borderw=5"
            f":bordercolor=black@0.85"
            f":x=(w-text_w)/2"
            f":y={y}"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vf", ",".join(filters),
        "-c:a", "copy",
        "-c:v", "libx264", "-crf", "18",
        str(out_path),
    ]
    print(f"  🖊️  燒入字幕：{subtitle!r}")
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and out_path.exists():
        print(f"  ✅ 完成 → {out_path.name}（{out_path.stat().st_size/1024:.0f} KB）")
        return True
    else:
        print(f"  ❌ 失敗：{result.stderr.decode(errors='replace')[-300:]}")
        return False


# ── Step 6：ffmpeg 2x 加速（去除原音）────────────────────────────────────────
def speed_up_video(src: Path, out: Path, speed: float = 2.0) -> bool:
    """影片加速並去除原始音軌。"""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vf", f"setpts={1/speed}*PTS",
        "-an",                          # 去除音訊
        "-c:v", "libx264", "-crf", "18",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and out.exists():
        print(f"  ✅ {speed}x 加速完成 → {out.name}（{out.stat().st_size/1024:.0f} KB）")
        return True
    print(f"  ❌ 加速失敗：{result.stderr.decode(errors='replace')[-200:]}")
    return False


# ── Step 7：OpenAI TTS 生成旁白 ───────────────────────────────────────────────
def generate_tts(oai_client: OpenAI, subtitle: str, out: Path) -> bool:
    """
    把字幕每行加上驚嘆號，用 nova 聲 1.25x 速度生成 mp3。
    字幕顯示與 TTS 文字刻意分開：視覺乾淨，語音興奮。
    """
    lines = subtitle.replace("\\n", "\n").split("\n")
    # 每行結尾若無標點則加驚嘆號
    excited_lines = []
    for line in lines:
        line = line.strip()
        if line and line[-1] not in "！!？?。.":
            line += "！"
        excited_lines.append(line)
    tts_text = "".join(excited_lines)   # 合成一句連唸

    print(f"  🎙️  TTS 文字：『{tts_text}』（nova, 1.25x）")
    try:
        resp = oai_client.audio.speech.create(
            model="tts-1-hd",
            voice="nova",
            input=tts_text,
            response_format="mp3",
            speed=1.25,
        )
        out.write_bytes(resp.content)
        print(f"  ✅ TTS 完成 → {out.name}（{out.stat().st_size/1024:.0f} KB）")
        return True
    except Exception as e:
        print(f"  ❌ TTS 失敗：{e}")
        return False


# ── Step 8：ffmpeg 合入 TTS 音訊 ──────────────────────────────────────────────
def merge_tts(video: Path, audio: Path, out: Path) -> bool:
    """把靜音影片與 TTS mp3 合成，以最短的那方結尾。"""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-i", str(audio),
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and out.exists():
        print(f"  ✅ 合音完成 → {out.name}（{out.stat().st_size/1024:.0f} KB）")
        return True
    print(f"  ❌ 合音失敗：{result.stderr.decode(errors='replace')[-200:]}")
    return False


# ── 主流程 ────────────────────────────────────────────────────────────────────
def main():
    openai_key = os.environ.get("OPENAI_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not openai_key:
        print("錯誤：請設定 OPENAI_API_KEY"); sys.exit(1)
    if not gemini_key:
        print("錯誤：請設定 GEMINI_API_KEY"); sys.exit(1)

    oai_client = OpenAI(api_key=openai_key)
    veo_client = genai.Client(api_key=gemini_key)

    # 找 storyboard JSON
    jsons = sorted(OUTPUT_DIR.glob("*_storyboard.json"))
    if not jsons:
        print("錯誤：output/ 找不到 *_storyboard.json，請先執行 /run-viral-storyboard")
        sys.exit(1)
    storyboard_path = jsons[0]
    if len(jsons) > 1:
        for i, j in enumerate(jsons, 1):
            print(f"  {i}. {j.name}")
        try:
            idx = int(input(f"找到多個分鏡，請選（1~{len(jsons)}）：") or "1") - 1
            storyboard_path = jsons[idx]
        except (ValueError, IndexError):
            pass

    print(f"📄 讀取分鏡：{storyboard_path.name}")
    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))

    # 列出 scene 截圖
    scene_shots = list_scene_shots()
    if not scene_shots:
        print("錯誤：output/storyboard_screenshots/ 找不到 scene_*.jpg，請先執行 /run-viral-storyboard")
        sys.exit(1)
    print(f"🖼️  找到 {len(scene_shots)} 張 scene 截圖：{[s.name for s in scene_shots]}")

    # ── Step 1：GPT-4o Vision 看圖選幀 + 生字幕 + 生 prompt ─────────────────
    print(f"\n🧠 Step 1 — {GPT_MODEL} Vision 分析截圖，選最佳幀…")
    try:
        plan = gpt_vision_plan(oai_client, storyboard, scene_shots)
    except Exception as e:
        print(f"錯誤：GPT Vision 呼叫失敗 — {e}")
        sys.exit(1)

    best_name  = plan.get("best_image", "")
    subtitle   = plan.get("subtitle", "").strip().strip('"')
    veo_prompt = plan.get("veo_prompt", "").strip()

    # 找對應截圖路徑
    ref_image = next((s for s in scene_shots if s.name == best_name), None)
    if not ref_image:
        print(f"  ⚠️  GPT 選的 {best_name!r} 不存在，改用第一張：{scene_shots[0].name}")
        ref_image = scene_shots[0]

    print(f"   ✅ 選定截圖  ：{ref_image.name}")
    print(f"   ✅ Hook 字幕 ：『{subtitle}』")
    print(f"\n📝 Veo3 Prompt 預覽（前 180 字）：")
    print(f"   {veo_prompt[:180]}…")

    # ── Step 2：Veo3 image-to-video ──────────────────────────────────────────
    print(f"\n🎬 Step 2 — {VEO_MODEL} image-to-video（以 {ref_image.name} 為起始）…")
    raw_video = generate_veo3_video(veo_client, veo_prompt, ref_image)
    if not raw_video:
        print("錯誤：Veo3 未輸出影片")
        sys.exit(1)

    # ── Step 3：ffmpeg 燒字幕 ─────────────────────────────────────────────────
    print(f"\n🖊️  Step 3 — ffmpeg 燒入繁體中文字幕…")
    subtitled = OUTPUT_DIR / "veo3_hook_subtitled.mp4"
    ok = burn_subtitle(raw_video, subtitle, subtitled)
    if not ok:
        import shutil
        shutil.copy2(raw_video, subtitled)
        print("  ⚠️  字幕燒入失敗，改用無字幕版本")

    # ── Step 4：ffmpeg 2x 加速（去原音）──────────────────────────────────────
    print(f"\n⚡ Step 4 — 影片 2x 加速…")
    sped = OUTPUT_DIR / "veo3_hook_2x.mp4"
    if not speed_up_video(subtitled, sped, speed=2.0):
        import shutil
        shutil.copy2(subtitled, sped)
        print("  ⚠️  加速失敗，使用原速版本")

    # ── Step 5：OpenAI TTS 生成旁白 ──────────────────────────────────────────
    print(f"\n🎙️  Step 5 — OpenAI TTS 生成旁白（nova, 1.25x）…")
    tts_path = OUTPUT_DIR / "veo3_hook_tts.mp3"
    tts_ok = generate_tts(oai_client, subtitle, tts_path)

    # ── Step 6：合入 TTS 音訊 ────────────────────────────────────────────────
    final_path = OUTPUT_DIR / "veo3_hook_final.mp4"
    if tts_ok:
        print(f"\n🔊 Step 6 — 合入 TTS 旁白…")
        if not merge_tts(sped, tts_path, final_path):
            import shutil
            shutil.copy2(sped, final_path)
            print("  ⚠️  合音失敗，改用無聲版本")
    else:
        import shutil
        shutil.copy2(sped, final_path)
        print("  ⚠️  TTS 失敗，改用無聲版本")

    # ── 複製到 clips/scene_00.mp4 ────────────────────────────────────────────
    import shutil
    clips_dir = OUTPUT_DIR / "clips"
    clips_dir.mkdir(exist_ok=True)
    scene_00 = clips_dir / "scene_00.mp4"
    shutil.copy2(final_path, scene_00)

    # ── 完成 ──────────────────────────────────────────────────────────────────
    print(f"\n✅ 完成！")
    print(f"   起始幀     ：{ref_image.name}")
    print(f"   字幕文字   ：{subtitle}")
    print(f"   最終影片   ：output/veo3_hook_final.mp4")
    print(f"   clips 勾子 ：output/clips/scene_00.mp4")
    print(f"   中間產物   ：veo3_hook_raw.mp4 / veo3_hook_subtitled.mp4 / veo3_hook_2x.mp4")
    print(f"\n💡 下一步：執行 /run-storyboard-assembler 合併完整影片")


if __name__ == "__main__":
    main()
