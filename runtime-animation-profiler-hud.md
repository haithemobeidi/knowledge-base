---
stack: [react, dom, performance]
kind: pattern
last_verified: 2026-07-08
---

# A dev-only in-app HUD for judging animation perf by numbers, not vibes

**One-liner:** a small, dependency-free React component that measures real frame timing during a specific animation and renders the numbers in a corner overlay — on whatever machine the build is running on, no DevTools/profiler attach required. Distinguishes two failure signals that look the same to the eye but have different root causes: **frame-skip** (the animation is janky right now) vs. **accumulation** (the app gets worse over time — a leak, not a one-off slow frame).

## Why this beats "does it feel smooth" during development

A GPU compositor-layer leak or a growing DOM produces a specific signature: smooth on a fresh app launch, degrading over a handful of repetitions, then plateauing (as opposed to an unbounded climb, which points at a JS heap leak instead). You cannot reliably eyeball "smooth → slightly worse → slightly worse again → plateaus" — but a HUD that prints the numbers after every repetition makes the shape of the degradation immediately legible, and tells you which failure family to chase before you open a profiler at all.

## Refresh-rate-agnostic jank detection

Don't hardcode "60fps, so &gt;16.7ms is a dropped frame" — that assumption breaks on 120/144Hz displays. Instead, compute the **median inter-frame delta over the current measurement window** (robust to the very slow frames you're trying to detect) and flag anything over 1.5x that median:

```ts
function computeJank(frameTimestamps: number[]) {
  const deltas = frameTimestamps.slice(1).map((t, i) => t - frameTimestamps[i]);
  const median = [...deltas].sort((a, b) => a - b)[Math.floor(deltas.length / 2)] ?? 16.67;
  const jankThreshold = median * 1.5;
  const jank = deltas.filter((d) => d > jankThreshold).length;
  const longestMs = Math.max(...deltas);
  return { jank, longestMs, fps: (1000 * (frameTimestamps.length - 1)) / (frameTimestamps[frameTimestamps.length - 1] - frameTimestamps[0]) };
}
```

Sample continuously via `requestAnimationFrame` for the duration of the animation being measured (start on animation-begin, stop on animation-end), push `performance.now()` each tick, then run the above once the animation completes.

## Accumulation signals — heap, DOM count, GPU-layer proxy, portal count

Snapshot four cheap signals at the end of each measured repetition:

```ts
function snapshotMemory() {
  const mem = (performance as any).memory; // Chromium-only (incl. WebView2); undefined elsewhere
  return {
    heapMb: mem ? Math.round(mem.usedJSHeapSize / 1_048_576) : 0,
    nodes: document.getElementsByTagName('*').length,
    // Inline will-change is a cheap proxy for "promoted to its own GPU compositor layer" —
    // if this climbs across repetitions without settling, you're leaking compositor layers.
    willChange: document.querySelectorAll('[style*="will-change"]').length,
    // Direct children of <body>: portal roots (modal libraries, tooltip libraries,
    // AnimatePresence-style overlays) mount here. If this climbs alongside `nodes`,
    // suspect a portal that isn't unmounting rather than an in-tree leak.
    bodyChildren: document.body.childElementCount,
  };
}
```

Plot `nodes`/`heapMb`/`willChange`/`bodyChildren` per repetition in the HUD. A plateau after N repetitions = compositor/GPU-resource saturation (usually benign, or fixable by capping concurrent GPU-promoted layers). An unbounded climb = an actual leak (something isn't unmounting or isn't clearing a ref).

## Leak fingerprinting: WHICH element is leaking, not just "something is"

The single most useful technique here — turns "the DOM node count keeps climbing" into "here is the exact element type and class string to grep for":

```ts
function tagHistogram(): Record<string, number> {
  const h: Record<string, number> = {};
  for (const el of document.getElementsByTagName('*')) h[el.tagName] = (h[el.tagName] ?? 0) + 1;
  return h;
}

// First measured repetition sets the baseline; every subsequent one reports
// cumulative growth vs. that baseline — over N repetitions a small per-cycle
// leak (+3/cycle) becomes impossible to miss ("+45" after 15 cycles).
function leakDelta(baseline: Record<string, number>, current: Record<string, number>): string[] {
  return Object.entries(current)
    .map(([tag, n]) => [tag, n - (baseline[tag] ?? 0)] as const)
    .filter(([, delta]) => delta > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([tag, delta]) => `${tag.toLowerCase()} +${delta}`);
}
```

Two refinements that make this even sharper:
- **Fold in your own component markers as pseudo-tags** — count `document.querySelectorAll('[data-my-component]').length` alongside the native tag counts, so growth points at a specific component's subtree, not just "DIV is growing" (which could be anything).
- **When one tag is the top offender, histogram it AGAIN by className** (or by parent tag+class, for class-less elements) to get the exact Tailwind/CSS class string — distinctive enough to `grep` straight to the source line responsible, no guessing which of the app's 40 components renders that tag.

## Shape of the HUD itself

- Gate the entire file behind your framework's dev-only flag (`import.meta.env.DEV` for Vite) so it tree-shakes out of production entirely — zero prod cost.
- Fixed-position corner overlay, monospace, small — a scrolling table of the last ~16 measured repetitions (duration, jank count, worst frame, fps, heap, node count, will-change count, body-children count), plus a rolling "leaking since start: tag +N, tag +N..." line once a baseline exists.
- Collapse/clear controls so it doesn't get in the way when you're not actively investigating.

## What NOT to do

- Don't assume 60fps and hardcode a 16.7ms jank threshold — compute it from the actual observed frame cadence so the tool works unmodified on 120/144Hz hardware.
- Don't rely on `performance.memory` existing — it's Chromium-only and non-standard; feature-detect and report 0/unavailable elsewhere rather than throwing.
- Don't ship this to production, even inert — gate the whole module import behind the dev flag so bundlers can tree-shake it, not just hide it behind a runtime `if`.
