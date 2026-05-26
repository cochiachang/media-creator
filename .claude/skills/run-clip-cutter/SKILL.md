---
name: run-clip-cutter
description: 讀取 output/ 的 CSV 時間戳，用 ffmpeg 剪出短片段並燒錄對應字幕，輸出至 output/clips/（不含片頭，片頭請另行執行 run-add-intro）。Run, cut, clip, ffmpeg, subtitle, 剪輯, 字幕, 短片段
---

# 精華短片剪輯器

讀取 `output/*_viral_segments.csv` 的時間戳與建議標題，為每個片段：

1. 呼叫 **intro-video 技能（Remotion）**：依標題產生彈跳字幕片頭 MP4
2. **剪輯原始片段**（含降噪，無疊字）
3. 合併片頭 + 片段，輸出至 `output/clips/`

Driver：`.claude/skills/run-clip-cutter/driver.py`  
Remotion 專案：`.claude/skills/run-clip-cutter/intro-remotion/`  
Input：`output/*_viral_segments.csv` + `output/<video>.*`（若 output/ 無影片則自動從 upload/ 複製）  
Output：`output/clips/clip_<序號>_<起始時間>.mp4`

## Prerequisites

```bash
brew install ffmpeg
brew install node   # Node.js + npm（供 Remotion 使用）
```

> **首次執行**：driver.py 會自動在 `intro-remotion/` 執行 `npm install` 安裝 Remotion，約需 1–3 分鐘。後續執行無需重複安裝。

## Run

```bash
python3 .claude/skills/run-clip-cutter/driver.py
```

若 `output/` 有多個 CSV，互動選擇。單一 CSV 自動執行。

## 片頭規格（Remotion / intro-video 技能）

- 引擎：**Remotion**（`intro-remotion/src/IntroVideo.tsx`）
- 時長：依標題文字量自動計算（約 2–4 秒），靜止展示 1 秒
- 背景主題：`dark`（深藍紫漸層 + 光暈脈動），可在 `driver.py` 的 `create_intro_remotion()` 修改 `theme` 參數
- 字幕動畫：每個字元依序彈跳入場（playful overshoot 效果）
- 多彩字幕：各字元自動循環彩色（金、粉、青等）
- 解析度：自動對應來源影片解析度（video_w × video_h）
- 字型大小：依解析度自動縮放（`min(video_w, video_h) // 15`，48–96px）
- 字型：PingFang TC → Noto Sans TC → Microsoft JhengHei（CSS fallback，無需手動指定字型檔）
- 自動斷行：標題超過 13 字時自動拆成 2 行，超過 26 字拆成 3 行，優先在標點/空白處斷行
- 音軌：渲染後由 ffmpeg 補入靜音立體聲軌（44100 Hz stereo aac），確保 concat 相容

## Gotchas

- **時間精度**：`-ss` 在 B-frame 影片上可能有 ±1 秒誤差。
- **`-t` vs `-to`**：使用 `-t duration` 而非 `-to end`，避免 input-seek 模式下 `-to` 從輸出起算造成片段過長。
- **首次安裝**：`npm install` 需要網路，並會在 `intro-remotion/node_modules/` 下載約 200–400 MB 的套件。
- **無音訊片段**：若原始影片無音訊軌，driver 自動補靜音軌以維持 concat 相容性。
- **Root.tsx 自動覆寫**：每次執行片段前，`intro-remotion/src/Root.tsx` 會被 driver 動態覆寫，請勿手動修改。

## Troubleshooting

| 問題 | 解法 |
|---|---|
| `ffmpeg: command not found` | `brew install ffmpeg` |
| `node: command not found` | `brew install node` |
| `output/ 中沒有找到 *_viral_segments.csv` | 先執行 `/run-viral-analyzer` |
| 找不到原始影片 | 確認 `output/` 或 `upload/` 內有與 CSV 同名的影片檔 |
| npm install 失敗 | 確認網路可用；或手動 `cd intro-remotion && npm install` |
| Remotion 渲染失敗（TSX 錯誤） | 確認 `intro-remotion/src/IntroVideo.tsx` 存在且完整（從 intro-video 技能重新複製） |
| Remotion 渲染失敗（字型問題） | macOS 應已內建 PingFang TC，可忽略；其他系統請安裝 Noto Sans CJK |
| `concat` 失敗（音訊流不符） | 檢查兩段影片的 sample rate；driver 片頭固定用 44100 Hz |
