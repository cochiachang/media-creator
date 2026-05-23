# 短影音自動化製作工具

將一支長影片自動剪輯成有爆紅潛力的短影音，並產出 Facebook 貼文與背景音樂。

---

## 快速開始

### 1. 環境準備

```bash
brew install ffmpeg
pip install openai httpx gdown
```

設定 API 金鑰：

```bash
export OPENAI_API_KEY=<your-openai-key>
export SUNO_API_KEY=<your-sunoapi-key>   # 從 sunoapi.org 取得
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
- **要生成幾支短影音？**（輸入數字，預設 3）
- **影片背景資訊**（主角、主題、品牌等）完成後輸出封存於：

```
output-your-video/
├── your-video.srt               # 字幕
├── your-video_viral_segments.csv  # 爆紅片段分析
├── clips/                       # 精華片段
├── posts/                       # Facebook 貼文
├── music/                       # 背景音樂
└── final/                       # 最終成品影片
```

---

## 完整流程

```
Google Drive 連結（可選）
    │
    ▼  /run-gdrive-download   從 Google Drive 下載影片
    │
upload/<video>.mp4
    │
    ▼  /run-transcribe        字幕轉錄（Whisper）
    │  output/<stem>.srt
    │
    ▼  /run-viral-analyzer    爆紅片段分析（GPT-4o）
    │  output/<stem>_viral_segments.csv
    │
    ▼  /run-clip-cutter       剪輯精華片段（ffmpeg）
    │  output/clips/*.mp4
    │
    ▼  /run-fb-post-generator  生成 Facebook 貼文（GPT-4o）
    │  output/posts/segment_*.txt
    │
    ▼  /run-music-generator   生成背景音樂（Suno AI）
    │  output/music/segment_*_v1.mp3
    │
    ▼  /run-final-mixer       混音輸出（ffmpeg）
       output/final/*.mp4
```

---

## 分開呼叫

每個步驟都可以單獨執行，方便重跑某個環節或調整參數。

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

### `/run-clip-cutter`

依據 CSV 的時間戳剪出片段，並加上 3 秒彈出字幕片頭。

- **Input**：`output/<file>_viral_segments.csv`
- **Output**：`output/clips/clip_0N_*.mp4`

```
/run-clip-cutter
```

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

將 v1 音樂作為背景音（15%）疊入片段影片（原聲 100%），輸出最終成品。

- **Input**：`output/clips/*.mp4` + `output/music/*_v1.mp3`
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
| `ModuleNotFoundError: gdown` | `pip install gdown` |
| Google Drive 下載失敗 | 確認分享設定為「知道連結的人皆可存取」 |
| `OPENAI_API_KEY 未設定` | `export OPENAI_API_KEY=<key>` |
| `SUNO_API_KEY 未設定` | `export SUNO_API_KEY=<key>`，金鑰至 sunoapi.org 取得 |
| Suno credits 不足 | 至 sunoapi.org 帳號頁面儲值 |
| 影片超過 25MB（Whisper 限制） | 用 ffmpeg 切段：`ffmpeg -i input.mp4 -t 600 part1.mp4 -ss 600 part2.mp4` |

---

## 參考資料

- [短影音爆紅入門全攻略.md](短影音爆紅入門全攻略.md) — 爆紅判斷方法論
