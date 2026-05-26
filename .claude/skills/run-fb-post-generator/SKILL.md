---
name: run-fb-post-generator
description: 根據 output/ 的 CSV 爆紅片段，呼叫 OpenAI GPT-4o 為每個片段生成 Facebook 貼文文字，輸出為 TXT 檔案。Generate, FB, Facebook, post, 貼文, 社群, 文案, copywriting
---

# Facebook 貼文生成器

讀取 `output/*_viral_segments.csv`，為每個片段呼叫 OpenAI GPT-4o 生成一篇繁中 Facebook 貼文（含開頭吸睛句、主文、CTA、hashtag），輸出為 `output/<filename>_fb_posts.txt`。

Driver：`.claude/skills/run-fb-post-generator/driver.py`
Input：`output/*_viral_segments.csv`
Output：`output/<filename>_fb_posts.txt`

## Prerequisites

```bash
pip install openai
export OPENAI_API_KEY=<your-key>
```

## Run

```bash
python3 .claude/skills/run-fb-post-generator/driver.py
```

若 `output/` 有多個 CSV，互動選擇。單一 CSV 自動執行。

## 輸出格式

```
=== 片段 1  00:00:02 → 00:00:21 ===
標題：台灣代表要出發了！精品咖啡界的奧斯卡，我去當評審

你知道精品咖啡界有個「奧斯卡獎」嗎？
...
#COE #精品咖啡 #台灣代表 ...

──────────────────────────────────────────────────

=== 片段 2  00:01:30 → 00:02:00 ===
...
```

## Gotchas

- 需要 `OPENAI_API_KEY` 環境變數
- 使用 gpt-4o，每篇貼文約消耗 500–800 tokens
- 片段數量多時確認 API 額度

## Troubleshooting

| 問題 | 解法 |
|---|---|
| `ModuleNotFoundError: openai` | `pip install openai` |
| `AuthenticationError` | 確認 `OPENAI_API_KEY` 已設定且有效 |
| `output/ 中沒有找到 *_viral_segments.csv` | 先執行 `/run-viral-analyzer` |
