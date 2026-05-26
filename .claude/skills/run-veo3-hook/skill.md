---
name: run-veo3-hook
description: 讀取 output/*_storyboard.json 的 hook 區塊與截圖，呼叫 Google Veo3（veo-3.0-generate-preview）以 image-to-video 模式生成前3秒勾子短片。自動選取中間參考幀、組合英文 prompt、生成 3 個版本供選擇，輸出 output/veo3_hook_final.mp4。Veo3, hook, 勾子, video generation, image-to-video, 短影音, 前3秒, 生成影片
---

# run-veo3-hook

讀取 `output/*_storyboard.json` 的 hook 區塊與截圖，呼叫 **Google Veo3**（`veo-3.0-generate-preview`）以 image-to-video 模式生成前3秒勾子短片。自動選取中間參考幀、組合英文 prompt、生成 3 個版本供選擇，輸出 `output/veo3_hook_final.mp4`。

Driver：`.claude/skills/run-veo3-hook/driver.py`
Input：`output/*_storyboard.json`、`output/storyboard_screenshots/hook_*.jpg`
Output：`output/veo3_hook_final.mp4`、`output/veo3_hook_v1~v3.mp4`

## Prerequisites

```bash
pip install google-genai
export GEMINI_API_KEY=<your-key>
```

Veo3 需要 Google AI Studio API key，且帳號需開通 `veo-3.0-generate-preview` 存取權限。

## Run

```bash
python3 .claude/skills/run-veo3-hook/driver.py
```

## 執行流程

1. 讀取 `output/*_storyboard.json` 的 `hook` 區塊
2. 從 `hook.screenshots` 選取中間幀作為 image reference
3. 將 hook.visual / hook.composition / hook.voiceover / hook.design_rationale 組合成英文 Veo3 prompt
4. 呼叫 `veo-3.0-generate-preview`（image-to-video，`generate_audio=True`）
5. 輪詢等待渲染（約 2-5 分鐘）
6. 下載 3 個版本 → `output/veo3_hook_v1~v3.mp4`
7. 用 ffmpeg 裁剪到 `hook.duration_seconds`（通常 3s）
8. 互動選擇最終版本 → `output/veo3_hook_final.mp4`

## Veo3 Prompt 組合邏輯

| hook 欄位 | 轉換方式 |
|---|---|
| `visual` | 直接描述畫面構圖與動作 |
| `composition` | 特寫→close-up，中景→medium shot |
| `voiceover` | 轉為 audio direction（情緒方向，非逐字翻譯） |
| `design_rationale` | 加入 "Design intent:" 段落，引導 Veo3 理解停留目的 |

## 注意事項

- Veo3 最短影片為 5 秒，腳本自動用 ffmpeg 裁剪到 hook 指定時長
- `generate_audio=True`：Veo3 自行生成環境音與語音，不使用原片聲音
- image-to-video 若 API key 不支援，自動 fallback 為純文字 text-to-video
- 渲染時間約 2-5 分鐘，請耐心等待

## 與整體 Pipeline 的關係

```
run-viral-storyboard
    ↓ (storyboard.json + hook screenshots)
run-veo3-hook → output/veo3_hook_final.mp4
    ↓
run-storyboard-assembler（待開發）
    合併 veo3_hook_final.mp4 + 其他場景剪輯片段
    ↓
output/final/<name>_assembled.mp4
```

## Troubleshooting

| 問題 | 解法 |
|---|---|
| `ModuleNotFoundError: google.genai` | `pip install google-genai` |
| `permission denied` / 403 | 確認 API key 有 Veo3 存取權（需申請） |
| `image not supported` | 自動 fallback 純文字；或確認帳號支援 image-to-video |
| 影片全黑 / 品質差 | 嘗試其他版本，或調整 `enhance_prompt=True` |
| 下載失敗 | 檢查 google-genai SDK 版本，確認 `>= 2.0` |
