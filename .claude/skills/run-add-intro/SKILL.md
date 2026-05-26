---
name: run-add-intro
description: 讀取 output/clips/ 的剪輯片段與 CSV 建議標題，用 Remotion 生成彈跳字幕片頭，合併後覆寫原片段。Run, intro, remotion, 片頭, 彈跳字幕, 合併, merge
---

# 片頭合併器

讀取 `output/clips/*.mp4` 與 `output/*_viral_segments.csv` 的建議標題，為每支片段：

1. 用 **Remotion（intro-video 技能）** 依標題渲染彈跳字幕片頭 MP4
2. 合併片頭 + 片段，**覆寫**原 `output/clips/clip_XX_*.mp4`

通常在 `/run-clip-cutter` 之後執行，之後再跑 `/run-final-mixer`。

Driver：`.claude/skills/run-add-intro/driver.py`  
Remotion 專案：`.claude/skills/run-add-intro/intro-remotion/`  
Input：`output/clips/*.mp4` + `output/*_viral_segments.csv`  
Output：覆寫 `output/clips/*.mp4`（加上片頭）

## Prerequisites

```bash
brew install ffmpeg
brew install node
```

> **首次執行**：自動在 `intro-remotion/` 執行 `npm install`（約 1–3 分鐘）。

## Run

```bash
python3 .claude/skills/run-add-intro/driver.py
```

## 片頭規格

- 引擎：Remotion（`intro-remotion/src/IntroVideo.tsx`）
- 主題：`dark`（深藍紫漸層＋光暈脈動）
- 字幕動畫：每個字元依序彈跳入場（playful overshoot）
- 時長：依文字量自動計算（約 2–4 秒）＋靜止 1 秒
- 解析度：自動對應各片段解析度
- 字型：PingFang TC → Noto Sans TC → Microsoft JhengHei（CSS fallback）

## Troubleshooting

| 問題 | 解法 |
|---|---|
| `node: command not found` | `brew install node` |
| `找不到 output/clips/*.mp4` | 先執行 `/run-clip-cutter` |
| `找不到 *_viral_segments.csv` | 先執行 `/run-viral-analyzer` |
| Remotion 渲染失敗 | 確認 `intro-remotion/src/IntroVideo.tsx` 存在且完整 |
