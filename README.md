# 短影音自動化製作工具

將一支長影片全自動剪輯成有爆紅潛力的短影音，並產出 AI 分鏡腳本、Facebook 貼文、CTA 片尾畫面與背景音樂。

---

## 快速開始

### 1. 環境準備

```bash
brew install ffmpeg node
pip install openai httpx gdown google-genai pillow
```

設定 API 金鑰：

```bash
export OPENAI_API_KEY=<your-openai-key>
export GEMINI_API_KEY=<your-gemini-key>    # Veo3 勾子生成（可選）
export SUNO_API_KEY=<your-sunoapi-key>     # 從 sunoapi.org 取得（可選）
```

### 2. 放入影片

**方法 A：手動放入**

將要處理的 `.mp4` 放入 `upload/` 資料夾：

```
upload/
└── your-video.mp4
```

**方法 B：從 Google Drive 下載**

```
/run-gdrive-download
```

貼上 Google Drive 分享連結，系統自動下載並存入 `upload/`。

### 3. 一鍵執行

在 Claude Code 中輸入：

```
/run-pipeline
```

系統會詢問兩個問題後全自動執行：
- **影片背景資訊**（主角、主題、品牌等）
- **CTA 目標**（追蹤粉專、購買產品、留言互動等）

完成後輸出封存於：

```
output-your-video/
├── your-video.srt                    # 字幕
├── your-video_viral_segments.csv     # 爆紅片段分析
├── your-video_storyboard.json        # AI 分鏡腳本
├── storyboard_cover.png              # DALL-E 封面圖
├── storyboard_screenshots/           # 分鏡截圖
├── cta_scene.png                     # CTA 片尾靜態畫面
├── clips/                            # 精華片段（含片頭）
├── posts/                            # Facebook 貼文
├── music/                            # 背景音樂
└── final/                            # 最終成品影片
```

---

## 完整流程

```
Google Drive 連結（可選）
    │
    ▼  /run-gdrive-download      從 Google Drive 下載影片
    │
upload/<video>.mp4
    │
    ▼  /run-transcribe           字幕轉錄（Whisper）
    │  output/<stem>.srt
    │
    ▼  /run-viral-analyzer       爆紅片段分析（GPT-4o）
    │  output/<stem>_viral_segments.csv
    │
    ▼  /run-viral-storyboard     AI 分鏡設計（GPT-5.5 + DALL-E 3）
    │  output/<stem>_storyboard.json
    │  output/storyboard_cover.png
    │  output/storyboard_screenshots/
    │
    ├─▶ /run-veo3-hook           AI 勾子影片生成（Google Veo3）[可選]
    │   output/veo3_hook_final.mp4
    │
    ├─▶ /run-cta-scene           CTA 片尾畫面生成（gpt-image-1 + TTS）[可選]
    │   output/cta_scene.png
    │   output/clips/cta_scene.mp4
    │
    ▼  /run-clip-cutter          剪輯精華片段（ffmpeg + 字幕燒錄）
    │  output/clips/scene_*.mp4
    │
    ▼  /run-add-intro            加入彈跳字幕片頭（Remotion）
    │  output/clips/scene_*.mp4（覆寫）
    │
    ▼  /run-fb-post-generator    生成 Facebook 貼文（GPT-4o）
    │  output/posts/segment_*.txt
    │
    ▼  /run-music-generator      生成背景音樂（Suno AI）
    │  output/music/segment_*_v1.mp3
    │
    ▼  /run-final-mixer          混音合併輸出（ffmpeg）
       output/final/*.mp4
```

---

## 分開呼叫

每個步驟都可以單獨執行，方便重跑某個環節或調整參數。

---

### `/run-gdrive-download`

從 Google Drive 分享連結下載影片，存入 `upload/`。

- **Input**：Google Drive 分享連結或 File ID
- **Output**：`upload/<filename>.<ext>`

```
/run-gdrive-download
```

> 支援 `/file/d/`、`?id=`、`uc?id=` 等所有常見 Google Drive 連結格式。檔案須設定為「知道連結的人皆可存取」。

---

### `/run-transcribe`

將影片轉錄成 SRT 字幕。

- **Input**：`upload/<file>.mp4`
- **Output**：`output/<file>.srt`

```
/run-transcribe
```

---

### `/run-viral-analyzer`

讀取字幕，分析所有潛力片段後只保留前 N 名輸出。

- **Input**：`output/<file>.srt`
- **Output**：`output/<file>_viral_segments.csv`（只含前 N 個片段）

```
/run-viral-analyzer
```

> 會詢問：要生成幾支短影音（N）、以及影片背景資訊。

---

### `/run-viral-storyboard`

讀取爆紅分析 CSV 與 SRT 字幕，呼叫 **GPT-5.5** 設計完整 30-60 秒分鏡腳本，並用 **DALL-E 3** 生成封面圖。

- **Input**：`output/<file>_viral_segments.csv`、`output/<file>.srt`、`upload/*.mp4`（截圖用）
- **Output**：`output/<file>_storyboard.json`、`output/storyboard_cover.png`、`output/storyboard_screenshots/`

```
/run-viral-storyboard
```

> 分鏡包含：前3秒勾子設計、逐幕視覺描述、轉場方式、CTA 片尾結構。

| 敘事結構 | 時長建議 | 說明 |
|---|---|---|
| **前3秒勾子** | ≤3 秒 | 製造懸念或強烈情緒，阻止觀眾滑動 |
| **情境交代** | 5-10 秒 | 快速建立背景（人是誰、在做什麼） |
| **高潮揭露** | 15-30 秒 | 核心爆紅內容，最精華的 1-2 個片段 |
| **額外亮點** | 5-10 秒 | 補充有趣細節，維持觀看張力 |
| **片尾 CTA** | 3-5 秒 | 明確行動引導 |

