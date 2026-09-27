// A project's social config for build-vertical.mjs. Copy it into the project
// (e.g. docs/social/config.js), keep the recordings/music/out folders beside
// it and gitignore those. Paths resolve relative to THIS file.
// Loaded two ways: by Node (module.exports) and by the scene page (window.SOCIAL).
const SOCIAL = {
  name: "myapp",                        // output prefix: out/myapp-reels.mp4
  brand: {
    word: "MYAPP",                      // the card wordmark
    accent: "#A78BFA",                  // kicker colour
    fonts: { display: "fonts/display.ttf", body: "fonts/body.ttf" }, // the app's real fonts
  },
  clipsDir: "clips",                    // real screen recordings (any shape; filled + centre-cropped)
  music: { file: "music/track.mp3", start: 0 }, // keep the licence certificate beside it
  hook: "The one-line question your user already asks themselves?",
  hookHold: 3,
  scenes: [
    { card: true, tag: "What it is, in one line.", color: ["#4B2F9A", "#1E1640"], hold: 3 },
    { clip: "feature-1.mp4", from: 0, to: 8, speed: 1.15,
      kicker: "Feature", title: "Benefit in<br>five words", sub: "One concrete detail.",
      color: ["#8A2A10", "#3A1208"] },
    { card: true, tag: "The call to action.", color: ["#4B2F9A", "#1E1640"], hold: 3.5 },
  ],
  // Scene indices ("hook" = the question card). Reels: the full set (45-60 s did
  // best in a 2026 study of 6M Reels); TikTok: a ~30 s cut (third-party pacing advice).
  cuts: { reels: ["hook", 1, 2], tiktok: ["hook", 1, 2] },
  outDir: "out",
};
if (typeof module !== "undefined") module.exports = SOCIAL;
if (typeof window !== "undefined") window.SOCIAL = SOCIAL;
