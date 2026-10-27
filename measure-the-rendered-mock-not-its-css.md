---
stack: [any, css, design-systems, branding]
kind: technique
last_verified: 2026-10-27
---

# Measure a mock's rendered layout before reproducing it: the CSS values lie under the cascade

**One-liner:** When an approved HTML mock becomes a real asset (an outlined SVG logo, a native layout, a video card), reading sizes off the mock's CSS gets you the rule you see, not the value that won. Let the browser lay the mock out and read the result: element boxes, the text baseline, glyph advances. Then diff your output against a render of the mock, pixel for pixel.

## The trap

The approved logo row in the mock had `.h { font: 600 1.08em "Exo"; letter-spacing: .04em }`, so the text "should" be 38 × 1.08 = 41.04px. The SVG outlined at 41.04px came out 7.4% wider on both words. Higher in the file, `.row .w { font-size: 38px }` (specificity 0,2,0) beat `.h`'s shorthand (0,1,0) on the same element, so the user had approved **38px** text. The ratio of the error, exactly 41.04/38, was what gave it away.

## The technique (no extra tooling beyond Chrome and Python)

1. **Rebuild just the approved element** in a scratch page with the same CSS and the same font file (`@font-face` on the real `.ttf`).
2. **Let a script write the measurements into the DOM**, then read them with headless Chrome's `--dump-dom` (no Puppeteer needed):
   - `getBoundingClientRect()` for each box: the mark, the text span, each word.
   - The **baseline**: append a zero-size `inline-block` with `vertical-align: baseline` to the text; its `top` is the baseline.
   - Wait for `document.fonts.ready` first, or you measure the fallback font.
3. **Rebuild from those numbers.** Shape each run the way the browser does (per span: no kerning across span boundaries), and apply `letter-spacing` after every glyph. Compare run widths to the measured ones; they should agree to about 0.01px.
4. **Verify by render diff:** screenshot the mock row and your output at 4x zoom on the same background, and diff with Pillow. Anti-aliasing noise stays under ~10/255; any real offset shows as a band. Also check that both renders contain ink, so two blank images don't "match".

## Case (Playmoir logo master, 2026-10-27)

`build-lockup.py` outlines "Playmoir" with uharfbuzz from the app's Exo 2 variable font (wght 600 for "Play", 400 for "moir") at the measured 38px, gap 18px and baseline 39px below a 48px mark. Run widths matched Chrome's to 0.01px, and the 4x diff against the mock's row maxed at 7/255.

Related: [[verify-the-artifact-your-user-receives]], [[derived-kit-copies-the-nearest-surface-not-the-canonical-source]].
