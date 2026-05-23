---
name: transcribe
description: 把影片或音訊檔案轉成帶時間戳的 SRT 字幕檔，使用 OpenAI Whisper API。當使用者上傳或指定影片/音訊檔案，想要逐字稿、字幕、SRT 檔，或說「幫我轉成文字」「產生字幕」時，使用這個 skill。
---

# 影片 / 音訊轉 SRT 逐字稿

使用 OpenAI Whisper API 將影片或音訊轉成帶時間戳的 SRT 字幕檔。

## 核心原則

- 影片（mp4, mov, avi, mkv…）先用 ffmpeg 抽出音軌再送 API
- 音訊（mp3, wav, m4a, ogg, flac, webm…）直接送 API
- 輸出一律為標準 SRT 格式，含時間戳
- 單檔上限 25 MB；超過請先切割

## 使用方式

使用者上傳檔案或告知路徑後，執行：

```bash
# 確認環境
pip install openai --quiet
apt-get install -y ffmpeg -qq

# 執行轉錄（輸出到同目錄）
python3 scripts/transcribe.py <輸入檔案路徑>

# 指定輸出路徑
python3 scripts/transcribe.py <輸入檔案路徑> <輸出.srt>
```

執行後把 SRT 內容顯示給使用者，並說明各段時間戳。

## 輸出格式範例

```
1
00:00:00,000 --> 00:00:03,400
歡迎來到哥斯大黎加咖啡卓越杯 2025。

2
00:00:03,400 --> 00:00:07,960
Finca Los Pinos，第七名，分數 88.13。
```

## 注意事項

- `OPENAI_API_KEY` 需設定在環境變數
- 超過 25 MB 請先切割：`ffmpeg -i input.mp4 -t 600 part1.mp4 -ss 600 part2.mp4`
- 純音效（無語音）會輸出空白 SRT，屬正常行為
