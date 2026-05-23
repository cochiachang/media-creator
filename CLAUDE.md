# media-creator

## 圖片生成規則

每次生成圖片後，必須自動將輸出檔案複製到專案根目錄下的 `upload/` 資料夾。

- 所有生圖腳本（包括 `generate_image.py`、`edit_logo_green.py` 及未來新增的腳本）都須在儲存主輸出後呼叫 `save_to_upload()` 將檔案同步至 `upload/`
- `upload/` 資料夾如不存在，應自動建立
- 每次新增生圖腳本時，請確保包含相同的 `save_to_upload()` 邏輯

## 專案結構

```
media-creator/
├── generate_image.py    # Google Imagen 4.0 生圖（Gemini API）
├── edit_logo_green.py   # OpenAI gpt-image-1 生圖
├── upload/              # 所有生成圖片的自動上傳目錄
└── CLAUDE.md
```

## 環境變數

- `GEMINI_API_KEY` — Google Imagen 生圖所需
- `OPENAI_API_KEY` — OpenAI gpt-image-1 生圖所需