---

### `/run-veo3-hook`

讀取分鏡 JSON 的 hook 區塊，呼叫 **Google Veo3** 以 image-to-video 模式生成 AI 勾子短片，產出 3 個版本供選擇。

- **Input**：`output/*_storyboard.json`、`output/storyboard_screenshots/hook_*.jpg`
- **Output**：`output/veo3_hook_final.mp4`、`output/veo3_hook_v1~v3.mp4`

```
/run-veo3-hook
```

> 需設定 `GEMINI_API_KEY`，並開通 `veo-3.0-generate-preview` 存取權限。渲染約需 2-5 分鐘。

---

### `/run-cta-scene`

讀取分鏡 JSON 的 `cta_scene` 區塊，對來源影片截圖後傳給 **gpt-image-1** 生成片尾靜態畫面，並合成 TTS 旁白，輸出 5 秒 CTA 片尾影片。

- **Input**：`output/*_storyboard.json`、`upload/*.mp4`
- **Output**：`output/cta_scene.png`、`output/cta_scene_tts.mp3`、`output/clips/cta_scene.mp4`

```
/run-cta-scene
```

> 需先執行 `/run-viral-storyboard`。`cta_scene.mp4` 可直接被 `/run-final-mixer` 接入。

---

### `/run-clip-cutter`

依據 CSV 的時間戳剪出片段，並燒錄對應字幕，輸出至 `output/clips/`（不含片頭）。

- **Input**：`output/<file>_viral_segments.csv`
- **Output**：`output/clips/scene_*.mp4`

```
/run-clip-cutter
```

---

### `/run-add-intro`

為每支片段用 **Remotion** 渲染彈跳字幕片頭，合併後覆寫原片段。

- **Input**：`output/clips/*.mp4` + `output/*_viral_segments.csv`
- **Output**：覆寫 `output/clips/*.mp4`（加上片頭）

```
/run-add-intro
```

> 片頭：深藍紫漸層主題、字元逐一彈跳入場，時長依標題長度自動計算（2-4 秒）。首次執行自動安裝 npm 依賴（約 1-3 分鐘）。

---

### `/run-burn-subtitle`

將 `upload/` 的影片燒入 `output/` 的 SRT 字幕，輸出含硬字幕的影片。

- **Input**：`upload/<video>.*` + `output/<video>.srt`
- **Output**：`output/<video>.mp4`

```
/run-burn-subtitle
```

> 白字黑邊、微軟正黑體、畫面下方置中。影片名稱與 SRT 名稱相同時自動配對。

---

### `/run-fb-post-generator`

為每個片段生成一篇自然口吻的繁中 Facebook 貼文。

- **Input**：`output/<file>_viral_segments.csv`
- **Output**：`output/posts/segment_N.txt`

```
/run-fb-post-generator
```

---

### `/run-music-generator`

讀取貼文內容，用 GPT-4o 生成 Suno prompt，呼叫 Suno API 生成背景音樂，每個片段產生 2 個版本。

- **Input**：`output/posts/segment_N.txt`
- **Output**：`output/music/segment_N_v1.mp3`、`segment_N_v2.mp3`

```
/run-music-generator
```

> 需設定 `SUNO_API_KEY`。生成約需 30–60 秒。

---

### `/run-final-mixer`

從 `scene_00` 開始依序合併所有場景片段，自動附加 `cta_scene.mp4` 片尾（若存在），再疊入背景音樂（原聲 100% + BGM 15%），輸出最終成品。

- **Input**：`output/clips/scene_*.mp4` + `output/music/*_v1.mp3`
- **Output**：`output/final/*.mp4`

```
/run-final-mixer
```

> 背景音量可在 [.claude/skills/run-final-mixer/driver.py](.claude/skills/run-final-mixer/driver.py) 頂部調整 `BGM_VOLUME`。

---

## 常見問題

| 問題 | 解法 |
|---|---|
| `ffmpeg: command not found` | `brew install ffmpeg` |
| `node: command not found` | `brew install node` |
| `ModuleNotFoundError: gdown` | `pip install gdown` |
| `ModuleNotFoundError: google.genai` | `pip install google-genai` |
| `ModuleNotFoundError: PIL` | `pip install pillow` |
| Google Drive 下載失敗 | 確認分享設定為「知道連結的人皆可存取」 |
| `OPENAI_API_KEY 未設定` | `export OPENAI_API_KEY=<key>` |
| `SUNO_API_KEY 未設定` | `export SUNO_API_KEY=<key>`，金鑰至 sunoapi.org 取得 |
| `GEMINI_API_KEY 未設定` | `export GEMINI_API_KEY=<key>`，至 Google AI Studio 取得 |
| Veo3 403 / permission denied | 確認帳號已開通 `veo-3.0-generate-preview` 存取權 |
| Veo3 渲染中請耐心等待 | 渲染約需 2-5 分鐘，正常現象 |
| gpt-image-1 無存取權限 | 確認 OpenAI 帳號已開通 gpt-image-1 |
| Suno credits 不足 | 至 sunoapi.org 帳號頁面儲值 |
| 影片超過 25MB（Whisper 限制） | 用 ffmpeg 切段：`ffmpeg -i input.mp4 -t 600 part1.mp4 -ss 600 part2.mp4` |
| 中文字幕顯示方塊 | 確認 `微軟正黑體.ttf` 在 `.claude/skills/run-clip-cutter/` |

---

## 參考資料

- [短影音爆紅入門全攻略.md](短影音爆紅入門全攻略.md) — 爆紅判斷方法論
