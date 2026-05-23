---
name: run-gdrive-download
description: 輸入 Google Drive 分享連結或 File ID，下載影片檔案並放入 upload/，供後續流水線使用。Download, Google Drive, gdrive, 下載, 影片, upload
---

# Google Drive 影片下載器

接受 Google Drive 分享連結（或裸 File ID），下載影片並驗證副檔名，存至 `upload/`。

Driver：`.claude/skills/run-gdrive-download/driver.py`
Input：Google Drive 公開分享連結 或 File ID
Output：`upload/<filename>.<ext>`

## Prerequisites

```bash
pip install gdown
```

## Run

```bash
python3 .claude/skills/run-gdrive-download/driver.py "<google_drive_url>"
```

### 支援的 URL 格式

| 格式 | 範例 |
|---|---|
| 分享連結（`/file/d/`）| `https://drive.google.com/file/d/1abc.../view?usp=sharing` |
| 開啟連結（`?id=`）| `https://drive.google.com/open?id=1abc...` |
| 直連（`uc?id=`）| `https://drive.google.com/uc?id=1abc...` |
| 裸 File ID | `1abc...XYZ` |

## 支援的影片格式

`.mp4` `.mov` `.avi` `.mkv` `.wmv` `.flv` `.ts` `.webm` `.m4v` `.3gp`

如果下載的檔案不在上述清單中，driver 會報錯並不寫入 `upload/`。

## 重複檔名處理

若 `upload/` 已有同名檔案，driver 自動在檔名加上 `_1`、`_2` 等後綴，不覆蓋原檔。

## Gotchas

- **檔案必須公開分享**：Google Drive 分享設定需為「知道連結的人」可存取，否則下載會失敗。
- **大型檔案警告頁**：`gdown` 自動繞過 Google 的防毒掃描確認頁，無需手動處理。
- **私人雲端硬碟**：不支援需要帳號登入才能存取的檔案；請先在 Google Drive 設定「Anyone with the link」。

## Troubleshooting

| 問題 | 解法 |
|---|---|
| `ModuleNotFoundError: gdown` | `pip install gdown` |
| `Download failed` | 確認 Google Drive 分享設定為「知道連結的人」 |
| 下載的不是影片 | 確認連結指向影片檔案，而非 Google 文件或資料夾 |
| `Could not extract a Google Drive file ID` | 確認貼上完整 URL，或提供正確 File ID |

## 後續步驟

下載完成後可直接執行：
- `/run-transcribe` — 轉錄字幕
- `/run-pipeline` — 完整短影音製作流水線
