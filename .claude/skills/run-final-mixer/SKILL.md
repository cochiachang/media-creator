---
name: run-final-mixer
description: 讀取 output/clips/ 影片和 output/music/ 的 v1 音樂，用 ffmpeg 疊入背景音樂（保留原聲），輸出最終影片至 output/final/。Run, mix, final, ffmpeg, bgm, 混音, 背景音樂, 最終輸出
---

# 最終混音器

讀取 `output/clips/*.mp4`，為每支影片找到對應的 `output/music/segment_<n>_v1.mp3`，用 ffmpeg 混音（原聲 100% + BGM 15%），輸出至 `output/final/`。

Driver：`.claude/skills/run-final-mixer/driver.py`
Input：`output/clips/*.mp4` + `output/music/*_v1.mp3`
Output：`output/final/*.mp4`

## Prerequisites

```bash
brew install ffmpeg
```

## Run

```bash
python3 .claude/skills/run-final-mixer/driver.py
```

## 音量設定

| 軌道 | 預設音量 | 說明 |
|---|---|---|
| 原始聲音 | 100% | `ORIGINAL_VOLUME = 1.5` |
| 背景音樂 | 10% | `BGM_VOLUME = 0.1` |

若需調整，修改 driver.py 頂部的常數即可。

## 對應規則

`clip_01_*.mp4` → `segment_1_v1.mp3`（取 clip 編號去掉前導零）
找不到對應時自動 fallback 至第一個可用的 `*_v1.mp3`。

## Troubleshooting

| 問題 | 解法 |
|---|---|
| `找不到 ffmpeg` | `brew install ffmpeg` |
| `output/clips/ 沒有 .mp4` | 先執行 `/run-clip-cutter` |
| `output/music/ 沒有 *_v1.mp3` | 先執行 `/run-music-generator` |
