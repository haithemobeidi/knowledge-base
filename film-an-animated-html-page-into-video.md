---
stack: [video, web, animation, ffmpeg, chrome, marketing]
kind: pattern
last_verified: 2026-11-18
---

# Film an animated HTML page into video: make the page a function of time, then screenshot every frame

**One-liner:** to turn a designed, animated HTML page (kinetic type, moving art, embedded screen recordings) into an MP4, don't screen-record it and don't composite stills. Give the page one `seek(t)` that sets everything on screen for time `t`, drive it over Chrome's debugging port, and pipe one screenshot per frame into ffmpeg. The film then matches the page exactly, at any frame rate, on any machine.

*Playmoir's social videos, 2026-11-18: three 20 s vertical videos, 600 frames each, about 3 minutes a render.*

## Why not the obvious ways

- **A still caption layer over a clip** (one PNG per scene, ffmpeg overlay and crossfade) is what the first builder did. It cannot animate words, art or windows, so every video looked like the same template.
- **Recording the page in real time** drops frames whenever the machine is busy, and an embedded `<video>` drifts against the CSS animations.
- **`--virtual-time-budget` screenshots** from headless Chrome look like a cheap way to grab "the page at 8 s". They are not: the budget stops on timer boundaries, so a timeline driven by `setTimeout` is caught right as a scene switches, with its entrance animations at their first frame. The stills showed empty scenes that were fine in a real browser. Useful only as a "does it load" check.

## The page: everything is a function of time

Scenes are blocks with a duration; CSS animations start when a scene gets its `on` class. `seek(t)` owns the clock (see [verify-motion-frame-by-frame.md](./verify-motion-frame-by-frame.md) for the pause-and-set trick this builds on):

```js
async function seek(t) {
  const i = starts.findLastIndex((s) => t >= s), local = t - starts[i];
  if (i !== cur) { scenes.forEach((s, n) => s.classList.toggle("on", n === i)); cur = i; }
  // getAnimations() flushes style first, so a scene that just turned on is already in the list
  for (const a of document.getAnimations()) { a.pause(); a.currentTime = local * 1000; }
  // anything JS used to animate (counters, progress bars) is computed from `local`, never from timers
  await Promise.all([...scenes[i].querySelectorAll("video")].map((v) => seekVideo(v, from(v) + local)));
}
const seekVideo = (v, time) => new Promise((done) => {
  if (Math.abs(v.currentTime - time) < 0.001 && v.readyState >= 2) return done();
  v.addEventListener("seeked", done, { once: true });
  v.currentTime = time;
});
```

Rules that fall out of it:

- **No timers, no transitions that depend on wall time.** Staggered words are `animation-delay: calc(var(--i) * .26s)`; `currentTime` covers the delay, and `animation-fill-mode: both` holds the end state.
- **Embedded recordings are seeked, never played**, and the frame is awaited (`seeked`) before the screenshot.
- **A ready promise** (`document.fonts.ready`, every video's `loadeddata`, background images decoded) so frame 0 is not missing a font.
- **The same `seek` drives the preview**: opened in a normal browser, a `requestAnimationFrame` loop calls `seek(elapsed)`. One code path, so what you review is what gets filmed. `?t=8` freezes it for a layout check.

## The builder: Chrome's debugging port, no dependencies

Node 22+ has a global `WebSocket` and `fetch`, so the DevTools protocol needs no library:

```js
spawn(CHROME, ["--headless=new", "--remote-debugging-port=9333", `--user-data-dir=${tmp}`,
  "--allow-file-access-from-files", "--autoplay-policy=no-user-gesture-required",
  "--force-device-scale-factor=1", "--window-size=1080,1920", "about:blank"]);
const target = (await (await fetch("http://127.0.0.1:9333/json/list")).json()).find((t) => t.type === "page");
const ws = new WebSocket(target.webSocketDebuggerUrl);
// Emulation.setDeviceMetricsOverride {1080, 1920, deviceScaleFactor 1}
// Page.addScriptToEvaluateOnNewDocument "window.__BUILD = true"   (turns the preview loop off)
// Page.navigate → poll Runtime.evaluate("window.__ready", awaitPromise) → total seconds
for (let f = 0; f < frames; f++) {
  await evaluate(`__seek(${f / 30})`);                       // Runtime.evaluate, awaitPromise: true
  const png = Buffer.from((await send("Page.captureScreenshot", { format: "png" })).data, "base64");
  if (!ffmpeg.stdin.write(png)) await once(ffmpeg.stdin, "drain");
}
```

ffmpeg reads the frames as they arrive: `-f image2pipe -framerate 30 -c:v png -i -`, music as a second input with `atrim`, fades and `loudnorm`, then `libx264 -crf 16 -pix_fmt yuv420p -movflags +faststart`.

## Traps

- **A `<symbol>` logo** injected by a script and drawn with `<use>` takes CSS variables from the `<use>` element, so one generated symbol file can be recoloured per page (`fill: var(--lg)`), and the logo is never retyped.
- **Close-ups of a screen recording go soft**: a 1348 px wide take enlarged 2x reads as low-res next to crisp type. Record the app at double scale, and set the important text in type above the recording, with the recording kept as proof.
- **A silent track**: some platforms want an audio stream. `-f lavfi -i anullsrc -shortest` adds one without re-encoding the video (`-c:v copy`).
- If the builder hangs waiting for ready, a `src` path in the page is wrong (a video that never fires `loadeddata`), or the port is taken.

## When not to bother

A cut that is only clips, cards and crossfades is faster with plain ffmpeg. This earns its keep when the type or layout moves, or when a designer's HTML mock should become the video without being rebuilt in an editor.
