---
stack: [css, web, ui]
kind: pattern
last_verified: 2026-09-30
---

# Show one region of a real screenshot in pure CSS, at the region's own aspect ratio

**One-liner:** to use a slice of a real app screenshot (a recap block, one trophy icon, one row of covers) without exporting new image files, give the container the region's aspect ratio and position an oversized `<img>` inside it with four percentage formulas driven by custom properties. No JS, no natural-size wait, and it scales with the container.

*Status: used for every slice in Playmoir's landing mock (2026-09-30), which the user reviewed and liked. The math is exact; it has not yet shipped on the live site.*

## The helper

```css
/* Region (x, y, w, h) of an image sized (W, H), in the image's own pixels. */
.crop { position: relative; overflow: hidden; aspect-ratio: var(--w) / var(--h); }
.crop img {
  position: absolute; max-width: none;
  width: calc(var(--W) / var(--w) * 100%);
  left:  calc(var(--x) / var(--w) * -100%);
  top:   calc(var(--y) / var(--h) * -100%);
}
```
```html
<div class="crop" style="--W:1442;--H:1222;--x:100;--y:330;--w:900;--h:620">
  <img src="shot-recap.png" alt="…">
</div>
```

## Why the formulas work

- The container is the region, scaled: its width stands for `w` image pixels, so the whole image is `W / w` container widths wide.
- `left` as a percentage resolves against the container's **width**, which stands for `w` pixels, so `-x / w` of it shifts the image by exactly `x`.
- `top` as a percentage resolves against the container's **height**, not its width. Because the container's aspect ratio is `w / h`, its height stands for exactly `h` image pixels, so `-y / h` is exact. That is the only reason the container has to carry the region's aspect ratio. Get the aspect wrong and the vertical offset drifts.
- Custom properties stay unitless numbers, and `calc(number / number * 100%)` is valid.

## Getting the numbers

Measure the region off the real file, never by eye. For UI slices, sample pixel runs with a short PIL script: scan a column or row for where the brightness changes to find an icon's edges. Record the source image's real size as `--W`/`--H`: it's the size of the file, not how big it displays.

## When to use the other technique

`object-position-percent-is-container-relative.md` crops with `object-fit: cover` and computed pixel offsets. It suits a fixed-size box showing a focal point. This helper suits "show exactly this rectangle, at whatever width the layout gives it".
