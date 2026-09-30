---
stack: [css, animation, web]
kind: pattern
last_verified: 2026-09-30
---

# Scroll-driven motion without a library: one scroll handler writes a progress variable, CSS does the rest

**One-liner:** for scroll-linked effects (a screenshot tilting flat and sharpening, a pinned "three beats" story, a section that travels sideways while you scroll down), you need no animation library. One rAF-throttled scroll handler turns each tagged element's position into a 0 to 1 progress number and writes it to a CSS custom property `--p`. Every visual (transform, filter, opacity) is then a `calc()` of `--p` in the stylesheet, so the JS stays about 30 lines and the look stays in CSS.

*Status: proven in a static mock the user reviewed and liked (Playmoir `docs/design/prototype/landing-motion.html`, 2026-09-30). Not yet on a live site or measured on the budget-laptop target; update this line when it is.*

## The three progress formulas

With `r = el.getBoundingClientRect()` and `vh = innerHeight`:

| Kind | Formula | 0 means | 1 means |
|---|---|---|---|
| **view** (element passes through the screen) | `(vh - r.top) / (vh + r.height)` | its top just entered at the bottom | its bottom just left at the top |
| **pin** (a tall section whose child is `position: sticky; top: 0; height: 100vh`) | `-r.top / (r.height - vh)` | the pin engages | the pin releases |
| **sideways travel** (inside a pin) | CSS: `translateX(calc(var(--p) * var(--travel) * -1))`, with `--travel = track.scrollWidth - innerWidth` measured in JS | first panel in view | last panel in view |

Clamp each to [0, 1] before writing. The pin's length (`height: 360vh` or similar) sets how much scrolling each beat takes. For discrete beats, derive the index as `Math.min(n - 1, Math.floor(p * n))` and toggle an `.on` class, letting CSS transitions handle the swap.

## Making it feel right

- **Finish early.** A view-progress effect that ends at `p = 1` ends as the element leaves the screen, so nobody sees the final state. Derive a faster sub-progress in CSS: `--q: clamp(0, calc(var(--p) * 1.9), 1)` lands the end state just past halfway.
- **Animate only compositor-friendly properties** (transform, opacity) plus filter where it earns its cost. Large `blur()` on a big image is the expensive one: keep it small, or drop it on low-end targets.
- **One handler, rAF-throttled, passive:** a `ticking` flag, a `requestAnimationFrame` callback, and `{ passive: true }` on the listener.

## Gotchas

1. **Read all, then write all.** Writing `--p` invalidates style, so reading the next element's rect straight after forces a fresh layout on every element, every frame. Loop once to collect rects, then loop again to write. (The 2026-09-30 mock interleaves them; fix it when porting.) Same family as `webview2-react-render-traps.md` Trap 8.
2. **Measure travel when the section is visible.** `scrollWidth` of a `display: none` subtree is 0, so a travel measured at load while the section is hidden stays 0 and nothing moves. Re-measure on resize, on font load, and whenever the section is shown.
3. **The pin needs height > 100vh**, or `r.height - vh` is ≤ 0 (guard the division).
4. **Reduced motion:** with `prefers-reduced-motion`, set the end state directly (`--p: 1`, beats all visible or stacked) instead of scroll-scrubbing.

## Why not CSS `animation-timeline: view()`

It expresses the same idea natively and needs no JS. Check its current cross-browser support before choosing it; at the time of the mock the JS version was chosen so the effect behaves the same everywhere. The formulas above are also what you'd reach for to polyfill it.

## Related

- `runtime-animation-profiler-hud.md`: measure that the handler isn't costing frames.
- `motion-mock-harness.md`: the toggles used to judge these effects.
