---
stack: [css, animation, web]
kind: pattern
last_verified: 2026-09-30
---

# Cursor "torch" reveal: two synchronized layers, the sharp one masked by a radial gradient at an eased cursor

**One-liner:** to make a faded, desaturated field come alive only where the cursor is (a wall of game covers that "remember" themselves under a torch), stack two identical layers. The bottom one is dimmed with `filter`, the top one is sharp and masked by `mask-image: radial-gradient(circle R at var(--mx) var(--my), #000 35%, transparent)`. JS only moves `--mx`/`--my`, easing them toward the pointer each frame so the light trails like a lamp.

*Status: built in Playmoir's landing mock, direction C (2026-09-30). The user reviewed and liked the mock; not yet shipped, and not yet measured on the budget-laptop target.*

## The parts

```css
.dim   { filter: grayscale(1) brightness(0.32); }
.sharp {
  mask-image: radial-gradient(circle 260px at var(--mx) var(--my), #000 35%, transparent 100%);
}
```
```js
let tx, ty, cx, cy;                       // target and current
hero.addEventListener('pointermove', e => { tx = e.clientX - heroRect.left; ty = e.clientY - heroRect.top; });
(function loop() {
  cx += (tx - cx) * 0.12; cy += (ty - cy) * 0.12;       // ease toward the pointer
  sharp.style.setProperty('--mx', `${cx + heroRect.left - sharpRect.left}px`);
  sharp.style.setProperty('--my', `${cy + heroRect.top - sharpRect.top}px`);
  requestAnimationFrame(loop);
})();
```

## Gotchas

1. **The two layers must be truly identical and in sync.** If the content moves (drifting columns), build both layers from the same deterministic list and give them the same animation, duration and start time. Any difference shows as a double image inside the torch. Never randomize per layer.
2. **Mask coordinates are relative to the masked element's own box.** If the layer overhangs its section (`inset: -10% -4%` so drifting edges never show), add the offset between the section and the layer, or the light sits off the cursor.
3. **Phones have no cursor.** Pick a touch fallback up front: drive the torch from scroll position, a slow autonomous wander, or tap. Otherwise mobile visitors see only the dim layer.
4. **Cost is two full layers.** Twice the paint, plus the filter. Keep the dimmed layer's filter static (don't animate the filter itself), and pause the rAF loop when the section is off-screen. The mock's loop runs forever; fix that when porting.
5. **Reduced motion:** stop the drift and leave the torch following the pointer (it's direct manipulation, not ambient motion), or show the wall fully sharp.

## Related

- `scroll-progress-as-a-css-variable.md`: the same "JS writes one custom property, CSS renders" split.
- `animation-keyed-to-creation-not-content.md`: why the two layers must be built from the same data, not two separate renders.
