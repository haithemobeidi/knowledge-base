---
stack: [react, css, framer-motion, animation]
kind: pattern
last_verified: 2026-07-08
---

# Shared-element "morph" transitions: a clip-path FLIP variant, and why mixing animation engines causes jutter

**One-liner:** the classic FLIP technique (clone the element, animate `transform: scale()` from the start rect to the end rect) blurs images and warps text because it's literally rasterizing content at intermediate sizes. An alternative: size a single ghost element to the **union bounding box** of both rects, render the content at each target's *native* size inside it, and animate `clip-path` to reveal one region then the other. `transform` only ever translates — it never scales — so nothing is ever rendered at a stretched size.

## The technique

1. **Compute the union box**: as wide/tall as whichever of the two rects (source, destination) is larger in each dimension. Pin the ghost element there.
2. **Two clip-path insets**, each cropping the union box down to one of the real rects:
   ```ts
   const boxW = Math.max(target.width, source.width);
   const boxH = Math.max(target.height, source.height);
   const sourceClip = `inset(0px ${boxW - source.width}px ${boxH - source.height}px 0px round ${sourceRadius})`;
   const targetClip  = `inset(0px ${boxW - target.width}px  ${boxH - target.height}px  0px round ${targetRadius})`;
   ```
3. **`transform: translate(dx, dy)`** moves the whole union box between the two rects' positions — never a scale.
4. **Two images (or content layers) at their OWN native size**, both absolutely positioned at the union box's top-left, crossfading at a timed pivot partway through the transition — rather than one image being stretched from small to large.
5. **Corner radii read from the real elements' own CSS variables** (not hardcoded px), so the morph's rounding matches whatever the destination component actually uses — if the theme's radius token changes later, the morph stays in sync automatically instead of drifting into a mismatched corner on landing.

This generalizes FLIP to "shared element transitions between two differently-shaped, differently-cropped containers" (e.g. a square grid thumbnail morphing into a wide banner) without ever rasterizing a scaled bitmap.

**Gotcha this technique specifically avoids:** if you naively size the ghost to only ONE of the two rects (say, the destination banner) and clip-path down to the smaller source rect, you clip content that's taller than the destination — e.g. a portrait-oriented source card whose caption/footer sits below the banner's height gets silently cut off. Always size the ghost to the **union**, never to either rect alone.

## The gotcha that costs the most debugging time: don't mix animation engines on one coupled transition

If your JS animation library drives `transform`/`opacity` via the browser's native Web Animations API (WAAPI) — which runs on the **compositor thread**, no per-frame JS — but you also hand it `clip-path` in the same `animate()`/`transition` call, many libraries fall back to their own **JS interpolator** for `clip-path` specifically (WAAPI support for `clip-path` interpolation is inconsistent across browsers, so libraries often special-case it). That JS interpolator runs on `requestAnimationFrame` on the **main thread** — a different clock than the compositor.

Result: `transform` and `clip-path` are supposed to move in lockstep (the union-box position and its crop should update together), but they're being driven by two different schedulers. Under any main-thread pressure (React re-renders, other work queued), the two drift apart frame-to-frame — visible as jutter/shimmer where the crop boundary doesn't quite track the translating box.

**Fix: drive `clip-path` via a native CSS transition, applied imperatively, so it also lands on the compositor thread:**

```ts
useLayoutEffect(() => {
  const el = ghostRef.current;
  if (!el) return;
  // Mount at the START clip with no transition (instant) — flush layout —
  // then re-enable the transition and set the END clip. The offsetHeight
  // read forces the browser to register the 'none' transition before the
  // target value change, so the next paint actually starts a transition
  // instead of jumping straight to the end state.
  el.style.transition = 'none';
  el.style.clipPath = startClip;
  void el.offsetHeight;                 // flush
  el.style.transition = `clip-path ${durationMs}ms ${easingCss}`;
  el.style.clipPath = endClip;
}, [phase, startClip, endClip]);
```

Meanwhile `transform`/`opacity` keep going through the JS library's normal `animate` prop (WAAPI path). Now all THREE properties ride the same thread with matched timing, and the drift disappears. The general rule: **when a shared-element transition couples multiple CSS properties that must move in exact lockstep, verify they're all on the same animation engine/thread — don't assume your animation library treats every property identically under the hood.** If one property's browser-native interpolation support is shakier than another's (clip-path is the common offender), that property is the one likely to get silently downgraded to a different execution path.

## Two supporting techniques worth stealing independently

**Adaptive wait for an async-mounted measurement target**, instead of a fixed timeout guess:

```ts
const startFlight = (attemptsLeft = 12) => {
  const target = document.querySelector('[data-morph-target]');
  if (target) {
    const r = target.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) { /* got it — start the transition */ return; }
  }
  if (attemptsLeft > 0) {
    requestAnimationFrame(() => startFlight(attemptsLeft - 1));
    return;
  }
  /* bounded fallback rect after ~12 frames (~200ms) so the transition never hangs */
};
```
rAF-polling (bounded, e.g. 12 attempts ≈ 200ms) adapts to real mount latency — a fast machine starts the transition within a frame or two, a slow one gets a longer wait automatically — without a fixed `setTimeout` guess that's either too short (races the target's mount) or wastes time on fast machines. The width/height `> 0` check specifically catches "mounted but not yet laid out," which a plain existence check (`if (target)`) would miss.

**Re-measure the LIVE source rect at reverse-transition time, not the rect captured at click time.** If the source element's position can change while the destination is open (grid reflow, filter/sort change, window resize), the reverse transition must re-query the source element's current position via a stable identifier (a `data-id` attribute), not reuse the stale rect from when the forward transition started — otherwise the reverse animation flies to where the element USED to be. If the source element is gone entirely (deleted, filtered out), skip the reverse transition and just fade — flying to empty space reads as a glitch, not a transition.

## What NOT to do

- Don't scale a rasterized image/text node between two very different sizes as your primary technique — the intermediate blur is visible on anything but tiny size deltas.
- Don't clip to either endpoint rect alone — always use the union bounding box, or content taller/wider than the smaller rect gets silently cut off.
- Don't assume "same animation library, same `animate()` call" means "same execution thread" for every property you're animating together. Verify the properties that must stay in lockstep are actually on the same thread; if one drifts, suspect a per-property engine fallback.
