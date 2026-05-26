---
name: run-transcribe
description: Transcribe video or audio files to timestamped SRT subtitles using OpenAI Whisper. Use when asked to transcribe, subtitle, convert speech to text, or generate SRT from a video or audio file.
---

# run-transcribe

Calls the OpenAI Whisper API to transcribe a video or audio file and writes a timestamped `.srt` subtitle file to `output/`.

Driver: `.claude/skills/run-transcribe/driver.py`
Input : `upload/<file>` (mp4, mov, mp3, wav, m4a, ogg, flac, webm …)
Output: `output/<file>.srt`

## Prerequisites

```bash
apt-get install -y ffmpeg
pip install openai
export OPENAI_API_KEY=<your-key>
```

## 多影片自動合併

`upload/` 內若有 **多支影片**，driver 會先用 `ffmpeg concat` 依檔名順序將它們合併成一支，再送 Whisper 轉錄，輸出為 `output/merged.srt`。

```
找到 3 個影片，依檔名順序合併為一支再轉錄：
  - part1.mp4
  - part2.mp4
  - part3.mp4
合併中（ffmpeg concat）…
✅ 合併完成：merged.mp4（180 MB）
從影片萃取音訊：merged.mp4
送交 Whisper API（language=zh）：merged_audio.mp3
使用 GPT-4o 校正同音字與斷句錯誤…
✅ SRT 已儲存：/…/output/merged.srt
```

> 若要手動指定合併順序，請直接傳入單一已合併的檔案路徑。

## Run (agent path)

Place the source file(s) in `upload/`, then:

```bash
# 基本用法（upload/ 只有一支影片，或自動合併多支）
python3 .claude/skills/run-transcribe/driver.py

# 指定單一檔案（跳過自動選取 / 合併）
python3 .claude/skills/run-transcribe/driver.py test_video.mp4

# 指定背景資訊（跳過互動詢問）
python3 .claude/skills/run-transcribe/driver.py test_video.mp4 --background "精品咖啡評審、COE 比賽"

# 只跑 Whisper，跳過 GPT-4o 校正
python3 .claude/skills/run-transcribe/driver.py test_video.mp4 --no-correct

# 指定輸出路徑
python3 .claude/skills/run-transcribe/driver.py test_speech.mp3 my_subtitles.srt
```

The driver prints progress lines and the final path:

```
從影片萃取音訊：test_video.mp4
送交 Whisper API（language=zh）：test_video_audio.mp3
使用 GPT-4o 校正同音字與斷句錯誤…
✅ SRT 已儲存：/…/output/test_video.srt
```

### 參數說明

| 參數 | 說明 |
|---|---|
| `--background TEXT` | 影片背景資訊（主角、品牌、專有名詞），提升同音字辨識準確度 |
| `--no-correct` | 跳過 GPT-4o 校正，只輸出 Whisper 原始結果 |

## SRT output format

```
1
00:00:00,000 --> 00:00:03,400
Welcome to the Cup of Excellence Costa Rica 2025.

2
00:00:03,400 --> 00:00:07,960
Finca Los Pinos, position seven, score 88.13.
```

## Gotchas

- **25 MB Whisper limit** — the driver checks size before uploading and exits with a clear error. For long videos, split first: `ffmpeg -i input.mp4 -t 600 part1.mp4 -ss 600 part2.mp4`
- **Video extraction** — ffmpeg converts to mono 16-kHz MP3 to minimise upload size. The temp file is deleted automatically.
- **Pure tones / silence** — Whisper returns an empty SRT (1 byte). This is correct behaviour, not a bug.
- **File path** — if the argument is not absolute, the driver prepends `upload/`. You do not need to write the full path.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: openai` | `pip install openai` |
| `ffmpeg: command not found` | `apt-get install -y ffmpeg` |
| `File not found` | Check the file is in `upload/` and the name matches exactly |
| `File too large` | Split the file with ffmpeg (see Gotchas) |
