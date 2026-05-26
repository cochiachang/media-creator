#!/usr/bin/env python3
"""
Facebook 貼文生成器 - 根據 CSV 片段資訊，呼叫 OpenAI 生成 FB 貼文存成 TXT
"""
import csv
import os
import sys
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("錯誤：缺少 openai 套件，請執行：pip install openai")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = PROJECT_ROOT / "output"
POSTS_DIR = OUTPUT_DIR / "posts"

SYSTEM_PROMPT = (
    "你是一個平常很愛在 Facebook 分享生活的台灣人，說話很自然隨性，"
    "就像在跟朋友聊天一樣。你不是行銷人員，不會說廣告話術，"
    "也不會刻意營造形象或置入行銷。你就是把一件你覺得有趣的事情分享出來。"
)

USER_PROMPT_TEMPLATE = """\
根據以下影片片段的內容，用平常朋友聊天的方式寫一篇 Facebook 貼文：

影片標題：{title}
片段摘要：{summary}
這段為什麼有趣：{viral_reason}
關鍵字參考：{keywords}

寫作原則：
- 像在跟朋友分享，不要像在打廣告
- 不要說「你知道嗎」「你是否曾經」這種起頭
- 不要有「按讚分享留言」這種 CTA
- 不要用過多驚嘆號，也不要每句都加 emoji
- 口氣可以帶一點個人感受或小感慨
- 繁體中文，150-200字（不含 hashtag）
- 結尾加 3-5 個貼近內容的 hashtag
- 直接輸出貼文，不需要任何說明"""


def generate_fb_post(client, segment):
    prompt = USER_PROMPT_TEMPLATE.format(
        title=segment.get("建議標題", ""),
        summary=segment.get("片段內容摘要", ""),
        viral_reason=segment.get("爆紅原因", ""),
        keywords=segment.get("推薦關鍵字", ""),
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
    )
    return response.choices[0].message.content.strip()


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


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("錯誤：請設定 OPENAI_API_KEY 環境變數")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    csv_files = list_csv_files()
    csv_file = select_csv(csv_files)

    segments = []
    with open(csv_file, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            segments.append(row)

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n開始生成 {len(segments)} 個 Facebook 貼文…\n")

    for seg in segments:
        idx = seg.get("片段編號", "?")
        title = seg.get("建議標題", "")
        time_range = f"{seg.get('開始時間', '')} → {seg.get('結束時間', '')}"
        print(f"[{idx}] {title[:30]}{'…' if len(title) > 30 else ''}")

        out_path = POSTS_DIR / f"segment_{idx}.txt"
        try:
            post = generate_fb_post(client, seg)
            with open(out_path, "w", encoding="utf-8") as out:
                out.write(f"片段 {idx}  {time_range}\n")
                out.write(f"標題：{title}\n\n")
                out.write(post)
                out.write("\n")
            print(f"      ✓ 已儲存至 output/posts/segment_{idx}.txt")
        except Exception as e:
            print(f"      ✗ 失敗：{e}")
            with open(out_path, "w", encoding="utf-8") as out:
                out.write(f"[生成失敗：{e}]\n")

    print(f"\n完成！FB 貼文已儲存至：output/posts/")


if __name__ == "__main__":
    main()
