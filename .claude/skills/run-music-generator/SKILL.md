---
name: run-music-generator
description: 讀取 output/posts/ 的 TXT 貼文，用 GPT-4o 生成 Suno prompt，再呼叫 Suno API 生成背景音樂 MP3。Run, music, generate, Suno, 音樂, 生成, 背景音樂, BGM
---

# 音樂生成器

讀取 `output/posts/*.txt`，為每個貼文用 GPT-4o 分析氛圍並生成 Suno AI prompt，呼叫 Suno API 生成短影音背景音樂，輸出為 `output/music/<segment>.mp3`。

Driver：`.claude/skills/run-music-generator/driver.py`
Input：`output/posts/*.txt`
Output：`output/music/<stem>.mp3`

## Prerequisites

```bash
pip install openai httpx
export OPENAI_API_KEY=<your-openai-key>
export SUNO_API_KEY=<your-suno-key>
```

Suno API key 取得：https://suno.com → 帳號設定 → API Keys

## Run

```bash
python3 .claude/skills/run-music-generator/driver.py
```

所有 `output/posts/` 內的 TXT 一次全部處理。

## 輸出範例

```
找到 3 個貼文，開始生成音樂…

[segment_1]
      生成 Suno prompt…
      風格：acoustic, upbeat, indie pop
      標題：台灣咖啡的驕傲
      Prompt：Upbeat acoustic indie pop with light guitar...
      等待 Suno 生成.......... 完成
      ✓ 已儲存至 output/music/segment_1.mp3
```

## Gotchas

- Suno 生成通常需要 60–120 秒，請耐心等待
- `make_instrumental=True`：純音樂，無人聲（適合短影音背景）
- 每首音樂約消耗 Suno 積分，確認帳號額度

## Troubleshooting

| 問題 | 解法 |
|---|---|
| `ModuleNotFoundError: httpx` | `pip install httpx` |
| `SUNO_API_KEY 未設定` | `export SUNO_API_KEY=<key>` |
| Suno API 401 | 確認 API key 有效，且帳號有足夠積分 |
| `output/posts/ 中沒有找到 .txt` | 先執行 `/run-fb-post-generator` |
