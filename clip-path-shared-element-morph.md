---
stack: [react, css, framer-motion, animation]
kind: pattern
last_verified: 2026-07-29
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

## The other timing trap: discrete hand-offs must OVERLAP, never meet

The section above is about two engines drifting during a *continuous* animation. This one is its discrete cousin, and it produces an intermittent flash rather than jutter.

Every shared-element morph ends in a hand-off: the flying ghost (or the expanded surface) goes away, and the real element it was standing in for becomes visible. The whole illusion rests on those two things being pixel-identical at that instant — which is exactly why it's tempting to schedule both for the same timestamp.

Don't. If the two events are driven by different mechanisms — say a CSS `animation-delay` revealing the real element, and your animation library's `AnimatePresence` unmounting the ghost — they are two independent clocks aimed at one moment. A single frame of skew resolves one of two ways:

- **Ghost leaves last** → both are on screen for a frame. Invisible, because they're identical. Fine.
- **Ghost leaves first** → neither is on screen for a frame. A hole punched through to whatever is behind. **That's the flash.**

You don't control which one wins, and it varies run to run with main-thread load — so the bug is intermittent, unreproducible on demand, and reads like a rendering glitch rather than a logic error.

**The rule: schedule the incoming element to appear BEFORE the outgoing one leaves, with enough margin to absorb scheduling jitter (~100ms is plenty).** An overlap is invisible by construction — the two surfaces matching is the premise of the morph. A gap is never invisible.

```
      reveal real element (t=300)
              ↓
  ─────────────┬──────────────────
               │  both present    │   ← invisible, this is the safe zone
  ─────────────┴──────────────────
                        ↑
              unmount ghost (t=400)
```

Concretely, if the retraction runs 400ms, reveal the underlying element at ~300ms rather than at 400ms. During the overlap the retracting surface is opaque and on top, and by 300ms an ease-out curve has it at ~97% of its final size — the two are indistinguishable.

Two corollaries:

- **Prefer a step to a fade at a hand-off.** Reveal the incoming element with a ~0ms opacity step early, not a fade timed to land exactly at the swap. A fade timed to the instant is the same race with extra frames in which to notice it.
- **An "invisible snap" only stays invisible while something still covers it.** The snap is doing its job *because* another layer is on top when it fires. If you later soften that snap into a crossfade "to make it smoother," you remove the cover and expose everything the snap was hiding — reliably making the transition worse. That's a real regression that shipped in the project this was extracted from, in a commit whose message says it was fixing the very symptom it caused.



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

## The trap inside "if the source is gone, skip the transition": detached is not absent

The advice above — *if the source element is gone entirely, skip the reverse transition* — is right, and the obvious implementation of it is wrong:

```ts
const liveTile = container.querySelector(`[data-id="${id}"]`);
if (!liveTile) { teardownWithoutTransition(); return; }   // looks sufficient. isn't.
```

That guard catches "the element was removed from a container that is still on screen." It does **not** catch "the container itself was unmounted," and the second case is the one that produces a spectacular visual bug.

**Why the null check passes.** You captured `container` as a DOM reference when the transition started. When a framework unmounts a subtree it typically removes only the **outermost host node** of that subtree from the document — the descendants stay attached to that now-detached root (React's `commitDeletionEffects` calls `removeChild` once at the boundary rather than walking every grandchild). So your captured `container` is detached but structurally intact, and **`querySelector` traverses a detached subtree perfectly happily**. The lookup succeeds. You get back a real `HTMLElement`. Everything looks fine.

**Why the result is a corner-flight.** Per CSSOM View, an element with no associated CSS layout box returns a zero `DOMRect` — and a detached element has no layout box. So `getBoundingClientRect()` returns `{x:0, y:0, width:0, height:0}`, and the reverse transition dutifully animates toward the viewport's top-left corner, shrinking to nothing.

> **Signature to memorize: a transition flying to the top-left corner means a zeroed rect.** That's almost always a detached or `display:none` node, not a math error in your positioning code.

**Two guards, at two different moments**, because they cover different windows:

```ts
// 1. At lookup — catches a container that was already unmounted.
if (!liveTile || !liveTile.isConnected) { teardownWithoutTransition(); return; }

// 2. At the instant the rect is committed to the flight — catches anything that
//    unmounts DURING the close (an async re-query resolving, a sync from another
//    device, a scroll-into-view preamble you awaited).
const rect = measuredEl.getBoundingClientRect();
if (!measuredEl.isConnected || rect.width === 0 || rect.height === 0) {
  teardownWithoutTransition(); return;
}
```

**Guard the element you actually MEASURE, not the one you looked up.** If you use a descendant marker to pick the rect (e.g. the tile carries `data-id` but you measure a `[data-morph-rect]` child so the flight lands on just the cover), then a connected *tile* does not prove a connected *cover*. Test the node whose rect you are about to trust.

**Why this reads as intermittent, and why that's misleading.** Whether you hit it depends on whether the container survived, which depends on your data — a list that renders `null` when empty unmounts its whole section when you remove the **last** item, but only removes one child when you remove one of three. Same click, two different code paths, selected by how many items happened to be left. It gets filed as a race and hunted for weeks. It isn't a race; it's deterministic per-case. (A genuine race exists *too* — the removal landing mid-transition — but it is a different, rarer bug, and conflating them sends you looking for timing jitter that isn't there.)

