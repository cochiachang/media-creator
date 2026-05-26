---
name: run-viral-storyboard
description: 呼叫 GPT-5.5 根據爆紅分析 CSV、SRT 字幕、短影音方法論，設計 30-60 秒短影音完整分鏡腳本，含前3秒勾子視覺設計、逐秒截圖、每段轉場提詞、CTA 片尾，輸出為 JSON。Storyboard, 分鏡, hook, 勾子, 短影音設計, JSON, gpt-5.5
---

# 短影音分鏡設計師

讀取 `output/*_viral_segments.csv` 和 `.srt` 字幕，結合 `短影音爆紅入門全攻略.md` 方法論，呼叫 **GPT-5.5**（`gpt-5.5-2026-04-23`）設計一支 30-60 秒短影音完整分鏡腳本。自動對最高爆紅評分片段做逐秒截圖，輸出包含前3秒勾子、轉場設計、CTA 片尾的完整 JSON 報告。

Driver：`.claude/skills/run-viral-storyboard/driver.py`
Input：`output/*_viral_segments.csv`、`output/*.srt`、`upload/*.mp4`（可選）
Output：`output/<filename>_storyboard.json`、`output/storyboard_screenshots/`

## Prerequisites

```bash
pip install openai
export OPENAI_API_KEY=<your-key>
```

## Run

```bash
python3 .claude/skills/run-viral-storyboard/driver.py
```

若 `output/` 有多個 CSV 或 SRT，互動選擇。

## 互動步驟

1. 確認 CSV / SRT / 影片來源（多個則互動選擇）
2. 詢問使用者：**片尾 CTA 是什麼？**（追蹤帳號 / 點擊連結 / 留言互動等）
3. 讀取 CSV、SRT、爆紅方法論
4. 用 ffmpeg 對 CSV 中**爆紅評分最高的片段**做逐秒截圖（`storyboard_screenshots/hook_XX.jpg`）
5. 呼叫 `gpt-5.5-2026-04-23`，設計完整分鏡腳本（30-60 秒）：
   - 前3秒勾子：畫面、文字疊加、旁白、構圖建議
   - 完整分鏡：依「勾子 → 情境交代 → 高潮揭露 → CTA」結構
   - 每個分鏡：來源片段、時間戳、視覺描述、字幕提詞、轉場方式
   - 片尾 CTA：引導畫面與語音設計
6. 對各分鏡節點用 ffmpeg 提取代表截圖
7. 組合所有資料輸出完整 JSON

## 分鏡設計原則（GPT 遵循）

| 敘事結構 | 時長建議 | 說明 |
|---|---|---|
| **前3秒勾子** | ≤3 秒 | 選最高爆紅評分片段，製造懸念或強烈情緒，阻止觀眾滑動 |
| **情境交代** | 5-10 秒 | 快速建立背景（人是誰、在做什麼） |
| **高潮揭露** | 15-30 秒 | 核心爆紅內容，最精華的 1-2 個片段 |
| **額外亮點** | 5-10 秒 | 補充有趣細節，維持觀看張力 |
| **片尾 CTA** | 3-5 秒 | 使用者指定行動，設計明確引導畫面 |

## JSON 輸出格式

```json
{
  "meta": {
    "generated_at": "ISO timestamp",
    "source_srt": "filename.srt",
    "source_csv": "filename_viral_segments.csv",
    "model": "gpt-5.5-2026-04-23",
    "cta": "使用者提供的 CTA",
    "total_duration_seconds": 45,
    "narrative_strategy": "整體敘事策略說明"
  },
  "hook": {
    "source_segment": "片段2",
    "start_time": "00:00:08,200",
    "end_time": "00:00:11,000",
    "duration_seconds": 3,
    "visual": "畫面構圖描述",
    "text_overlay": "疊加文字（10字以內）",
    "voiceover": "旁白或原聲片段",
    "composition": "特寫",
    "screenshots": ["output/storyboard_screenshots/hook_01.jpg"],
    "design_rationale": "為何這3秒能留住觀眾"
  },
  "storyboard": [
    {
      "scene_number": 1,
      "label": "hook",
      "source_segment": "片段X",
      "start_time": "HH:MM:SS,mmm",
      "end_time": "HH:MM:SS,mmm",
      "duration_seconds": 3,
      "visual": "畫面描述",
      "text_overlay": "字幕/提詞",
      "voiceover": "旁白或原聲",
      "transition_in": "cut",
      "transition_out": "zoom",
      "screenshot": "output/storyboard_screenshots/scene_01.jpg",
      "viral_score": 9,
      "purpose": "此場景在整支影片中的作用"
    }
  ],
  "cta_scene": {
    "duration_seconds": 5,
    "visual": "畫面描述",
    "text_overlay": "CTA 文字",
    "voiceover": "引導語音",
    "cta_action": "具體行動指令"
  }
}
```

## Gotchas

- 需要 `OPENAI_API_KEY`（需有 `gpt-5.5-2026-04-23` 存取權限）
- `upload/` 需有影片才能執行截圖；無影片時跳過截圖，分鏡 JSON 仍正常輸出
- 先執行 `/run-viral-analyzer` 確保 CSV 已存在

## Troubleshooting

| 問題 | 解法 |
|---|---|
| `ModuleNotFoundError: openai` | `pip install openai` |
| `AuthenticationError` | 確認 `OPENAI_API_KEY` 有效且有 GPT-5.5 存取權限 |
| `output/ 找不到 CSV` | 先執行 `/run-viral-analyzer` |
| ffmpeg not found | `brew install ffmpeg` |
| JSON parse error | driver.py 有 fallback 解析機制，檢查 raw output 確認格式 |
