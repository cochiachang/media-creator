---
name: run-final-mixer
description: 從 scene_00 開始，依數字順序合併 output/clips/ 所有 scene 影片，自動附加 cta_scene.mp4 片尾（若存在），再用 ffmpeg 疊入背景音樂（保留原聲），輸出最終影片至 output/final/。Run, mix, final, ffmpeg, bgm, 混音, 背景音樂, 最終輸出, 合併, concat, scene, cta
---

# 最終混音器

從 `scene_00` 開始，將 `output/clips/scene_*.mp4` 依數字順序全部合併，**自動附加 `output/clips/cta_scene.mp4`（CTA 片尾，若存在）**，再疊入 `output/music/*_v1.mp3` 背景音樂，輸出至 `output/final/`。

Driver：`.claude/skills/run-final-mixer/driver.py`
Input：`output/clips/scene_*.mp4` + `output/clips/cta_scene.mp4`（選用）+ `output/music/*_v1.mp3`
Output：`output/final/merged_scenes.mp4`（純合併）、`output/final/merged_scenes_final.mp4`（含 BGM）

## Prerequisites

```bash
brew install ffmpeg
```

## Run

```bash
python3 .claude/skills/run-final-mixer/driver.py
```

## 流程

| 步驟 | 說明 |
|---|---|
| Step 1 | 收集 `scene_00.mp4`、`scene_01.mp4`、… 依數字從小到大排序；若 `cta_scene.mp4` 存在，自動附加於最後 |
| Step 2 | ffmpeg filter_complex concat 合併 → `merged_scenes.mp4`（重新編碼，正確處理時間戳） |
| Step 3 | 疊入第一個 `*_v1.mp3` 作為 BGM → `merged_scenes_final.mp4` |

## 音量設定

| 軌道 | 預設音量 | 說明 |
|---|---|---|
| 原始聲音 | 150% | `ORIGINAL_VOLUME = 1.5` |
| 背景音樂 | 20% | `BGM_VOLUME = 0.2` |

若需調整，修改 driver.py 頂部的常數即可。

## Troubleshooting

| 問題 | 解法 |
|---|---|
| `找不到 ffmpeg` | `brew install ffmpeg` |
| `output/clips/ 沒有 scene_*.mp4` | 確認 clips 目錄有 scene_00.mp4 等檔案 |
| `output/music/ 沒有 *_v1.mp3` | 先執行 `/run-music-generator` 產生音樂 |
| 想加 CTA 片尾但找不到 | 先執行 `/run-cta-scene` 產生 `output/clips/cta_scene.mp4` |
| 合併失敗（codec 不相容）| 確認所有 scene 影片格式一致（同解析度、幀率、編碼） |
