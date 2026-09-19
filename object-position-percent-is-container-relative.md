---
stack: [css, animation, images, web]
kind: gotcha
last_verified: 2026-09-18
---

# `object-position` percentages are container-relative — the same value crops differently in every box

**One-liner:** a percentage `object-position` does **not** name a point in the image. It names an alignment between the image's overflow and the container's box, so the slice you actually see is a function of **that container's size**. Two boxes of different heights showing the same image at the same `object-position: 50% 30%` display **different parts of the picture**. Any animation that hands an image from one box to a differently-sized box — a rest tile morphing into a hero, a thumbnail expanding into a lightbox — will jump at the handoff, and the jump is in the *art*, not in the geometry you were tweening.

## The mechanism, exactly

With `object-fit: cover`, the image is scaled until it covers the box, so one axis overflows. `object-position` distributes that overflow:

```
overflow_y   = scaled_image_height - container_height
offset_y     = overflow_y × percentage
```

The percentage is applied to **the overflow**, and the overflow depends on the container. Put the same image in a 180px-tall tile and a 420px-tall band, both `cover`, both `object-position: 50% 30%`:

- tile: overflow might be 60px → the crop starts 18px down the scaled image
- band: overflow might be 240px → the crop starts 72px down

Same declaration, different picture. Nothing warns you, because both are individually correct.

## Why it survives review

Each state looks right **in isolation**. You tune the tile until the character's face is framed; you tune the band until the face is framed; both screenshots are fine. The defect only exists *during the transition between them*, which is the one state nobody screenshots. In the case this came from it took three fix iterations and a frame-by-frame scrub to even see — every attempt "fixed" it by re-tuning one of the two endpoints, which by construction cannot work, because the endpoints were never the problem. The handoff was.

That is the tell for this class: **a fix that makes one end better and the other end worse, repeatedly.** If tuning A degrades B and tuning B degrades A, you are not looking at a mis-tuned value, you are looking at a value whose *meaning* changes between A and B.

## The fix: resolve to pixels against the image's natural size

Stop expressing the crop as a share of a box you don't control. Express it as a point in the *image*, then compute the per-container pixel offset:

```ts
/** The crop we actually want, as a fraction of the IMAGE (stable everywhere). */
const FOCUS_Y = 0.30;

function objectPositionPx(naturalW: number, naturalH: number, boxW: number, boxH: number) {
  // Replicate object-fit: cover.
  const scale = Math.max(boxW / naturalW, boxH / naturalH);
  const scaledH = naturalH * scale;
  const overflowY = Math.max(0, scaledH - boxH);
  // Where FOCUS_Y lands in the scaled image, pulled back to the box's top edge,
  // then clamped so we never reveal a transparent edge.
  const offsetY = Math.min(overflowY, Math.max(0, FOCUS_Y * scaledH - boxH / 2));
  return `50% ${-offsetY}px`;
}
```

Every container now computes its own pixel offset from one shared, container-independent intent. The slice is identical in the tile, in the ghost, and in the band, so the morph has nothing to jump.

Two practicalities:

- **You need the natural size**, which means waiting for the image to be decodable (`img.complete && img.naturalWidth > 0`, else `load`). If you compute this at mount you will get zeros and silently fall back to a centre crop — see [animation-keyed-to-creation-not-content.md](./animation-keyed-to-creation-not-content.md), which is the same trap one layer up.
- **Recompute on resize** if the container is fluid. The whole point is that the offset is a function of the box.

## How to confirm it in 30 seconds

Set `object-position: 50% 0%` on both containers, then `50% 100%`. If the two boxes show the *same* slice at both extremes, percentages are safe here (no overflow — the aspect ratios match). If they diverge, every intermediate value diverges too, and any morph between them will jump.

## The general rule

**A CSS value that resolves against the element's own box is not a shared value, even when the declaration is identical.** Percentages in `object-position`, `background-position`, `transform-origin`, `translate`, and `background-size` all share this shape: they look like a constant in the stylesheet and behave like a function of the layout. Whenever the same visual state is produced by two elements of different sizes, ask of every percentage: *does this mean the same thing in both boxes?*

## What NOT to do

- Don't fix it by forcing both containers to the same aspect ratio. It works, and it hands your layout a constraint that the design will eventually break; the next size change silently reintroduces the bug.
- Don't tune the endpoints. See above — it cannot converge, and each round makes the code look more deliberately wrong.
- Don't reach for `background-position` instead. It has exactly the same percentage semantics; you will port the bug.

## Related

- [clip-path-shared-element-morph.md](./clip-path-shared-element-morph.md) — the sibling problem: morphing between differently-*shaped* containers, solved with `clip-path` insets on a shared union box. Same domain, different axis: that one is about the box, this one is about the crop inside it.
- [animation-keyed-to-creation-not-content.md](./animation-keyed-to-creation-not-content.md) — why the natural-size read has to wait for decode.
