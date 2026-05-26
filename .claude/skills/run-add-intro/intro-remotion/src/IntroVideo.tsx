/**
 * IntroVideo.tsx — 彈跳字幕片頭元件（完整自給自足版本）
 *
 * 使用方式：
 *   <IntroVideo lines={["PENNY到哥斯大尼加", "做COE評審啦！"]} theme="jungle" />
 *
 * Props:
 *   lines    — 字幕行（1~3 行），每行是一個字串
 *   theme    — 背景主題："dark" | "jungle" | "ocean" | "sunset"（預設 "dark"）
 *   charDelay — 每個字元的間隔 frames（預設 3）
 *   fontSize  — 字體大小 px（預設 72）
 */

import {
  AbsoluteFill,
  Easing,
  Sequence,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// ─── 主題定義 ────────────────────────────────────────────────────────────────

export type IntroTheme = "dark" | "jungle" | "ocean" | "sunset";

const THEMES: Record<
  IntroTheme,
  { bg: string; glow: string; lineColors: string[][] }
> = {
  dark: {
    bg: "linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)",
    glow: "rgba(120,80,255,0.25)",
    lineColors: [
      ["#FFD700", "#FF6B9D", "#00E5FF", "#76FF03", "#FF6B35"],
      ["#FF6B9D", "#FFD700", "#00E5FF", "#76FF03", "#FF6B35"],
      ["#00E5FF", "#FFD700", "#FF6B9D", "#76FF03", "#FF6B35"],
    ],
  },
  jungle: {
    bg: "linear-gradient(135deg, #1a3a1a 0%, #2d6a2d 40%, #1a4a3a 100%)",
    glow: "rgba(118,255,3,0.2)",
    lineColors: [
      ["#FFD700", "#FFD700", "#FFD700", "#FFD700", "#FFD700",
       "#00E5FF", "#76FF03", "#76FF03", "#76FF03", "#76FF03", "#76FF03"],
      ["#FF6B9D", "#FFD700", "#FFD700", "#FFD700", "#FF6B9D", "#FF6B9D", "#FF6B35", "#ffffff"],
      ["#FFD700", "#76FF03", "#00E5FF", "#FF6B9D", "#FF6B35"],
    ],
  },
  ocean: {
    bg: "linear-gradient(135deg, #0a1628 0%, #1a3a5c 50%, #0d2137 100%)",
    glow: "rgba(0,229,255,0.2)",
    lineColors: [
      ["#00E5FF", "#40C4FF", "#80D8FF", "#B3E5FC", "#E1F5FE"],
      ["#00E5FF", "#40C4FF", "#80D8FF", "#B3E5FC", "#E1F5FE"],
      ["#00E5FF", "#40C4FF", "#80D8FF", "#B3E5FC", "#E1F5FE"],
    ],
  },
  sunset: {
    bg: "linear-gradient(135deg, #1a0a00 0%, #7b2d00 50%, #3d0a1a 100%)",
    glow: "rgba(255,107,53,0.25)",
    lineColors: [
      ["#FF6B35", "#FFD700", "#FF6B9D", "#FF8C00", "#FFB347"],
      ["#FFD700", "#FF6B35", "#FF6B9D", "#FF8C00", "#FFB347"],
      ["#FF6B9D", "#FFD700", "#FF6B35", "#FF8C00", "#FFB347"],
    ],
  },
};

// ─── BounceChar：單一字元彈跳動畫 ─────────────────────────────────────────────

interface BounceCharProps {
  char: string;
  color: string;
  /** 從這個 frame 開始動畫 */
  startFrame: number;
  fontSize: number;
}

const BounceChar: React.FC<BounceCharProps> = ({
  char,
  color,
  startFrame,
  fontSize,
}) => {
  const frame = useCurrentFrame();
  const local = frame - startFrame;

  const scale = interpolate(local, [0, 18], [0, 1], {
    easing: Easing.bezier(0.34, 1.56, 0.64, 1), // playful overshoot
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const translateY = interpolate(local, [0, 18], [fontSize * 0.5, 0], {
    easing: Easing.bezier(0.34, 1.56, 0.64, 1),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const opacity = interpolate(local, [0, 6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // 在 startFrame 之前完全隱藏但保留佔位
  if (local < 0) {
    return (
      <span
        style={{
          display: "inline-block",
          fontSize,
          opacity: 0,
          fontFamily:
            '"PingFang TC", "Noto Sans TC", "Microsoft JhengHei", sans-serif',
          lineHeight: 1.2,
        }}
      >
        {char}
      </span>
    );
  }

  return (
    <span
      style={{
        display: "inline-block",
        fontSize,
        fontWeight: 900,
        color,
        transform: `scale(${scale}) translateY(${translateY}px)`,
        opacity,
        fontFamily:
          '"PingFang TC", "Noto Sans TC", "Microsoft JhengHei", sans-serif',
        lineHeight: 1.2,
        textShadow: `0 4px 20px rgba(0,0,0,0.5)`,
      }}
    >
      {char}
    </span>
  );
};

// ─── IntroLine：一整行文字 ─────────────────────────────────────────────────────

interface IntroLineProps {
  text: string;
  colors: string[];
  /** 這一行第一個字元從哪個 frame 開始 */
  lineStartFrame: number;
  charDelay: number;
  fontSize: number;
}

const IntroLine: React.FC<IntroLineProps> = ({
  text,
  colors,
  lineStartFrame,
  charDelay,
  fontSize,
}) => {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "row",
        flexWrap: "nowrap",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {text.split("").map((char, i) => (
        <BounceChar
          key={i}
          char={char}
          color={colors[i % colors.length]}
          startFrame={lineStartFrame + i * charDelay}
          fontSize={fontSize}
        />
      ))}
    </div>
  );
};

// ─── DecoEmoji：片尾裝飾 emoji ────────────────────────────────────────────────

interface DecoEmojiProps {
  emojis: string;
  startFrame: number;
}

const DecoEmoji: React.FC<DecoEmojiProps> = ({ emojis, startFrame }) => {
  const frame = useCurrentFrame();
  const local = frame - startFrame;

  const opacity = interpolate(local, [0, 15], [0, 1], {
    easing: Easing.bezier(0.16, 1, 0.3, 1),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const translateY = interpolate(local, [0, 15], [12, 0], {
    easing: Easing.bezier(0.16, 1, 0.3, 1),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  if (local < 0) return null;

  return (
    <div
      style={{
        marginTop: 24,
        fontSize: 44,
        opacity,
        transform: `translateY(${translateY}px)`,
        letterSpacing: "0.2em",
      }}
    >
      {emojis}
    </div>
  );
};

// ─── IntroVideo：主元件（對外 export） ────────────────────────────────────────

export interface IntroVideoProps {
  /** 字幕行，1~3 行。每行一個字串。 */
  lines: string[];
  /** 背景主題 */
  theme?: IntroTheme;
  /** 每個字元的入場間隔（frames，預設 3） */
  charDelay?: number;
  /** 字體大小 px（預設 72） */
  fontSize?: number;
  /** 行與行之間的間隔 frames（預設 4） */
  lineGap?: number;
  /** 裝飾 emoji，留空則不顯示（預設 ""） */
  decoEmojis?: string;
}

export const IntroVideo: React.FC<IntroVideoProps> = ({
  lines,
  theme = "dark",
  charDelay = 3,
  fontSize = 72,
  lineGap = 4,
  decoEmojis = "",
}) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();
  const themeConfig = THEMES[theme];

  // 計算每行的 startFrame
  const lineStartFrames: number[] = [];
  let cursor = 0;
  for (const line of lines) {
    lineStartFrames.push(cursor);
    cursor += line.length * charDelay + lineGap;
  }

  // 所有字元結束後 emoji 才出現
  const allDone = cursor;

  // 背景漸入 + 光暈脈動
  const bgOpacity = interpolate(frame, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const glowScale = interpolate(frame, [0, fps * 3], [0.9, 1.15], {
    easing: Easing.inOut(Easing.sin),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: themeConfig.bg,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
      }}
    >
      {/* 背景光暈 */}
      <div
        style={{
          position: "absolute",
          width: 700,
          height: 700,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${themeConfig.glow} 0%, transparent 70%)`,
          transform: `scale(${glowScale})`,
          opacity: bgOpacity,
          pointerEvents: "none",
        }}
      />

      {/* 字幕行 */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 12,
          alignItems: "center",
          position: "relative",
          zIndex: 1,
        }}
      >
        {lines.map((line, lineIdx) => (
          <IntroLine
            key={lineIdx}
            text={line}
            colors={
              themeConfig.lineColors[lineIdx % themeConfig.lineColors.length]
            }
            lineStartFrame={lineStartFrames[lineIdx]}
            charDelay={charDelay}
            fontSize={fontSize}
          />
        ))}
      </div>

      {/* 裝飾 emoji */}
      {decoEmojis && (
        <div style={{ position: "relative", zIndex: 1 }}>
          <DecoEmoji emojis={decoEmojis} startFrame={allDone} />
        </div>
      )}
    </AbsoluteFill>
  );
};

// ─── 工具函式：計算需要幾秒 ──────────────────────────────────────────────────

/**
 * 根據 lines/charDelay/fps 計算片頭影片需要的總 frames。
 * 最短保留 1 秒的靜止展示時間。
 *
 * 使用範例（在 Root.tsx 中）：
 *   const frames = calcIntroDurationFrames({
 *     lines: ["PENNY到哥斯大尼加", "做COE評審啦！"],
 *     charDelay: 3,
 *     lineGap: 4,
 *     fps: 30,
 *     holdSeconds: 1,
 *   });
 */
export const calcIntroDurationFrames = ({
  lines,
  charDelay = 3,
  lineGap = 4,
  fps = 30,
  holdSeconds = 1,
  emojiFrames = 20,
}: {
  lines: string[];
  charDelay?: number;
  lineGap?: number;
  fps?: number;
  holdSeconds?: number;
  emojiFrames?: number;
}): number => {
  let totalAnimFrames = 0;
  for (const line of lines) {
    totalAnimFrames += line.length * charDelay + lineGap;
  }
  // 最後一個字動畫結束需要 18 frames
  totalAnimFrames += 18;
  // emoji 淡入 + hold
  totalAnimFrames += emojiFrames + fps * holdSeconds;
  return totalAnimFrames;
};
