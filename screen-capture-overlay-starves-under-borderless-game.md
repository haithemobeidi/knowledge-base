---
stack: [windows, desktop-overlay, screen-capture, hdr, debugging, process]
kind: gotcha
last_verified: 2026-10-16
---

# A screen-capture overlay starves under a borderless game that bypasses the compositor: the copy it reads is stale and, in HDR, wrong

**One-liner:** an overlay that works by capturing the desktop (NeuralScreen, Lossless Scaling, OBS display capture, Magpie, anything on Desktop Duplication or Windows.Graphics.Capture) dropped to 15 to 19 fps whenever a borderless game had focus and jumped past 120 the instant the game lost focus, with the GPU nearly idle. No load lever touched it: not a game frame cap, not GPU scheduling priority, not admin rights. The game was being presented straight to the display from its own swap chain (a hardware plane, not the composed desktop), so the desktop image the capture API reads refreshed only now and then, and because the game was outputting HDR10 while Windows HDR was off, that image was also flat and washed. Two fixes measured: turn **Windows HDR on** (the borderless game is composed again, captured at the game's full rate, with correct colour), or run the game **Windowed** sized to the screen (a bordered window is always composed). Read the app's own phase timings before trying the upstream thread's fixes.

*Division2-DLSS5: NeuralScreen 2.4.0 over The Division 2, RTX 5090, Windows 11 (26200), 2026-10-16.*

## Symptom

- The overlay reports 15 to 19 fps while the game draws, and 120 to 166 fps as soon as the game loses focus (Alt-Tab), same settings.
- Capping the game at 120, then 60, moves the overlay by one frame. Running the overlay as administrator with its worker's GPU scheduling class set to realtime (the fix the upstream issue thread recommended) changes nothing: 15 to 19 fps either way.
- Switching the app from display capture (Desktop Duplication) to window capture (Windows.Graphics.Capture) makes it worse: 10 fps flat.
- Every image of the desktop is flat: blacks around 40/255, washed colours, including the untouched half of the overlay's wipe comparison, while the panel itself looks right.

## The measurement that named it

The app's phase profiler (`NS_PHASE=1`) printed per-frame timings:

| phase | time |
|---|---|
| neural pass on the GPU | 3.4 ms |
| wait for a captured frame, Desktop Duplication | alternating about 5 ms and 85 ms |
| wait for a captured frame, Windows.Graphics.Capture | 92 to 100 ms |
| fresh source frames per second | 19 (display capture), 10 (window capture) |

GPU work was a tenth of the frame budget. The overlay spent its time waiting for the desktop image to change: Windows handed it a new composed frame about 19 times a second while the game itself ran at 60 to 120.

## Cause

A borderless window that covers the screen and has focus can be scanned out directly from its own swap chain (independent flip on a hardware plane, multi-plane overlay); the Desktop Window Manager then stops composing it into the desktop image every frame. Capture APIs read that desktop image. So the game is on screen at full rate while the copy the overlay gets updates only when the compositor happens to run, and a frame cap on the game does nothing because the compositor, not the game, decides when the copy refreshes. Alt-Tab fixes it instantly because a game without focus loses the plane and is composed again.

The colour half has the same root. With Windows HDR off, the game's HDR10 swap chain drove the panel in HDR directly, and the composed desktop copy held the 10-bit PQ-encoded buffer read as SDR, which comes out as flat grey. The overlay was reproducing a wrong input, not washing a right one.

The upstream issue blamed hardware-accelerated GPU scheduling and GPU contention. That is a plausible story for a different symptom (both apps slow); the measured shape here was one idle app waiting on another's frames.

## Fixes measured

| game mode | Windows HDR | game cap | overlay fps | colour of the captured copy |
|---|---|---|---|---|
| Borderless, in focus | off | 120 | 19 | flat |
| Borderless, in focus | off | 60 | 17 to 18 | flat |
| Borderless, Alt-Tabbed | off | 120 | 120 to 166 | flat |
| Windowed, sized to the screen | off | 60 | 60 flat (capture waits 8 to 15 ms) | flat (game in HDR10), right (game HDR off) |
| Windowed, sized to the screen | on | off | 85 to 90 | right |
| Borderless, in focus | on | off | 135 to 150 | right |

- **Windows HDR on** (Win + Alt + B) with the game left in HDR10. The borderless game is composed again, so capture runs at the game's rate and the copy matches the panel. One switch fixes both symptoms. The app's log confirmed the capture turned FP16 and its SDR conversion looked right to the user.
- **Windowed** mode sized to the display, title bar pushed above the top edge (window rect (-8,-8) to (3448,1448) on a 3440x1440 panel). It looks like borderless and a bordered window is never scanned out directly. This fixes the rate with Windows HDR off too, but not the colour while the game outputs HDR10.
- An uncapped source judders because the overlay repaints whenever a frame lands. A game cap at a rate the overlay sustains gives even pacing.

Not measured: a borderless **SDR** game with Windows HDR off. The runs that starved all had the game in HDR10, so this lesson cannot say whether the plane alone or the HDR10 output on the plane is what Windows HDR on removes. The remaining system-wide lever, turning multi-plane overlay off (`HKLM\SOFTWARE\Microsoft\Windows\Dwm`, DWORD `OverlayTestMode` = 5, restart, reversible by deleting it), was never needed. It is a Windows-level change: offer it as the user's decision with the trade-off stated, never as a first move.

A second effect, measured with PresentMon (Intel's frame-time recorder) once the capture problem was solved: with the game **windowed** under the overlay and Windows HDR on, the game itself presented in bursts of about five frames at 60 fps separated by stalls of 0.1 to 1.9 s (87 stalls, 49 of 60 seconds), each stall CPU-side inside the game (the frame's CPU time was the whole gap, GPU busy a normal 5 to 8 ms, no wait in Present), while the same game with the overlay closed presented 60 a second with a 19.5 ms p99. The overlay's presenter sat in a hardware plane ("Hardware Composed: Independent Flip") above the composed game window, running a steady 66 a second, which is also the number a frame counter shows: the overlay's cadence, not the game breaking its cap. Consistent with the game throttling itself because the compositor reports its window covered; not GPU contention (overlay GPU busy 4.5 ms a frame, game 6 ms, with the GPU mostly idle). The same game borderless had fed the overlay 135 to 150 fresh frames a second earlier that day, so the stall belongs to the composed-window case; the borderless capture is the next measurement. When a game gets choppy under a capture overlay, record the game's own presents before touching GPU priority or caps: a CPU-side gap with an idle GPU is an engine deciding not to run.

## Pixel checks that separated capture from effect

- Overlay pass-through pixels equalled a Windows screenshot of the game within 1 unit. The overlay reproduces its input.
- A grey-levels test window (0, 16, 64, 128, 192, 235, 255) came through the overlay as 3, 17, 64, 125, 190, 232, 253. The pipeline is faithful.
- A screenshot of the game alone, overlay closed, was just as flat while the panel looked right. The composed copy and the displayed signal differ at the source.
- Display gamma ramp identity on both monitors, Night Light off.

The move that decides it is the third bullet: compare the **untouched** half of the comparison to a capture of the game with the overlay closed. If they match and both look wrong, the capture is wrong, not the effect. Same family as [screen-recordings-lie-about-luminance.md](./screen-recordings-lie-about-luminance.md), opposite direction: there the capture carried a change the display never showed; here the display carried one the capture never got.

## Method: the upstream thread's diagnosis is not yours

The project's issue on exactly this symptom (overlay at 1.5 fps with a game running) closed with "turn hardware GPU scheduling off, cap the game, or run as administrator with realtime GPU priority", and the reporter's own numbers supported a contention story (game 159 to 55 fps, overlay 1.5 to 55 with realtime). Two of the three were applied here and moved nothing; the user declined the Windows setting. The phase breakdown separated "waiting for a frame" from "starved of GPU" in one run. Same rule as [instrument-before-patching.md](./instrument-before-patching.md): when a proposed fix is cheap, try it once, but read the app's own timing before the second one. A symptom that pattern-matches an upstream thread can have a different cause on your machine.

## Tells, ten seconds each

- Capture wait dominates the phase breakdown while GPU work is a few milliseconds.
- Alt-Tab, or any focus loss, restores full rate immediately.
- A game frame cap and a GPU priority change leave the overlay's rate where it was.
- Window capture is slower than display capture, not faster.
- The untouched half of the comparison looks as wrong as the processed half.
- The game's own presents come in short bursts with CPU-side gaps while the overlay covers it, GPU idle: an occlusion throttle, not load.

## Related

- [always-on-top-overlay-vs-exclusive-fullscreen.md](./always-on-top-overlay-vs-exclusive-fullscreen.md) — the painting half of the same family: a window cannot out-paint exclusive fullscreen but still eats clicks. That lesson calls borderless "composited, keep the overlay", true for painting over it and not enough for capturing it: a borderless game on a hardware plane is on screen without being in the composed image.
- [screen-recordings-lie-about-luminance.md](./screen-recordings-lie-about-luminance.md) — the capture carries a luminance step the display never showed.
- [instrument-before-patching.md](./instrument-before-patching.md) — read the surface's own decisions before the next patch.
- [negative-control-before-trusting-a-probe.md](./negative-control-before-trusting-a-probe.md) — the grey-levels window is the negative control for "the overlay washes the colours".
