---
stack: [compose, android, skia, animation, image-treatment, shared-element]
kind: gotcha
last_verified: 2026-09-21
---

# A darkening layer clipped at the same edge as the art cannot hide it — "half over half" leaves a quarter of the art in the edge row

**One-liner:** wherever a box's edge lands on a fractional pixel row (a flying shared-element frame) or on an anti-aliased curve (a rounded clip), every layer inside the box is drawn at the same partial coverage; a dark scrim or seal at half coverage over art at half coverage leaves art × ½ × ½ showing, which on white art is a visible light hairline or corner outline that only exists while the edge is fractional. Fix by keeping the art off the edge (inset it under an opaque strip) or by compositing the box offscreen so the clip is applied once to the finished pixels; detect it with a step scan, not a peak scan.

## Symptom

- A one-pixel **lighter line at the foot of a banner while it flies** (a shared-element frame growing/travelling), gone the moment it settles. Strongest on flat white heroes, faint on mid-tone art, absent on dark art. **Intermittent between identical runs**: only the runs whose last frames land the edge between pixel rows show it.
- A **light outline that draws only along the rounded corners** of a card over a near-black page, never along its straight edges; the cards with dark art are clean, the cards with white art are outlined. Flickers as the cards fade in.
- A "seal" (an opaque strip of page colour at the very bottom of the box) that was added to fix the first symptom *darkens* the line but never removes it, and passes a verification run by luck (the run landed on integer rows).

## Cause

Compositing arithmetic at a partial-coverage edge. With coverage `c` on the edge row, page `P`, art `A`, dark layer `D` (alpha 1) drawn *inside the same clipped box*:

```
row = P·(1−c)² + A·c·(1−c) + D·c
```

The `A·c·(1−c)` term is the art showing through: at `c = 0.5` a quarter of the art. For white art on a near-black page that is a row at ~70 over a page of ~11; for dark art (`A ≈ P`) it vanishes, which is why the symptom tracks the hero's brightness. Anything drawn *inside* the box at the same edge — a scrim, a seal, a second overlay — is itself at coverage `c` and can only scale the term, never zero it.

Two places produce a fractional edge:
1. **A shared-element frame in flight** (Compose `sharedBounds`, any FLIP): the animated bounds are floats; the content is laid out at integer size and drawn at a fractional offset, so the top and bottom rows are partial on most frames.
2. **A rounded clip** (`Modifier.clip(RoundedCornerShape)`): Android's outline clip is applied per draw op with anti-aliasing, not to the composite, so the art and the wash over it each get their own partial pixel along the curve.

## Fix

- **Flight edge:** keep the art short of the edge. Inset the art by 2dp (`Modifier.fillMaxSize().padding(bottom = 2.dp)`) and let an opaque page-colour strip own those 2dp on top of the scrim. The edge row then holds only dark over dark, invisible at any coverage. The crop stays width-driven at banner shapes, so the scale does not change; the picture rises by a fraction of a point.
- **Rounded clip:** clip the *composite* once — `graphicsLayer { shape = RoundedCornerShape(r); clip = true; compositingStrategy = CompositingStrategy.Offscreen }`. One offscreen buffer per card; fine for a screen of 44dp strips, measure before doing it to hundreds of large items. Alternative with no buffer: don't clip, draw a page-coloured mask path (rect minus rounded rect) over the content as one primitive.
- **Don't** add a darker seal, a taller seal, or a heavier scrim at the edge: all of them live inside the clip and inherit `c`.

## How to see it on tape

Screen-record the motion, extract every frame (`ffmpeg -fps_mode passthrough`), then scan rows for a **step** — a row brighter than the page below it by a margin while darker than the art above — not a **peak** (brighter than both neighbours). A peak scan misses this line entirely, which is how a verified fix came back three sessions later. Check the row spans the full width (encoder banding does not) and compare a dark-art control take.

## Related

- `gradient-scrim-mach-bands-and-8bit-residue.md` — the other way a scrim shows an edge on bright art (stops, not coverage).
- `screen-recordings-lie-about-luminance.md` — why absolute values from a recording are only comparative.
- `clip-path-shared-element-morph.md` — the desktop's morph, which clips a fixed canvas instead of laying the art out to the frame.
