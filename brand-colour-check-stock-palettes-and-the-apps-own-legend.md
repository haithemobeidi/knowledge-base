---
stack: [design, branding, css, tailwind, process]
kind: gotcha
last_verified: 2026-11-18
---

# Before offering a brand colour, check it against the stock palettes and against the app's own colour legend

**One-liner:** a brand colour picked by eye in a Tailwind-era project is often a stock palette value, and the "alternatives" offered to replace it tend to be its stock neighbours. Look each candidate up in the common toolkits' palettes before showing it, and read the product's existing colour meanings before naming a favourite or a fallback. Both checks take minutes and both were skipped here, in front of the user.

*Playmoir, 2026-11-18: the brand violet moved to amber after three wrong turns.*

## What happened

The founder asked whether the brand purple was "the AI purple people seem to notice". It was: `#A78BFA` is exactly Tailwind's `violet-400`, a default accent on a great many new, AI-assisted sites (no count was measured; the exact match to the stock value is the fact). Three mistakes followed, each avoidable with a lookup:

1. **The first alternative offered was the same problem.** "Periwinkle" `#98A3FF` was mocked as an escape from the AI look. It sits between Tailwind's `indigo-300` (`#A5B4FC`) and `indigo-400` (`#818CF8`), and violet-to-indigo is the other half of the same cliche. The founder picked it; only then was the caveat raised.
2. **An argument for the winner rested on a misread screenshot.** Amber was recommended partly because it "sits with the app's red Play button". The red was that game's accent colour in the recording, not a fixed part of the design. The founder caught it.
3. **The fallback offered was already taken.** "Ember" (amber pushed toward orange) was offered in case amber clashed with gold text in the app. The app's stylesheet already had an orange for boss names in notes. One grep (`ai-accents.css`: places gold, bosses orange, people blue, items violet) showed that, and also showed the app's own note colour and trophy colour were ambers, which was a better argument for amber than the one that had been made.

## The checks

**1. Is the candidate a stock value, or a near neighbour of one?** Compare against the palettes the project's toolkit ships (Tailwind's ramps, Material, Radix, Open Color). A value within a few units of a stock step will read as that stock colour. If the goal is "does not look like every other new site", stay off the default ramps of the hue that is overused, not just off the exact hex.

**2. What does each colour already mean in the product?** Grep the styles for every hex before proposing one:

```bash
grep -rniE "#[0-9a-f]{6}" src --include=*.css | sort | uniq -c | sort -rn | head -40
```

Colours that carry meaning (a legend, states, categories) are not free. A brand colour that lands on one of them either borrows its meaning or breaks the legend, and so does a fallback.

**3. Is the evidence a design token or one screenshot?** A colour seen in a recording may be per-user, per-item or themed. Confirm in the code before building an argument on it.

**4. Who else owns that colour on the same ground?** Name the nearest well-known mark (amber play-shape on black is Plex) so the owner compares the two before deciding, instead of after shipping.

## How to present the options

Mock the candidates on the real pieces side by side (logo, icon at small sizes, a badge, an end card, the logo over a real app screen), and state for each one: its nearest stock neighbour, what it already means in the app, and the nearest brand that uses it. The user picked from the board in one look once those were on it; the earlier round with a bare colour toggle produced a pick that had to be walked back.

See also [categorical-palette-validate-dont-eyeball.md](./categorical-palette-validate-dont-eyeball.md) for the measured version of "don't trust your eye" when colours must be told apart.
