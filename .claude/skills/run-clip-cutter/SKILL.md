---
name: run-clip-cutter
description: 讀取 output/ 的 CSV 時間戳，用 ffmpeg 剪出短片段，並製作帶有彈出字幕特效的3秒片頭。Run, cut, clip, ffmpeg, subtitle, intro, 剪輯, 字幕, 片頭, 短片段
---

# 精華短片剪輯器

讀取 `output/*_viral_segments.csv` 的時間戳與建議標題，為每個片段：

1. 製作 **3 秒黑底片頭**：標題置中，微軟正黑體 32px，彈出動畫（0.5 秒彈入）
2. **剪輯原始片段**（無疊字）
3. 合併片頭 + 片段，輸出至 `output/clips/`

Driver：`.claude/skills/run-clip-cutter/driver.py`
Font：`.claude/skills/run-clip-cutter/微軟正黑體.ttf`（已內建）
Input：`output/*_viral_segments.csv` + `upload/<video>.*`
Output：`output/clips/clip_<序號>_<起始時間>.mp4`

## Prerequisites

```bash
brew install ffmpeg
```

## Run

```bash
python3 .claude/skills/run-clip-cutter/driver.py
```

若 `output/` 有多個 CSV，互動選擇。單一 CSV 自動執行。

## 片頭規格

- 時長：3 秒，黑底
- 字型：`.claude/skills/run-clip-cutter/微軟正黑體.ttf`（內建，優先）→ PingFang TC → STHeiti
- 字級：32px，白字＋半透明黑底框
- 位置：畫面正中央（`x=(w-tw)/2, y=(h-th)/2`）
- 彈出動畫：0→120%（前 0.3s 線性放大）→ 100%（後 0.2s 縮回），共 0.5s
- 自動斷行：左右各留 60px 空間，超過寬度自動換行（CJK 字元算 1 單位，ASCII 算 0.5）

## Gotchas

- **時間精度**：`-ss` 在 B-frame 影片上可能有 ±1 秒誤差。
- **`-t` vs `-to`**：使用 `-t duration` 而非 `-to end`，避免 input-seek 模式下 `-to` 從輸出起算造成片段過長。
- **斷行轉義**：`escape_drawtext()` 先 split `\n` 再各段轉義後 rejoin，避免轉義 `\` 後 `\n` 變成 `\\n` 導致斷行失效。
- **無音訊片段**：若原始影片無音訊軌，driver 自動補靜音軌以維持 concat 相容性。

## Troubleshooting

| 問題 | 解法 |
|---|---|
| `ffmpeg: command not found` | `brew install ffmpeg` |
| 中文字亂碼 / 方框 | 確認 `微軟正黑體.ttf` 在 skill 目錄；或 `fc-list :lang=zh-tw \| grep PingFang` |
| `output/ 中沒有找到 *_viral_segments.csv` | 先執行 `/run-viral-analyzer` |
| 找不到原始影片 | 確認 `upload/` 內有與 CSV 同名的影片檔 |
| `concat` 失敗（音訊流不符） | 檢查兩段影片的 sample rate 是否一致；driver 片頭固定用 44100 Hz |
