---
stack: [css, mobile-web, web]
kind: gotcha
last_verified: 2026-10-02
---

# One element sticking out sideways makes a phone zoom the whole page out; `overflow-x: clip`, not `hidden`, fixes it without breaking `sticky`

**One-liner:** a mobile browser fits the page's *widest* content into the viewport, so one wide element zooms everything out. `overflow-x: hidden` on both `html` and `body` stops that but turns `body` into a scroll container, which unsticks every `position: sticky` section. `overflow-x: clip` on both clips without creating a scroll container.

*Playmoir's website, 2026-10-02 (`apps/landing/src/styles/base.css`).*

```css
/* fallback where clip is unknown: hidden on body alone */
body { overflow-x: hidden; }
@supports (overflow: clip) {
  html, body { overflow-x: clip; }
}
```

Still find the element that sticks out (it is usually a decoration with a negative margin or a 100vw width plus a scrollbar); clipping hides the symptom on purpose, so the page can't be widened by the next one either.
