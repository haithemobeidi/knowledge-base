---
stack: [css, design, chromium, webview2, oled, image-treatment]
kind: gotcha
last_verified: 2026-09-02
---

# A linear-gradient scrim draws as "two layers" over bright art — Mach bands at the stops, and the residue is 8-bit

**One-liner:** a 3-stop `linear-gradient` scrim reads as separate layers over bright imagery because every colour stop is a slope discontinuity the eye amplifies into a horizontal edge (Mach banding); the fix is the easing-gradient / Material-scrim technique — many stops sampled off a smooth curve, zero slope at both ends, one token for every surface — and the faint strata that remain on an OLED are 8-bit quantization from Chromium's undithered gradient rasterization, which no stop count can remove.

## Symptom

- A hero banner fades into the page through a scrim. Over dark art the fade is invisible. Over white or bright art the same scrim shows one hard-ish line where it starts and another at its middle stop; users describe it as **"two separate layers"** or a **"double gradient."**
- The screenshot geometry matches the stops exactly. Ours: a 380px banner with a 230px scrim, stops at `0% → 82% at 42% → 100%`; the veil "started" at y=150 (380 − 230) and the "second layer" sat at y≈283 (the 42% stop).
- After the fix, a **fine horizontal striping** remains — on OLED panels only, invisible on most LCDs.

## Cause

1. **Mach bands.** The visual system enhances contrast wherever the *slope* of a gradient changes. A piecewise-linear gradient has a slope kink at every colour stop, so the eye draws an edge there even though the colour itself is continuous. Bright content exposes the full contrast range of the scrim; dark content hides it because scrim ≈ content.
2. **8-bit steps.** Chromium rasterizes CSS gradients without dithering. A slow fade across a couple of hundred pixels spends several pixels per 8-bit step; an OLED resolves each step crisply, an LCD's own noise hides them.

Two rounds were spent chasing the "double gradient" in the *image* treatment (a blur wash for flat heroes) before checking the artifact's y-coordinates against the gradient stops. The wash was fine; the scrim was the layer.

## Fix

1. **Ease the gradient.** Hold the solid surface colour through the bottom N% (ours 20%), then fall along an ease-in-out sine sampled at ~20 stops, arriving at both ends with zero slope — invisible onset, seamless into the page. Preserve whatever density your text legibility was tuned on by choosing the curve, not by adding a stop (ours had to pass ~82% at the 42% mark; the sine does). References: CSS-Tricks "Easing Linear Gradients"; Material Design scrims prescribe the same long natural falloff.

   ```css
   --scrim-gradient: linear-gradient(
     to top,
     var(--surface) 0%,
     var(--surface) 20%,
     color-mix(in srgb, var(--surface) 99.4%, transparent) 24%,
     color-mix(in srgb, var(--surface) 97.6%, transparent) 28%,
     /* … one stop every 4%, sampled off the curve … */
     color-mix(in srgb, var(--surface) 0.6%, transparent) 96%,
     transparent 100%
   );
   ```

2. **Make it one token.** Nine hand-copied "verbatim" gradients across seven bands and two cards had drifted: one band's fade height wandered from 230 to 240px and nobody noticed for weeks. Define `--scrim-gradient` once; every surface — including any animated clone of the banner — references it. Tune the curve there only.

3. **The 8-bit residue, options honestly ranked:**
   - **Ship as-is** — the macro layers are gone; most users never see the strata. We sat with it for a month and closed it: "haven't noticed."
   - **Masked film grain over the scrim** — ~20 lines, one opacity knob, but grain is perceptible texture by design; the same OLED had already graded film grain "didn't fully kill" on a wallpaper.
   - **Baked dithered scrim images** — a boot-time hidden canvas renders the exact curve in float with blue-noise dither at ~half a quantization step (below texture visibility: dither, not grain), one image per fixed scrim height, swapped in for the token. Imperceptible and zero runtime cost, but bakes the surface colour (needs a regenerate hook if theming retints it) and softens slightly under fractional display scaling.
   - **Live WebGL scrim** — the dynamic version of the same math; most invasive, buys nothing over baked images while heights are design constants.

## What NOT to do

- **Don't chase a "double gradient" in the image treatment first.** Overlay the artifact's y-coordinates on the gradient stops; if they match, the scrim is the layer.
- **Don't add a fourth stop to "smooth it."** Every stop is another edge.
- **Don't keep the gradient as N verbatim copies "for locality."** Locality is how the copies drift; the token is the fix for both the banding and the drift.
- **Don't measure this on an LCD only.** The residue is an OLED phenomenon; the person who reports it is the one with the panel that shows it.

Related: `material-tier-glassmorphism-tokens.md` (the token discipline for translucent surfaces), `screen-recordings-lie-about-luminance.md` (before you measure a band from a capture).
