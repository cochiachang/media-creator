---
name: run-cta-scene
description: 讀取 output/*_storyboard.json 的 cta_scene 區塊，用 ffmpeg 每秒截一張圖，傳給 OpenAI gpt-image-1 生成吸引人的短影音片尾靜態畫面，並疊上 voiceover CTA 文字，輸出為 PNG。CTA, 片尾, end screen, call to action, gpt-image-1, 靜態畫面, short video ending
---

# CTA 片尾靜態畫面生成器

讀取 `output/*_storyboard.json` 的 `cta_scene` 區塊，對來源影片的 `start_time`～`end_time` 片段用 **ffmpeg 每秒截一張圖**，全部傳給 **OpenAI gpt-image-1**（image edit 模式），生成一張吸引人的短影音片尾靜態畫面，並用 Pillow 疊上 `voiceover` 的 CTA 文字，最終輸出 `output/cta_scene.png`。

Driver：`.claude/skills/run-cta-scene/driver.py`
Input：`output/*_storyboard.json`、`upload/*.mp4`
Output：`output/cta_scene.png`、`output/cta_scene_tts.mp3`、`output/clips/cta_scene.mp4`（5秒片尾影片）、`output/cta_scene_frames/`（截圖暫存）

## Prerequisites

```bash
pip install openai pillow
brew install ffmpeg
export OPENAI_API_KEY=<your-key>
```

## Run

```bash
python3 .claude/skills/run-cta-scene/driver.py
```

若 `output/` 有多個 storyboard JSON，互動選擇。

## 執行流程

1. **找 storyboard JSON** — 掃描 `output/*_storyboard.json`，多個則互動選擇
2. **讀取 cta_scene** — 取出 `start_time`、`end_time`、`voiceover`、`text_overlay`、`visual`、`cta_action`
3. **找來源影片** — 掃描 `upload/*.mp4`，多個則互動選擇
4. **ffmpeg 截圖** — 從 `start_time` 到 `end_time`，每秒截一張（`output/cta_scene_frames/frame_XX.jpg`）
5. **gpt-image-1 生成** — 將所有截圖傳入 `images.edit()`，prompt 包含：
   - 短影音片尾風格（9:16 垂直、視覺衝擊強）
   - 從影片截圖中汲取色調、氛圍、風格
   - CTA 行動指令（`cta_action`）與引導語（`voiceover`）
   - 要求畫面包含醒目的 CTA 文字區域（大字、高對比）
6. **Pillow 疊字** — 在生成圖片下方疊入 `voiceover` 文字（白字黑邊，大字）
7. **TTS 旁白** — 用 `tts-1-hd` / `nova` / `1.25x` 生成 `voiceover` 旁白 MP3（`output/cta_scene_tts.mp3`）
8. **合成影片** — ffmpeg 將靜態 PNG + TTS MP3 合成 **5 秒 H.264 影片**，輸出至 `output/clips/cta_scene.mp4`
9. **完成摘要** — 列出所有輸出檔案路徑與大小

## 輸出檔案

| 檔案 | 說明 |
|---|---|
| `output/cta_scene.png` | 最終片尾靜態畫面（1024×1792） |
| `output/cta_scene_tts.mp3` | voiceover CTA 旁白音訊（nova, 1.25x） |
| `output/clips/cta_scene.mp4` | **5 秒 H.264 片尾影片**（PNG＋TTS 合成，yuv420p，可直接接 run-final-mixer） |
| `output/cta_scene_frames/` | ffmpeg 截圖暫存資料夾 |

## Gotchas

- `cta_scene.start_time` 與 `end_time` 若區間 < 1 秒，會至少截一張（起始幀）
- gpt-image-1 `images.edit()` 最多支援 16 張參考圖；超過時自動取均勻分佈的 16 張
- 需要 `OPENAI_API_KEY`（需有 gpt-image-1 存取權）
- Pillow 疊字使用系統中文字體（PingFang / STHeiti）；找不到時改用 Pillow 預設字體

## Troubleshooting

| 問題 | 解法 |
|---|---|
| `ModuleNotFoundError: openai` | `pip install openai` |
| `ModuleNotFoundError: PIL` | `pip install pillow` |
| `ffmpeg not found` | `brew install ffmpeg` |
| `AuthenticationError` | 確認 `OPENAI_API_KEY` 有效且有 gpt-image-1 存取權 |
| `output/ 找不到 storyboard` | 先執行 `/run-viral-storyboard` |
| `upload/ 找不到影片` | 將 .mp4 放入 `upload/`，或執行 `/run-gdrive-download` |
| cta_scene 截圖為全黑 | 確認影片時間戳格式正確（`HH:MM:SS,mmm`） |
