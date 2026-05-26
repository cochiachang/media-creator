#!/usr/bin/env python3
"""
Facebook 貼文生成器 - 讀取 *_storyboard.json，呼叫 GPT-4o 生成一篇 FB 貼文存成 TXT
"""
import json
import os
import sys
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("錯誤：缺少 openai 套件，請執行：pip install openai")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR   = PROJECT_ROOT / "output"
POSTS_DIR    = OUTPUT_DIR / "posts"

SYSTEM_PROMPT = (
    "你是一個平常很愛在 Facebook 分享生活的台灣人，說話很自然隨性，"
    "就像在跟朋友聊天一樣。你不是行銷人員，不會說廣告話術，"
    "也不會刻意營造形象或置入行銷。你就是把一件你覺得有趣的事情分享出來。"
)

USER_PROMPT_TEMPLATE = """\
以下是一支短影音的完整分鏡腳本 JSON，請根據整體內容，寫一篇 Facebook 貼文：

{storyboard_json}

寫作原則：
- 像在跟朋友分享整支影片的感受，不要像在打廣告
- 不要說「你知道嗎」「你是否曾經」這種起頭
- 不要有「按讚分享留言」這種 CTA
- 不要用過多驚嘆號，也不要每句都加 emoji
- 口氣可以帶一點個人感受或小感慨
- 繁體中文，150-200字（不含 hashtag）
- 結尾加 3-5 個貼近內容的 hashtag
- 直接輸出貼文，不需要任何說明"""


def generate_fb_post(client: OpenAI, storyboard: dict) -> str:
    prompt = USER_PROMPT_TEMPLATE.format(
        storyboard_json=json.dumps(storyboard, ensure_ascii=False, indent=2)
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.8,
    )
    return response.choices[0].message.content.strip()


def select_storyboard() -> Path:
    jsons = sorted(OUTPUT_DIR.glob("*_storyboard.json"))
    if not jsons:
        print("output/ 中沒有找到 *_storyboard.json 檔案")
        print("請先執行 /run-viral-storyboard 產生分鏡腳本")
        sys.exit(1)
    if len(jsons) == 1:
        print(f"使用分鏡腳本：{jsons[0].name}")
        return jsons[0]
    print("找到多個分鏡腳本：")
    for i, f in enumerate(jsons, 1):
        print(f"  {i}. {f.name}")
    while True:
        try:
            choice = input("請選擇要處理的檔案（輸入編號）：").strip()
        except EOFError:
            return jsons[0]
        if choice.isdigit() and 1 <= int(choice) <= len(jsons):
            return jsons[int(choice) - 1]
        print("請輸入有效的編號")


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("錯誤：請設定 OPENAI_API_KEY 環境變數")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    sb_path    = select_storyboard()
    storyboard = json.loads(sb_path.read_text(encoding="utf-8"))

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    stem     = sb_path.stem.replace("_storyboard", "")
    out_path = POSTS_DIR / f"{stem}_fb_post.txt"

    print(f"\n🤖 呼叫 GPT-4o 生成 Facebook 貼文…")
    try:
        post = generate_fb_post(client, storyboard)
    except Exception as e:
        print(f"錯誤：生成失敗 — {e}")
        sys.exit(1)

    out_path.write_text(post + "\n", encoding="utf-8")

    print(f"\n✅ 貼文已儲存：output/posts/{out_path.name}")
    print(f"\n{'─'*50}")
    print(post)
    print(f"{'─'*50}")


if __name__ == "__main__":
    main()
