---
name: run-burn-subtitle
description: 將 upload/ 的影片燒入 output/ 的 SRT 字幕，輸出含燒錄字幕的影片至 output/。Burn, subtitle, SRT, 字幕, 燒錄字幕, hardcode, embed subtitle
---

# 字幕燒錄器

讀取 `upload/` 的影片與 `output/` 的 `.srt` 字幕，用 ffmpeg `subtitles` filter 將字幕硬燒進影片，輸出至 `output/<影片名稱>_subtitled.mp4`。

Driver：`.claude/skills/run-burn-subtitle/driver.py`
Font：`.claude/skills/run-clip-cutter/微軟正黑體.ttf`（共用，已內建）
Input：`upload/<video>.*` + `output/<video>.srt`
Output：`output/<video>_subtitled.mp4`

## Prerequisites

```bash
# macOS
brew install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg
```

## Run

```bash
python3 .claude/skills/run-burn-subtitle/driver.py
```

- 若 `upload/` 和 `output/` 各只有一個影片 / SRT，自動執行。
- 若有多個檔案，或無法自動配對，會互動詢問。
- 影片名稱與 SRT 名稱相同時（如 `foo.mp4` + `foo.srt`）自動配對，無需手動選擇。

## 字幕規格

| 設定 | 值 |
|---|---|
| 字型 | Microsoft JhengHei（微軟正黑體）→ 系統預設 |
| 字級 | 16px |
| 顏色 | 白字 + 黑色外框（Outline=2） |
| 位置 | 畫面下方置中（Alignment=2，MarginV=30） |

## Gotchas

- **路徑轉義**：Windows 磁碟代號冒號（`C:`）在 ffmpeg filter 字串中須轉義。driver 已自動處理，透過將 SRT 複製至無特殊字元的暫存目錄繞過。
- **字型辨識**：`fontsdir` 指向 `.claude/skills/run-clip-cutter/`，ffmpeg/libass 從中載入字型；`FontName=Microsoft JhengHei` 對應 `微軟正黑體.ttf` 的內部名稱。
- **無音訊影片**：driver 自動偵測，無音訊時改用 `-an`，避免 `copy` 音訊失敗。
- **重新編碼**：影片串流會重新編碼為 H.264（libx264 fast preset），音訊直接 copy，不影響音質。

## Troubleshooting

| 問題 | 解法 |
|---|---|
| `ffmpeg: command not found` | `brew install ffmpeg` 或 `choco install ffmpeg` |
| 中文字幕顯示方塊 | 確認 `微軟正黑體.ttf` 在 `.claude/skills/run-clip-cutter/` |
| `output/ 中找不到 .srt` | 先執行 `/run-transcribe` 產生字幕 |
| `upload/ 中找不到影片` | 確認影片已放入 `upload/` 資料夾 |
| ffmpeg 回報 filter 語法錯誤 | 確認 ffmpeg 版本支援 libass（`ffmpeg -version` 查看 `--enable-libass`） |
