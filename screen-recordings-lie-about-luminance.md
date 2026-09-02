---
stack: [windows, webview2, chromium, animation, debugging, screen-capture, ffmpeg]
kind: gotcha
last_verified: 2026-09-02
---

# A screen recording can show a brightness "pop" that is not on the display

**One-liner:** Windows screen recordings of a Chromium/WebView2 window can carry a window-wide luminance step the eye never sees — every pixel, including chrome no code touches, jumps between two tone curves depending on what the page is compositing — so a "pop" or "flash" diagnosed from a capture may be the recorder's tone mapping, not your CSS. Before reading brightness off a recording, measure pixels your code cannot have changed, and know the display's HDR state.

## Symptom

- Frame-stepping a recording of an animation, the whole window gets brighter in one frame at a beat in the animation — for us, the moment a large hero image landed at the end of a card-to-banner flight. The hero, the body text, the sidebar, the title bar: everything.
- Measured with ffmpeg (region means, 0–255 gray) on the frame before and the frame after the step:

| Region | Before | After |
|---|---|---|
| App-shell gutter (no code touches it) | 21 | 60 |
| Title-bar strip | 25 | 77 |
| Body background | 7 | 51 |
| Hero art | 115 | 213 |
| White text, max value | 227 | 255 |

  The per-region ratios differ (×2.8, ×1.85, ×3.1…), so it is not one scrim lifting or one `brightness()` filter — it is a different tone curve applied to the whole frame.
- Across three recordings the window is "bright" whenever a large real-art image is on screen and "dark" on a grid of small thumbnails and on placeholder art, regardless of which screen it is.
- The person at the actual display, asked to look for the pop: *"idk what pop lol nothing pops."* That is the tell.

## Cause — what is established and what is not

**Established:** the step lives in the capture, not the page. The dark-state value of the untouched shell pixels equals the surface colour's expected 8-bit value (`#171517` → ~22), i.e. captured 1:1; the bright state is the same pixels tone-mapped up. Nothing in the CSS dims or brightens the window: grep for filters/scrims found only per-element effects, and regions outside every animated container moved in lockstep with the animated ones. The user confirmed it as known recorder behaviour: *"that's the windows recording, that's not on us."*

**Hypothesis, unconfirmed:** on an HDR-enabled display, Chromium/WebView2 promotes its swap chain to an HDR (FP16) surface when certain large image layers are composited, and Windows' capture path tone-maps HDR and SDR frames differently — the display shows its own consistent mapping, the recorder shows the switch. It fits every observation (the trigger is "large real-art image on screen", not "filter present": the small thumbnails carry CSS filters too and stay dark) but was never confirmed by toggling HDR off and re-recording. Say so if you cite it.

## Fix — a method, not a patch

1. **Never diagnose luminance from a capture alone.** Ask the human at the display first. If they see nothing, the capture is the suspect.
2. **Measure pixels no code touches** — window chrome, a bare gutter, the title-bar strip — across the frames of interest. If those move, the whole frame's tone curve moved: capture artifact.
3. **Separate "content changed" from "curve changed" per region.** Ratios that differ between a bright region and a dark one indicate a curve, not a uniform filter.
4. **Record the display's HDR state with every recording you keep as evidence**, and re-record with HDR off when the evidence matters.
5. **Re-read older frame evidence with the same doubt.** Ours: a "white-art pop in ONE frame" filed a month earlier from user-captured frames through the same pipeline was partly this.

The ffmpeg one-liners (Git Bash on Windows; `crop=W:H:X:Y`):

```bash
# mean gray of one region in one frame
ffmpeg -v error -i frame.png -vf "crop=16:200:2:800,scale=1:1,format=gray" \
  -f rawvideo -pix_fmt gray - | od -An -tu1

# the same region as a timeline, one number per third of a second
ffmpeg -v error -i rec.mp4 -vf "fps=3,crop=16:200:2:800,scale=1:1,format=gray" \
  -f rawvideo -pix_fmt gray - | od -An -tu1 -w1000

# contact sheet to find the beat (5 columns; drawtext needs fontconfig, skip it)
ffmpeg -v error -ss 0.30 -t 1.0 -i rec.mp4 -vf "scale=400:-1,tile=5x6:padding=4" sheet_%02d.png
```

## What the recording still told us

The capture was wrong about *brightness* and right about *sequence*. Frame-stepping still showed the real defect — a hand-off where one composition was unmounted and another mounted, with the logo appearing in the same frame — because sequence survives tone mapping. Use recordings for *when* and *what order*; use the display and untouched-pixel measurements for *how bright*.

## What NOT to do

- **Don't tune animations against a capture's brightness.** We nearly filed a compositing bug with numbers that were partly the recorder.
- **Don't assume a flicker report and a recording show the same thing.** The recording can add a step the eye doesn't see, and it can also lift the black level so a real step looks worse than it is.
- **Don't trust `drawtext` for frame labels on a stock Windows ffmpeg** — no fontconfig, it segfaults. Read frame numbers from tile order.

Related: `crossfade-luminance-gap-and-view-transitions.md` (a luminance artifact that IS in the page, and how to compute it), `instrument-before-patching.md`.
