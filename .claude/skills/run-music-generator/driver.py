#!/usr/bin/env python3
"""
音樂生成器 - 讀取 output/posts/ 的 TXT 貼文，用 GPT-4o 生成 Suno prompt，再呼叫 sunoapi.org 生成音樂
"""
import os
import sys
import time
import json
import httpx
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("錯誤：缺少 openai 套件，請執行：pip install openai")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
POSTS_DIR = PROJECT_ROOT / "output" / "posts"
MUSIC_DIR = PROJECT_ROOT / "output" / "music"

SUNO_API_BASE = "https://api.sunoapi.org/api/v1"
WEBHOOK_SITE = "https://webhook.site"

SYSTEM_PROMPT = (
    "你是一位音樂製作人，擅長根據文字內容為短影音設計背景音樂。"
    "你的任務是根據 Facebook 貼文的氛圍與主題，產出一段給 Suno AI 使用的英文 prompt。"
)

USER_PROMPT_TEMPLATE = """\
根據以下 Facebook 貼文的內容與氛圍，生成一段給 Suno AI 的音樂 prompt。

貼文內容：
{post_content}

請輸出 JSON 格式，包含以下欄位：
{{
  "prompt": "描述音樂風格、節奏、樂器、情緒的英文句子（30-60字）",
  "style": "音樂風格標籤，英文，逗號分隔（如 pop, acoustic, upbeat）",
  "title": "音樂標題（繁體中文，5-10字）"
}}

注意：
- prompt 和 style 必須是英文
- 風格要符合貼文的情緒與主題
- 適合作為短影音背景音樂（60秒左右）
- 只輸出 JSON，不要其他說明"""


def generate_suno_prompt(client, post_content):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(post_content=post_content)},
        ],
        temperature=0.8,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content.strip())


def create_webhook():
    """建立 webhook.site 臨時端點，回傳 (uuid, callback_url)"""
    r = httpx.post(f"{WEBHOOK_SITE}/token", json={}, timeout=10)
    r.raise_for_status()
    uuid = r.json()["uuid"]
    return uuid, f"{WEBHOOK_SITE}/{uuid}"


def create_suno_task(suno_key, prompt_data, callback_url):
    headers = {
        "Authorization": f"Bearer {suno_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "customMode": True,
        "instrumental": True,
        "model": "V4_5ALL",
        "callBackUrl": callback_url,
        "prompt": prompt_data["prompt"],
        "style": prompt_data.get("style", ""),
        "title": prompt_data.get("title", ""),
    }
    resp = httpx.post(f"{SUNO_API_BASE}/generate", json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 200:
        raise ValueError(f"Suno API 錯誤：{data.get('msg', data)}")
    return data["data"]["taskId"]


def extract_audio_urls(payload_str):
    """從 callback payload 中找出所有音樂 URL，回傳 list"""
    try:
        payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
    except json.JSONDecodeError:
        return []

    # 取 data 陣列（sunoapi.org 格式：{"code":200,"data":{"data":[...]}}）
    outer = payload.get("data") or payload
    if isinstance(outer, dict):
        clips = outer.get("data") or []
    else:
        clips = outer if isinstance(outer, list) else []

    urls = []
    for clip in clips:
        # stream_audio_url 優先（audio_url 通常為空）
        url = (clip.get("stream_audio_url") or
               clip.get("source_stream_audio_url") or
               clip.get("audio_url") or
               clip.get("audioUrl") or
               clip.get("url") or "")
        if url:
            urls.append(url)

    return urls


def wait_for_callback(webhook_uuid, timeout=600):
    """輪詢 webhook.site 直到收到 Suno 的 callback，回傳音樂 URL 列表"""
    deadline = time.time() + timeout
    print("      等待 Suno callback", end="", flush=True)
    while time.time() < deadline:
        r = httpx.get(
            f"{WEBHOOK_SITE}/token/{webhook_uuid}/requests",
            timeout=10,
        )
        r.raise_for_status()
        for req in r.json().get("data", []):
            urls = extract_audio_urls(req.get("content", ""))
            if urls:
                print(" 完成")
                return urls
        print(".", end="", flush=True)
        time.sleep(10)
    raise TimeoutError(f"等待 Suno callback 超時（{timeout}s）")


def download_audio(url, out_path):
    with httpx.stream("GET", url, timeout=120, follow_redirects=True) as resp:
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=8192):
                f.write(chunk)


def list_post_files():
    if not POSTS_DIR.exists():
        return []
    return sorted(POSTS_DIR.glob("*.txt"))


def main():
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        print("錯誤：請設定 OPENAI_API_KEY 環境變數")
        sys.exit(1)

    suno_key = os.environ.get("SUNO_API_KEY")
    if not suno_key:
        print("錯誤：請設定 SUNO_API_KEY 環境變數")
        sys.exit(1)

    post_files = list_post_files()
    if not post_files:
        print("output/posts/ 中沒有找到 .txt 檔案")
        print("請先執行 /run-fb-post-generator 產生貼文")
        sys.exit(1)

    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=openai_key)

    print(f"找到 {len(post_files)} 個貼文，開始生成音樂…\n")

    for txt_path in post_files:
        stem = txt_path.stem
        print(f"[{stem}]")
        post_content = txt_path.read_text(encoding="utf-8").strip()

        try:
            print("      生成 Suno prompt…")
            prompt_data = generate_suno_prompt(client, post_content)
            print(f"      風格：{prompt_data.get('style', '')}")
            print(f"      標題：{prompt_data.get('title', '')}")
            print(f"      Prompt：{prompt_data.get('prompt', '')[:60]}…")

            webhook_uuid, callback_url = create_webhook()
            task_id = create_suno_task(suno_key, prompt_data, callback_url)
            print(f"      Task ID：{task_id}")

            audio_urls = wait_for_callback(webhook_uuid)

            for i, url in enumerate(audio_urls, 1):
                suffix = f"_v{i}" if len(audio_urls) > 1 else ""
                mp3_path = MUSIC_DIR / f"{stem}{suffix}.mp3"
                print(f"      下載版本 {i}…")
                download_audio(url, mp3_path)
                print(f"      ✓ 已儲存至 output/music/{stem}{suffix}.mp3")
            print()

        except Exception as e:
            print(f"      ✗ 失敗：{e}\n")

    print("完成！音樂檔案已儲存至：output/music/")


if __name__ == "__main__":
    main()
