// Vertical social cuts (1080x1920, 30 fps, H.264 + AAC) from real screen
// recordings, driven by a project's social config (see example-config.js).
// Headless Chrome paints each card and a transparent caption layer from
// scene-vertical.html; ffmpeg lays the layer over the clip (scaled to fill the
// frame, centre-cropped) and crossfades the scenes. Proven on Playmoir's
// Reels/TikTok cuts, 2026-09-27.
//
// Run: node build-vertical.mjs <config.js> <cut> [--cover] [--review]
//   <cut>     a key of config.cuts (e.g. reels, tiktok) → <outDir>/<name>-<cut>.mp4
//   --cover   also render <outDir>/<name>-cover.png (the first card scene)
//   --review  render stills with the safe-zone overlay instead of a video
// Needs ffmpeg/ffprobe on PATH and Chrome (CHROME env to override the path).
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const [cfgArg, cut] = process.argv.slice(2).filter((a) => !a.startsWith("--"));
const flag = (f) => process.argv.includes(f);
const cfgPath = resolve(cfgArg ?? "");
const C = createRequire(import.meta.url)(cfgPath);
const DIR = dirname(cfgPath);
if (!cut || !C.cuts?.[cut]) throw new Error(`usage: build-vertical.mjs <config.js> <${Object.keys(C.cuts ?? {}).join("|")}> [--cover] [--review]`);

const CHROME = process.env.CHROME || (process.platform === "win32"
  ? "C:/Program Files/Google/Chrome/Application/chrome.exe" : "google-chrome");
const FADE = C.fade ?? 0.5;
const OUT = resolve(DIR, C.outDir ?? "out");
const WORK = join(OUT, `v-${cut}`);
mkdirSync(WORK, { recursive: true });
const run = (cmd, args) => execFileSync(cmd, args, { stdio: ["ignore", "pipe", "inherit"] }).toString();
const ff = (args) => run("ffmpeg", ["-v", "error", "-y", ...args]);
const page = pathToFileURL(join(HERE, "scene-vertical.html")).href;
const cfgUrl = encodeURIComponent(pathToFileURL(cfgPath).href);
const shoot = (png, query) => run(CHROME, ["--headless=new", "--disable-gpu", "--hide-scrollbars",
  "--allow-file-access-from-files", "--force-device-scale-factor=1", "--window-size=1080,1920",
  "--default-background-color=00000000", "--virtual-time-budget=4000", `--screenshot=${png}`,
  `${page}?config=${cfgUrl}&${query}`]);
const enc = ["-r", "30", "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-pix_fmt", "yuv420p"];
const name = C.name ?? "promo";

if (flag("--cover")) {
  const first = C.scenes.findIndex((s) => s.card);
  shoot(join(OUT, `${name}-cover.png`), `s=${first}`);
  console.log(`cover → ${join(OUT, `${name}-cover.png`)}`);
}

if (flag("--review")) {
  // One still per scene of the cut, a frame 1 s into each clip under the copy, zones drawn.
  C.cuts[cut].forEach((id, i) => {
    const s = id === "hook" ? null : C.scenes[id];
    let q = s ? `s=${id}` : "hook=1";
    if (s && !s.card) {
      const still = join(WORK, `still-${i}.png`);
      ff(["-ss", String(s.from + 1), "-i", resolve(DIR, C.clipsDir, s.clip), "-frames:v", "1", still]);
      q += `&still=${encodeURIComponent(pathToFileURL(still).href)}`;
    }
    shoot(join(WORK, `review-${i}.png`), `${q}&zones=1`);
  });
  console.log(`review stills → ${WORK}`);
  process.exit(0);
}

const segments = C.cuts[cut].map((id, i) => {
  const seg = join(WORK, `seg-${i}.mp4`);
  const png = join(WORK, `layer-${i}.png`);
  const s = id === "hook" ? null : C.scenes[id];
  if (!s || s.card) {
    shoot(png, s ? `s=${id}` : "hook=1");
    ff(["-loop", "1", "-t", String(s ? s.hold : (C.hookHold ?? 3)), "-i", png, "-vf", "fps=30,format=yuv420p", ...enc, seg]);
  } else {
    shoot(png, `s=${id}&top=1`);
    ff(["-i", resolve(DIR, C.clipsDir, s.clip), "-loop", "1", "-i", png,
      "-filter_complex",
      `[0:v]trim=start=${s.from}:end=${s.to},setpts=(PTS-STARTPTS)/${s.speed ?? 1},fps=30,` +
      // Fill the frame whatever the recording's shape, centre-cropped.
      `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[c];` +
      `[1:v]format=rgba[t];[c][t]overlay=0:0:shortest=1,format=yuv420p`,
      // Explicit length: the looped layer never ends on its own.
      "-t", ((s.to - s.from) / (s.speed ?? 1)).toFixed(3), ...enc, seg]);
  }
  const dur = Number(run("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", seg]));
  console.log(`${cut} ${i} (${id}): ${dur.toFixed(2)} s`);
  return { seg, dur };
});

// Crossfade chain: each fade starts FADE seconds before the running total ends.
const inputs = segments.flatMap((s) => ["-i", s.seg]);
let chain = "";
let total = segments[0].dur;
for (let i = 1; i < segments.length; i++) {
  const from = i === 1 ? "[0:v]" : `[x${i - 1}]`;
  const to = i === segments.length - 1 ? "[v]" : `[x${i}]`;
  chain += `${from}[${i}:v]xfade=transition=fade:duration=${FADE}:offset=${(total - FADE).toFixed(3)}${to};`;
  total += segments[i].dur - FADE;
}
if (segments.length === 1) chain = "[0:v]null[v];";
const music = C.music?.file ? resolve(DIR, C.music.file) : null;
const audioIn = music ? ["-ss", String(C.music.start ?? 0), "-i", music] : [];
const aFilter = music
  ? `;[${segments.length}:a]atrim=0:${total.toFixed(3)},afade=t=in:d=1,` +
    `afade=t=out:st=${(total - 2.5).toFixed(3)}:d=2.5,loudnorm=I=-14:TP=-1.5:LRA=11[a]`
  : "";
const final = join(OUT, `${name}-${cut}.mp4`);
ff([...inputs, ...audioIn, "-filter_complex", chain.slice(0, -1) + aFilter, "-map", "[v]",
  ...(music ? ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"] : []),
  "-r", "30", "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
  "-t", total.toFixed(3), final]);
console.log(`built ${final} (${total.toFixed(1)} s)`);
