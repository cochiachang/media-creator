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

## Run (agent path)

Place the source file in `upload/`, then:

```bash
# audio file → output/test_speech.srt
python3 .claude/skills/run-transcribe/driver.py test_speech.mp3

# video file (audio is extracted automatically) → output/test_video.srt
python3 .claude/skills/run-transcribe/driver.py test_video.mp4

# custom output path
python3 .claude/skills/run-transcribe/driver.py test_speech.mp3 my_subtitles.srt
```

The driver prints progress lines and the final path:

```
Extracting audio from video: test_video.mp4
Sending to Whisper API: test_video_audio.mp3
SRT saved to: /…/output/test_video.srt
```

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
