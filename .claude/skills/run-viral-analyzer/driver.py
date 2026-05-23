#!/usr/bin/env python3
"""
Analyze SRT subtitles to find viral short-video segments using GPT-4o.
Usage: python driver.py [--count N] [--background TEXT] [srt_file]

Input : output/<file>.srt
Output: output/<file>_viral_segments.csv
"""
import argparse
import csv
import io
import os
import sys
from pathlib import Path

from openai import OpenAI

BASE = Path(__file__).resolve().parents[3]
OUTPUT_DIR = BASE / "output"
METHODOLOGY_FILE = BASE / "短影音爆紅入門全攻略.md"

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def pick_srt(output_dir: Path) -> Path:
    srt_files = sorted(output_dir.glob("*.srt"))
    if not srt_files:
        sys.exit("找不到 output/ 內的 .srt 檔案，請先執行 /run-transcribe。")
    if len(srt_files) == 1:
        return srt_files[0]
    print("找到多個 SRT 檔案，請選擇：")
    for i, f in enumerate(srt_files, 1):
        print(f"  {i}. {f.name}")
    choice = input("請輸入編號：").strip()
    try:
        return srt_files[int(choice) - 1]
    except (ValueError, IndexError):
        sys.exit("無效的選擇。")


def load_methodology() -> str:
    if METHODOLOGY_FILE.exists():
        return METHODOLOGY_FILE.read_text(encoding="utf-8")
    return ""


def analyze_viral_segments(srt_content: str, methodology: str, count: int, background: str) -> list[dict]:
    methodology_section = f"\n\n以下是短影音爆紅方法論，請參考用於評分：\n{methodology}" if methodology else ""
    background_section = f"\n影片背景資訊：{background}" if background else ""

    prompt = f"""你是短影音內容策略專家，請分析以下 SRT 字幕，找出最有爆紅潛力的片段。{background_section}{methodology_section}

請分析所有有潛力的片段，依爆紅潛力由高到低排序，**只回傳前 {count} 名**。

輸出格式：純 CSV 文字，使用 UTF-8，包含標題列，欄位如下：
片段編號,開始時間,結束時間,片段內容摘要,爆紅潛力評分,爆紅原因,推薦關鍵字,建議標題

規則：
- 片段編號：1 到 {count}
- 開始時間/結束時間：格式 HH:MM:SS.mmm（毫秒用句點分隔，例如 00:00:09.500，**不要用逗號**）
- 片段內容摘要：30 字以內
- 爆紅潛力評分：1–10 整數
- 爆紅原因：具體說明
- 推薦關鍵字：3–5 個，用「、」頓號分隔（不要用逗號），整個欄位**必須**用雙引號包住
- 建議標題：吸睛、能引發好奇心的短影音標題，**必須**用雙引號包住
- 爆紅原因：**必須**用雙引號包住（因為可能含逗號）
- 片段內容摘要：**必須**用雙引號包住
- 除標題列外，每行代表一個片段，標題列**不要**有尾隨逗號
- 輸出的 CSV 只有 8 個欄位，不能多也不能少

SRT 字幕內容：
{srt_content}
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )

    csv_text = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if csv_text.startswith("```"):
        lines = csv_text.splitlines()
        csv_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    reader = csv.DictReader(io.StringIO(csv_text))
    return list(reader)


def save_csv(rows: list[dict], output_path: Path) -> None:
    if not rows:
        sys.exit("GPT-4o 未回傳任何片段，請確認 SRT 內容是否正確。")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("srt_file", nargs="?", help="SRT file path (relative to output/ if not absolute)")
    parser.add_argument("--count", type=int, default=3, help="Number of viral segments to return")
    parser.add_argument("--background", type=str, default="", help="Background info about the video")
    args = parser.parse_args()

    if args.srt_file:
        srt_path = Path(args.srt_file)
        if not srt_path.is_absolute():
            srt_path = OUTPUT_DIR / srt_path
    else:
        srt_path = pick_srt(OUTPUT_DIR)

    if not srt_path.exists():
        sys.exit(f"找不到 SRT 檔案：{srt_path}")

    srt_content = srt_path.read_text(encoding="utf-8")
    if not srt_content.strip():
        sys.exit("SRT 檔案是空的，請重新執行 /run-transcribe。")

    methodology = load_methodology()

    print(f"分析 SRT：{srt_path.name}（要求 {args.count} 個片段）…")
    rows = analyze_viral_segments(srt_content, methodology, args.count, args.background)

    output_csv = OUTPUT_DIR / (srt_path.stem + "_viral_segments.csv")
    save_csv(rows, output_csv)

    print(f"\n找到 {len(rows)} 個爆紅片段：")
    for row in rows:
        num = row.get("片段編號", "?")
        start = row.get("開始時間", "")
        end = row.get("結束時間", "")
        score = row.get("爆紅潛力評分", "")
        title = row.get("建議標題", "")
        print(f"  #{num} [{start} → {end}] 評分={score} 《{title}》")

    print(f"\nCSV 已儲存至：{output_csv}")


if __name__ == "__main__":
    main()
