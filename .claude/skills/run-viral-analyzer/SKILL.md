---
name: run-viral-analyzer
description: 分析影片字幕找出爆紅精華片段，輸出含時間戳、爆紅原因、關鍵字、建議標題的 CSV 分析報告。Run, analyze, viral, highlight, segment, 短影音, 精華片段, 爆紅分析, 剪輯, 時間戳
---

# 爆紅精華片段分析器

讀取 `output/` 內的 `.srt` 字幕檔，結合 `短影音爆紅入門全攻略.md` 的方法論，透過 GPT-4o 找出最有爆紅潛力的片段，以列表顯示並輸出 CSV 報告。

Input：`output/<file>.srt`
Output：`output/<file>_viral_segments.csv`

## Run（agent path）
互動步驟：
1. 若 `output/` 有多個 `.srt` 檔，輸入編號選擇
2. 若外部未傳入，詢問使用者：**要生成幾支短影音？**（預設 3）→ 記為 N
3. 若外部未傳入，詢問使用者：**影片背景資訊**（主題、主角身份、品牌等）
4. 分析所有有機會爆紅的片段，依爆紅潛力由高到低排序，**只保留前 N 名**
5. CSV 自動儲存至 `output/<filename>_viral_segments.csv`，只包含這 N 個片段

## CSV 輸出格式

固定欄位（UTF-8 BOM，可直接用 Excel 開啟）：

| 欄位 | 說明 |
|---|---|
| 片段編號 | 依爆紅潛力評分由高到低排列 |
| 開始時間 | HH:MM:SS,mmm |
| 結束時間 | HH:MM:SS,mmm |
| 片段內容摘要 | 30 字以內 |
| 爆紅潛力評分 | 1–10（10 最高） |
| 爆紅原因 | 具體說明為何有爆紅潛力 |
| 推薦關鍵字 | 3–5 個，逗號分隔 |
| 建議標題 | 吸睛、能引發好奇心的短影音標題 |
