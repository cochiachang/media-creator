---
name: intro-video
description: 用 Remotion 產生彈跳字幕片頭 MP4，輸入文字即可自動算時長並渲染
metadata:
  tags: remotion, video, intro, animation, 片頭, 字幕
---

## 功能說明

這個 skill 讓你輸入片頭文字，就自動產出 MP4 片頭影片。  
所有元件完全自給自足，直接複製到任何 Remotion 專案即可使用。

特性：
- 每個字元依序彈跳入場（playful overshoot 效果）
- 支援 1～3 行文字
- 4 種背景主題：`dark`（深藍紫）、`jungle`（叢林綠）、`ocean`（海洋藍）、`sunset`（夕陽橘）
- 自動計算影片時長（依文字量），不需手動算 frames
- 支援結尾 emoji 裝飾

---

## 步驟 1：在新專案或現有專案中安裝 Remotion

如果是全新資料夾：

```bash
npx create-video@latest --yes --blank --no-tailwind my-intro
cd my-intro
```

如果是現有專案，確認已安裝：

```bash
npm install remotion @remotion/cli
```

---

## 步驟 2：複製元件檔案

將 [assets/IntroVideo.tsx](assets/IntroVideo.tsx) 複製到你的 `src/` 目錄下：

```
src/
  IntroVideo.tsx   ← 複製這個檔案（不需修改）
  Root.tsx         ← 在這裡設定你的文字
```

`IntroVideo.tsx` 包含所有元件，**不依賴任何外部自訂模組**，只用到 `remotion` 本身。

---

## 步驟 3：在 `Root.tsx` 設定你的文字

```tsx
import { Composition } from "remotion";
import { IntroVideo, calcIntroDurationFrames } from "./IntroVideo";

// ① 設定你的文字（1～3 行）
const LINES = [
  "PENNY到哥斯大尼加",
  "做COE評審啦！",
];

const FPS = 30;
const CHAR_DELAY = 3; // 每個字元間隔 frames

// ② 自動算出影片需要幾 frames
const DURATION = calcIntroDurationFrames({
  lines: LINES,
  charDelay: CHAR_DELAY,
  fps: FPS,
  holdSeconds: 1,    // 全部字出現後靜止幾秒
});

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Intro"
      component={IntroVideo}
      durationInFrames={DURATION}
      fps={FPS}
      width={1280}
      height={720}
      defaultProps={{
        lines: LINES,
        theme: "jungle",      // "dark" | "jungle" | "ocean" | "sunset"
        charDelay: CHAR_DELAY,
        fontSize: 72,
        decoEmojis: "🌿 ☕ 🏆 ✈️ 🌿",
      }}
    />
  );
};
```

### Props 說明

| Prop | 型別 | 預設 | 說明 |
|------|------|------|------|
| `lines` | `string[]` | 必填 | 字幕行（1～3 行） |
| `theme` | `"dark"\|"jungle"\|"ocean"\|"sunset"` | `"dark"` | 背景主題 |
| `charDelay` | `number` | `3` | 每個字元間隔 frames（3 = 0.1 秒 @30fps） |
| `fontSize` | `number` | `72` | 字體大小 px |
| `lineGap` | `number` | `4` | 行與行之間的間隔 frames |
| `decoEmojis` | `string` | `""` | 結尾裝飾 emoji，留空不顯示 |

---

## 步驟 4：直接 render 成 MP4

```bash
npx remotion render Intro out/intro.mp4
```

不需要開瀏覽器或 Studio。輸出在 `out/intro.mp4`。

### 常用選項

```bash
# 加快 render 速度
npx remotion render Intro out/intro.mp4 --concurrency=8

# 覆蓋已有的輸出
npx remotion render Intro out/intro.mp4 --overwrite

# 只 render 某幾幀做快速確認
npx remotion render Intro out/intro.mp4 --frames=0-30
```

---

## 主題預覽

| theme | 背景 | 適合場景 |
|-------|------|---------|
| `dark` | 深藍 → 紫漸層 + 紫色光暈 | 科技、遊戲、正式場合 |
| `jungle` | 深綠叢林漸層 + 綠色光暈 | 旅遊、自然、輕鬆氣氛 |
| `ocean` | 深海藍漸層 + 青藍光暈 | 清爽、企業、報告 |
| `sunset` | 暗橘夕陽漸層 + 橘色光暈 | 活力、慶祝、宣告 |

---

## 快速範例

### 三秒「大家好」片頭（預設 dark 主題）

```tsx
defaultProps={{
  lines: ["大家好"],
  theme: "dark",
  fontSize: 160,
  decoEmojis: "👋",
}}
```

### 旅遊宣告片頭

```tsx
defaultProps={{
  lines: ["PENNY到哥斯大尼加", "做COE評審啦！"],
  theme: "jungle",
  fontSize: 72,
  decoEmojis: "🌿 ☕ 🏆 ✈️ 🌿",
}}
```

### 多行公告（ocean 主題）

```tsx
defaultProps={{
  lines: ["Q3 成果發表", "2025 年度大會", "歡迎參加 🎉"],
  theme: "ocean",
  fontSize: 64,
  charDelay: 2,
}}
```

---

## 自訂顏色

如果需要每行自訂顏色，直接修改 `IntroVideo.tsx` 裡的 `THEMES` 物件，
在對應 theme 的 `lineColors` 陣列中調整各字元的顏色即可。
每行的 `lineColors` 陣列會循環使用，字元數超過時自動從頭循環。
