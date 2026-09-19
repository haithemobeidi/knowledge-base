---
stack: [css, animation, react, overlay, ui]
kind: gotcha
last_verified: 2026-09-18
---

# An overlay that lifts `pointer-events` at close-start needs every child to follow — or defend itself

**One-liner:** to let clicks through the moment a close begins, the overlay root sets `pointer-events: none`. But a child anywhere inside it that sets `pointer-events: auto` **re-enables hit-testing for itself**, regardless of the ancestor. So any child that does not join the exit choreography keeps eating clicks and hovers while looking like it is on its way out — and the bug is **temporal**, not spatial, which is why it presents as random.

## Why it reads as a geometry bug for weeks

The symptom is "sometimes clicks land, sometimes they don't, in roughly the same place." That shape sends you to geometry every time: hit-box sizes, `z-index` stacking, a transformed ancestor, viewport compression, a stray full-bleed wrapper. In the case this came from, all three filed hypotheses were geometric and all three were near-misses — plausible, testable, wrong. It cost about three weeks of intermittent investigation.

The reason geometry cannot be the answer is worth keeping, because it is the discriminator: **a mounted, non-click-through overlay is airtight.** If the overlay were simply covering the wrong area, the failure would be stable — the same coordinates would fail every time. A failure that depends on *when* you click, at coordinates that work at other moments, cannot be a spatial split. Something is changing over time, and the only thing changing is the close animation's phase.

**The experiment that settled it:** put `inert` on the background content. `inert` suppresses *everything* — clicks, focus, and hover tooltips. If tooltips still appear from the background while the overlay is "open," the overlay is not covering it. If they stop, the overlay is airtight and your intermittent failure is about phase, not position. That one observation collapsed the entire geometric branch of the search.

## The mechanism

```css
.overlay-root { pointer-events: none; }   /* set at close-start */
.overlay-panel { pointer-events: auto; }  /* ...but this still hit-tests */
```

`pointer-events` is not a hierarchical veto. A descendant can re-enable itself inside a `none` ancestor — that is the documented behaviour and it is the basis of every "click-through except this bit" layout. It means `pointer-events: none` on the root is a statement about the root, not a broadcast.

So at close-start you get a window — the length of the exit animation — where the root says "pass clicks through," the user believes the overlay is leaving, and one fully-opaque, `pointer-events: auto` child is still swallowing input. The narrower the window, the more random it looks.

## Fixes

**1. Make exit a single choreography every surface participates in.** If the close is one state (`closing`) that every animated child reads, then every child's exit is defined in the same place and a child that does not participate is visible in code review as a child with no exit. This is the structural fix: the defect above is really "one surface had a private opinion about closing."

**2. Where a child must keep its own `pointer-events: auto`, make it drop it at close-start explicitly.** Tie it to the same flag:

```tsx
<div
  className="overlay-panel"
  style={{ pointerEvents: closing ? 'none' : 'auto' }}
/>
```

**3. Prefer `inert` on the background over `pointer-events: none` on the overlay, where support allows.** `inert` also removes focusability and assistive-tech reachability, which `pointer-events` does not — an overlay that is click-through but still tabbable is its own bug, quieter than this one.

## How to confirm it in 30 seconds

Slow the exit animation to three seconds and click through the overlay's area during the exit. If clicks land everywhere except over one panel, that panel is the one not following. This is faster and more certain than any amount of DOM inspection, because it makes a millisecond-wide window into a three-second one.

## The general rule

**"Closing" is a phase, not an instant, and every property that makes an overlay an overlay has to be defined across that whole phase.** Opacity, hit-testing, focus containment and scroll locking each need an answer for *open*, *closing* and *closed* — and it is always the middle one that is missing, because it is the only one that is hard to look at.

More generally: when an intermittent failure's coordinates are not stable, stop looking at geometry. Ask what is different about *when* it fails. A spatial hypothesis for a temporal bug produces an endless supply of near-misses, each of which explains most of the evidence.

## What NOT to do

- Don't fix it by shortening the exit animation until the window is too small to hit. The bug is still there and now it is rarer, which is worse.
- Don't put `pointer-events: none !important` on the subtree. It will also break the legitimate "this bit stays interactive" cases the pattern exists for, probably on a different surface, later.
- Don't trust that `pointer-events: none` on a root disables its descendants. It does not, and every layout that uses click-through panels depends on it not doing so.
- Don't discard the near-miss hypotheses silently. Record them — "a mounted overlay is airtight, so a spatial split was impossible" is the sentence that saves the next investigation, and it only exists because three geometric theories were tried first.

## Related

- [exit-animation-props-captured-at-unmount.md](./exit-animation-props-captured-at-unmount.md) — the sibling click-eater: an overlay stranded mounted at `opacity: 0` with `pointer-events: auto` because its unmount bookkeeping was dropped. Same symptom, different cause; check both.
- [layout-shift-mid-press-eats-the-click.md](./layout-shift-mid-press-eats-the-click.md) — another input failure that is about timing rather than position.
- [instrument-before-patching.md](./instrument-before-patching.md) — the general discipline this three-week hunt failed to apply early enough.
