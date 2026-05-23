# media-creator

## 資料夾用途

- `upload/` — **輸入**參考圖片存放處。使用者將欲處理的圖片放在此處，腳本再從這裡讀取並送至 Gemini 或 OpenAI API 做進一步處理（例如風格轉換、顏色修改）。
- `output/` — **輸出**目錄。所有 AI 生成或處理後的圖片一律儲存至此資料夾。

## 生圖規則

- 所有生圖腳本的輸出必須儲存到 `output/` 資料夾，不可直接存在專案根目錄
- 若腳本需要參考圖片，從 `upload/` 讀取，再送給 Gemini / OpenAI API
- 兩個資料夾不存在時應自動建立（`os.makedirs(..., exist_ok=True)`）
- 新增生圖腳本時，請遵守相同的 `upload/` → API → `output/` 流程

## 專案結構

```
media-creator/
├── generate_image.py    # Google Imagen 4.0 生圖（Gemini API）
├── edit_logo_green.py   # OpenAI gpt-image-1 生圖／修圖
├── upload/              # 輸入參考圖片（送給 API 處理用）
├── output/              # AI 生成結果輸出目錄
└── CLAUDE.md
```

## 環境變數

- `GEMINI_API_KEY` — Google Imagen 生圖所需
- `OPENAI_API_KEY` — OpenAI gpt-image-1 生圖所需
