---
name: run-pipeline
description: 一鍵執行完整短影音製作流水線：依序呼叫 run-transcribe、run-viral-analyzer、run-clip-cutter、run-add-intro、run-fb-post-generator、run-music-generator、run-final-mixer，完成後將 output/ 封存為 output-<mp4名稱>/。Pipeline, 流水線, 一鍵, 完整製作, 自動化, full pipeline
---

# 短影音完整製作流水線

依序呼叫所有技能，完成一支影片從原始 MP4 到最終成品的完整製作。

## 執行步驟

1. 確認 `upload/` 內有 `.mp4` 檔案，記下檔名（後面封存資料夾用）
2. 詢問使用者以下兩個問題（一次問完）：
   - **影片背景資訊**（主題、主角身份、品牌等）
   - **ＣＴＡ 目標**（希望觀眾完成的行動，例如「追蹤粉專」、「購買產品」、「留言 tag 朋友」等）
3. 依序呼叫以下技能，每個步驟完成後再進行下一步：
   1. `/run-transcribe` — 轉錄字幕（產生 SRT）
   2. `/run-viral-analyzer` — 分析爆紅片段，傳入 N 與背景資訊，跳過 skill 內的互動詢問
   3. `/run-viral-storyboard` — 設計分鏡腳本，傳入背景資訊，跳過 skill 內的互動詢問
   4. `/run-veo3-hook`  — 生成 VEO3 分鏡腳本
   5. `/run-cta-scene` — 生成 CTA 片尾（可選，視需求而定），這邊應該帶入使用者輸入的ＣＴＡ
   6. `/run-clip-cutter` — 剪輯精華片段（降噪＋字幕燒錄，輸出至 output/clips/，不含片頭）
   7. `/run-fb-post-generator` — 生成 Facebook 貼文
   8. `/run-music-generator` — 生成背景音樂
   9. `/run-final-mixer` — 最終混音輸出

4. 所有步驟完成後，用 Bash 工具將 `output/` 資料夾改名為 `output-<mp4檔名去掉副檔名>/`，並建立新的空 `output/` 備用：
   ```bash
   mv output/ output-<stem>/ && mkdir output/
   ```

5. 將 `output-<stem>/final/` 下所有檔案複製到 `results/`，然後 commit（**不要** commit `output-*/`）：
   ```bash
   mkdir -p results
   cp output-<stem>/final/* results/
   git add results/
   git commit -m "results: add final output from <stem>"
   git push
   ```

## 錯誤處理

- 轉錄、分析、剪輯失敗 → 停止並告知使用者
- 貼文、音樂、混音失敗 → 記錄警告，繼續後續步驟
- 最後仍執行封存

## 完成後告知使用者

- 最終影片位置：`output-<stem>/final/`（本地封存）
- 已複製至 Git 倉庫：`results/`（已 commit & push）
- 貼文文字位置：`output-<stem>/posts/`
- 整個流程花費時間
