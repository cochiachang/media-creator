// 此檔案由 driver.py 在每次渲染前自動產生，請勿手動修改。
import { Composition } from "remotion";
import React from "react";
import { IntroVideo, calcIntroDurationFrames } from "./IntroVideo";

const LINES: string[] = ["咖啡獵人Penny", "的評審行李箱大公開"];
const FPS = 30;
const CHAR_DELAY = 3;

const DURATION = calcIntroDurationFrames({
  lines: LINES,
  charDelay: CHAR_DELAY,
  fps: FPS,
  holdSeconds: 1,
});

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Intro"
      component={IntroVideo}
      durationInFrames={DURATION}
      fps={FPS}
      width={720}
      height={1280}
      defaultProps={{
        lines: LINES,
        theme: "dark",
        charDelay: CHAR_DELAY,
        fontSize: 48,
      }}
    />
  );
};