**The structural fix, if you own the list:** don't let the container unmount. A section that renders a collapsed header at zero items instead of returning `null` cannot produce a detached container at all. Keep the guards anyway — they're shared code protecting every other surface that *does* unmount.

## Scoping the lookup and "render nothing when empty" are mutually exclusive

A follow-on that only appears once you fix a *different* bug, and it is worth knowing before you fix that one.

**The other bug first.** A reverse flight has to find the element it should fly back to, usually `container.querySelector('[data-id="..."]')`. If `container` is resolved with `closest('[data-morph-container]')` and the nearest such ancestor is the whole screen root, that lookup spans **every** surface on the page — so the flight lands on the first document-order match, which is the wrong card as soon as two surfaces render the same item. The fix is one attribute: give each list its own `data-morph-container` so the lookup is scoped to the list you actually clicked in.

**What that attribute does to a list that unmounts when empty.** Before, an item card's `closest()` walked up to a screen-root container that never unmounts, so the detached-container bug above was *dormant* — the container outlived any list. The moment the list carries its own container attribute, an `if (!items.length) return null` becomes exactly the detached-container case: click the last item, the list empties, the `<ul>` unmounts, the flight measures a detached node, and the rect comes back zeroed.

So the two changes are individually correct and **jointly required**. Shipping the scoping attribute without making the list permanent trades a wrong-target bug for a zeroed-rect bug. Land them in the same commit.

**And "make the section permanent" is not enough.** The node that must stay mounted is *the one carrying the attribute*, not its parent. This is wrong:

```jsx
<section>                                  {/* permanent — but not the container */}
  {items.length > 0
    ? <ul data-morph-container>{cards}</ul> {/* still unmounts */}
    : <EmptyState />}
</section>
```

The section survives, the `<ul>` doesn't, and the container detaches exactly as before. One list has to render always and swap its *children*:

```jsx
<section>
  <ul data-morph-container>
    {isEmpty ? ghostPlaceholders : cards}
  </ul>
</section>
```

There's a layout dividend for free: placeholders that hold the real grid's dimensions mean the first real item arriving moves nothing on the page, so you also stop the empty→populated transition from shoving content around.

## What NOT to do

- Don't scale a rasterized image/text node between two very different sizes as your primary technique — the intermediate blur is visible on anything but tiny size deltas.
- Don't treat `if (!element)` as "the element is gone." It only means *this lookup returned nothing*. A detached-but-intact subtree returns elements normally and measures as all zeros — check `isConnected` and a non-zero rect, on the node you actually measure.
- Don't clip to either endpoint rect alone — always use the union bounding box, or content taller/wider than the smaller rect gets silently cut off.
- Don't schedule a hand-off's two halves (reveal the real element / remove the ghost) for the same timestamp from two different mechanisms. Overlap them. Meeting exactly is a coin-flip between "invisible" and "one-frame hole."
- Don't soften an invisible snap into a crossfade to make it "smoother" without checking what the snap was hiding — the snap is usually invisible *because* another layer still covers it at that instant.
- Don't add a per-list `data-morph-container` scope without also making that list permanent — the scope is what turns a dormant early-return-when-empty into a live detached-container bug, so the two fixes are jointly required, not independently optional.
- Don't assume making the *section* permanent is enough. The node carrying the container attribute is the one that must never unmount; if the `<ul>` inside a permanent `<section>` still swaps out at zero items, nothing is fixed.
- Don't assume "same animation library, same `animate()` call" means "same execution thread" for every property you're animating together. Verify the properties that must stay in lockstep are actually on the same thread; if one drifts, suspect a per-property engine fallback.
