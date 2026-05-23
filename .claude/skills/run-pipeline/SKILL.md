---
name: run-pipeline
description: 一鍵執行完整短影音製作流水線：依序呼叫 run-transcribe、run-viral-analyzer、run-clip-cutter、run-fb-post-generator、run-music-generator、run-final-mixer，完成後將 output/ 封存為 output-<mp4名稱>/。Pipeline, 流水線, 一鍵, 完整製作, 自動化, full pipeline
---

# 短影音完整製作流水線

依序呼叫所有技能，完成一支影片從原始 MP4 到最終成品的完整製作。

## 執行步驟

1. 確認 `upload/` 內有 `.mp4` 檔案，記下檔名（後面封存資料夾用）
2. 詢問使用者以下兩個問題（一次問完）：
   - **要生成幾支短影音？**（預設 3）→ 記為 N
   - **影片背景資訊**（主題、主角身份、品牌等）
3. 依序呼叫以下技能，每個步驟完成後再進行下一步：
   1. `/run-transcribe` — 轉錄字幕
   2. `/run-viral-analyzer` — 分析爆紅片段，傳入 N 與背景資訊，跳過 skill 內的互動詢問
   3. `/run-clip-cutter` — 剪輯精華片段
   4. `/run-fb-post-generator` — 生成 Facebook 貼文
   5. `/run-music-generator` — 生成背景音樂
   6. `/run-final-mixer` — 最終混音輸出

4. 所有步驟完成後，用 Bash 工具將 `output/` 資料夾改名為 `output-<mp4檔名去掉副檔名>/`，並建立新的空 `output/` 備用：
   ```bash
   mv output/ output-<stem>/ && mkdir output/
   ```

## 錯誤處理

- 步驟 1-3（轉錄、分析、剪輯）失敗 → 停止並告知使用者
- 步驟 4-6（貼文、音樂、混音）失敗 → 記錄警告，繼續後續步驟
- 最後仍執行封存

## 完成後告知使用者

- 最終影片位置：`output-<stem>/final/`
- 貼文文字位置：`output-<stem>/posts/`
- 整個流程花費時間
