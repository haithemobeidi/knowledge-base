---
stack: [animation, testing, ios, web, process]
kind: pattern
last_verified: 2026-10-13
---

# Verify motion frame by frame, deterministically: real-time glances and 1 s samples miss what users see

**One-liner:** an automated "does the animation look right" check that watches in real time is blind twice over. In a hidden browser tab `requestAnimationFrame` and `IntersectionObserver` don't fire, so scroll-driven motion looks dead. And sampling a recording once a second missed three separate bugs in an iOS flight that the user saw at once. Step motion deterministically: on the web, pause the Animation objects and set `currentTime`; on iOS, record the simulator, slow the app's own motion, and contact-sheet the frames at 30 fps.

*Playmoir: the website, 2026-10-02; the iOS game-page flight, 2026-10-13.*

## Web: drive time yourself

A headless or background tab throttles rAF to nothing and never reports intersections, so a page whose motion is scroll- or rAF-driven appears frozen to a script, which reads as "broken" when it isn't, or "fine" when the frames are never rendered. Instead:

```js
for (const a of document.getAnimations()) a.pause();          // CSS animations + transitions + WAAPI
for (const t of [0, 100, 200, 300, 400, 520]) {
  for (const a of document.getAnimations()) a.currentTime = t;
  await screenshot(`frame-${t}.png`);
}
```

`getAnimations()` returns `CSSAnimation`/`CSSTransition` objects too, so this covers CSS-only motion. For scroll-driven effects, set the scroll position and dispatch the scroll handling explicitly.

## iOS simulator: record, slow down, sheet it

1. A debug-only launch flag scales every app animation: `-slowMotion 8` read from `UserDefaults` in the motion constants (always 1 in release). XCUITest passes it via `TEST_RUNNER_<NAME>` env vars, which reach the test runner's environment.
2. Record while a UI test drives the motion: `xcrun simctl io "iPhone 17" recordVideo --codec h264 --force flight.mov`, stopped with SIGINT.
3. No ffmpeg needed: a 30-line Swift script with `AVAssetImageGenerator` (zero tolerance before/after) pulls frames at chosen times into one contact-sheet PNG, or two frames side by side at full resolution with gridlines for measuring a shift.
4. Look at the hand-off frames especially: the last frame of the flying copy against the first frame of the real view.

What it caught that a 1 s sample and a full-speed glance didn't: the art not yet downloaded during the flight (it popped in on landing); the flying cover drawn twice too large because a fill image sized its frame; a ~45 pt sideways jump at hand-off; and iOS 26's scroll-edge blur appearing on the real page but not the flying copy (`.scrollEdgeEffectHidden(true, for: .top)`). See `swiftui-layout-and-animation-traps.md`.

## The rule

Never sign off motion from a real-time look or a coarse sample. Step it, and compare hand-off frames side by side. The user's eye at full speed is the final check, not the first.

## Related

- `motion-mock-harness.md` (speed multiplier and replay in HTML mocks), `film-it-adb-screenrecord.md` (the Android recording side), `screen-recordings-lie-about-luminance.md`.
