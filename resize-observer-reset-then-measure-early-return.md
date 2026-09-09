---
stack: [dom, react, web, layout, css-grid]
kind: gotcha
last_verified: 2026-09-09
---

# A "reset, then measure" layout hook with an early return leaves the reset in place — and ResizeObserver guarantees that path runs one frame after mount

**One-liner:** A measure-and-apply layout hook that first CLEARS its own inline styles "to measure the natural box", then bails with a same-as-last-time early return, has just un-applied itself — the browser renders whatever the stylesheet says instead of what the hook computed. `ResizeObserver` makes this a certainty, not a race: it fires once on `observe()`, and again every time your own applied styles change the element's height, so the early-return path runs one frame after mount, every mount. While the hook's output and the stylesheet fallback happen to agree, nothing is visibly wrong and the hook can ship "working" for weeks. The day they differ, the element flashes between the two layouts on every resize tick and comes to rest on the fallback.

## The failure shape

```ts
useLayoutEffect(() => {
  let lastKey = '';
  const apply = () => {
    // "Measure the natural box: drop our own geometry first so a later pass
    // does not measure the previous pass's padding."
    el.style.gridTemplateColumns = '';
    el.style.padding = '';
    const rect = el.getBoundingClientRect();
    const key = computeKey(rect);          // cols / width / pad
    if (key === lastKey) return;           // <-- returns with the styles CLEARED
    lastKey = key;
    el.style.gridTemplateColumns = `repeat(${cols}, ${w}px)`;
    el.style.padding = `...`;
  };
  apply();
  const ro = new ResizeObserver(() => requestAnimationFrame(apply));
  ro.observe(el);
  ro.observe(el.parentElement);
  return () => ro.disconnect();
}, [el]);
```

Timeline at mount: `apply()` computes and sets the geometry (correct, for one frame). `observe()` delivers its initial callback → next frame `apply()` clears the styles, measures, computes the same key, returns. The inline styles are now empty; the element renders with the class-based fallback template. Any later resize repeats the pair: set (key changed) → own height changes → RO fires → clear → same key → return. Set, fallback, set, fallback — and the LAST event after a drag stops is always the RO echo of the last set, so it rests on the fallback.

## Why it hides

- **Same answer, two authors.** In the case this came from, the hook's `repeat(5, 230px)` and the fallback `repeat(auto-fill, minmax(220px, 1fr))` produced the same five columns within a fraction of a pixel. The whole *point* of the hook (whole-device-pixel columns so a moving tile lands crisp) was invisible to the eye at rest, and the sharpness measurements had been taken during the one frame the hook was in effect.
- **The bug is in the comment.** "Drop our own geometry first so we measure the natural box" reads as diligence. Nobody questions a line that explains itself.
- **The symptom arrives with an unrelated change.** The flash appeared the day the computed template was changed to differ from the fallback (a zoom rule replacing a fill rule). The hook "had been working" — so the new rule got blamed first.

## The fixes, in order of preference

**1. Measure something your own styles cannot move.** `getBoundingClientRect()` on a block element returns the border box, which is sized by the parent — your own inline `padding` and `grid-template-columns` do not change it. So there was never a reason to clear before measuring. Delete the clears; the early return becomes safe and every re-apply is an idempotent no-op:

```ts
const apply = () => {
  const rect = el.getBoundingClientRect();   // border box — unaffected by our padding/template
  const key = computeKey(rect);
  if (key === lastKey) return;               // nothing was touched, so nothing is lost
  lastKey = key;
  el.style.gridTemplateColumns = /* ... */;
};
```

**2. If you truly must reset to measure, the early return must re-apply.** Store the last applied style values alongside the key and restore them on the early-return path. Clunkier, but correct.

**3. Or compare before you mutate.** Measure first (see 1), decide, and only then touch styles — a mutation that happens only after the decision cannot be left half-done.

The general rule is older than this bug: **an early return after a mutation must undo or complete the mutation.** "Reset → measure → maybe bail" violates it by construction.

## ResizeObserver specifics worth knowing

- **It fires on `observe()`** (spec: an observation is delivered when observation starts if the element is rendered with a non-zero size). Any hook that applies once and then observes will get a second `apply` one frame later. Your "first run" is never the last run.
- **Your own writes trigger it.** Setting a grid's template changes its height → the RO on that element fires → your callback runs again. Without an idempotence check this is a loop; with a *broken* idempotence check (this article) it is a flip-flop.
- **Observing the parent too is fine** — a cheap, idempotent re-apply is the price. Just make sure re-apply IS a no-op when nothing changed.

## How to confirm it in 30 seconds

Make the hook's output deliberately absurd — `repeat(2, 400px)`, a lurid `outline` — and reload. If the element renders the stylesheet's layout at rest anyway, the hook's output is not holding. This beats DevTools: the inline style attribute you inspect there may be the one written *before* the clearing pass or the empty one after it, depending on when you look.

## Related

- [webview2-react-render-traps.md](./webview2-react-render-traps.md) — trap 8 is the neighbouring mistake in the same family: mutating and measuring in one pass gives you the pre-mutation rect. This article is the inverse: mutating (clearing) *before* measuring and then not restoring.
- [exit-animation-props-captured-at-unmount.md](./exit-animation-props-captured-at-unmount.md) — the same "silently wrong for months, surfaces when you touch something adjacent" shape.
