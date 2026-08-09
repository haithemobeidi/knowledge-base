---
stack: [any, android, web, ios, fonts, assets, performance]
kind: howto
last_verified: 2026-08-09
---

# "Bundling webfonts costs megabytes" is folklore — measure it, then subset it

**One-liner:** an app shipped with system fonts instead of its own brand typefaces, justified by a code comment reading *"bundling three webfont families would add megabytes."* Nobody had measured. The real number was **1.62 MB for four families**, and the bulk was not the Latin glyphs anyone wanted — **every static Rajdhani weight carries a full Devanagari set at ~390 KB**, and the design needed two of those weights. Subsetting to the character ranges the UI can actually emit took all six files to **516 KB**, with no visible difference. Typography is the single largest carrier of brand identity; half a megabyte is a cheap price, and the folklore had quietly sold it as an expensive one.

## The failure shape

It is a three-line story and it is very common:

1. Someone asks "should we bundle the brand fonts?"
2. Someone answers "that would add megabytes" — plausibly, from experience, without opening a file browser.
3. **The estimate becomes a code comment**, which reads as a decision that was investigated. Everyone downstream inherits it.

The tell is a justification that names a *magnitude* rather than a *measurement*: "megabytes", "too big", "bloats the bundle". A real measurement has a number and a date.

## Two things to measure, not one

The obvious question is "how big is the family?" The more useful one is **"what is big INSIDE it?"** Those have different answers and only the second one tells you what to do.

Google Fonts ships most families with full language coverage. For a Latin-only UI that means you are shipping:

- **Devanagari, Cyrillic, Greek, Vietnamese** — entire scripts, frequently the majority of the file.
- **Every OpenType layout feature**, including ones nothing enables.
- On static families, **all of that once per weight.**

Measured here: Rajdhani has no variable release, so two weights meant two full Devanagari sets — ~780 KB of glyphs for a UI that renders English. That is not "fonts are big." That is "you are shipping a script you don't use, twice."

## The fix, in one command

`pyftsubset` (from `fonttools`) cuts a font to the codepoints you declare:

```bash
python -m venv .fontvenv && .fontvenv/Scripts/python -m pip install fonttools brotli

# Basic Latin, Latin-1, Latin Extended-A, plus the punctuation a UI actually emits:
# en/em dashes, curly quotes, bullet, ellipsis, arrows, minus, euro, trademark.
RANGES="U+0020-007E,U+00A0-00FF,U+0100-017F,U+2010-2015,U+2018-201F,U+2022,U+2026,U+2039-203A,U+2190-2193,U+2212,U+20AC,U+2122"

python -m fontTools.subset in.ttf \
  --unicodes="$RANGES" \
  --layout-features='*' \
  --name-IDs='*' \
  --output-file=out.ttf
```

Two flags matter more than they look:

- **`--layout-features='*'`** keeps kerning and ligatures. The default drops features, and a subset that kerns worse than the original is a downgrade you will notice on headings before you work out why.
- **`--name-IDs='*'`** keeps the name table, including the licence and designer records. For OFL fonts that is not cosmetic — see below.

Measured result, four families / six files: **1.62 MB → 516 KB**, no visible difference.

## Where the ranges come from

Do not guess the ranges from a chart. Derive them:

- **Basic Latin + Latin-1 + Latin Extended-A** covers Western European text and is the safe floor.
- **Then add the punctuation your own UI emits.** Grep your string resources for typographic characters — em dashes, curly quotes, ellipses, arrows, ™, €. These are the ones that produce a single missing glyph in a shipped screen, which looks far worse than a plainer font would have.

**What happens outside the range is the part that makes this safe:** an unmapped codepoint falls through to the system font. A CJK game title still renders. It renders in the platform font rather than your brand font — which is what would have happened anyway, because no bundled Latin family covered it.

## Variable vs static — the distinction that changes the arithmetic

- **Variable font:** one file serves every weight along an axis. Subset once, done.
- **Static family:** one file per weight, and every one of them carries the full language coverage. This is where multi-megabyte numbers actually come from.

If a family has a variable release, take it. If it does not, the per-weight cost is real and you should ship only the weights the design uses — adding a Medium "for completeness" is another whole file.

**The trap on the variable side:** the renderer needs the axis pinned per weight, or it loads the file at its default weight and *synthesises* the rest. You get a "bold" that is a smeared regular. In Compose that means one `Font(...)` per weight with `variationSettings = FontVariation.Settings(FontVariation.weight(w))`; on the web it is `font-variation-settings` / a correctly declared `@font-face` weight range. Whatever the platform, verify a real bold is being loaded rather than faked — the two look similar in a screenshot and different at a glance in person.

## Licensing rides along

Almost every Google font is **SIL Open Font License 1.1**. Subsetting is explicitly permitted (it is a Modified Version), but two obligations survive into your binary:

- **Ship the licence text** and keep the copyright notice — this is why `--name-IDs='*'` matters, and why a `FONTS_LICENSE.txt` belongs next to the fonts.
- **Surface it in-app** if you distribute through a store. A licence file in your repo is not a licence delivered to the user. A "Licences" row in Settings opening a scrollable text screen is the standard pattern and takes an hour.

Also: OFL forbids selling the fonts on their own and forbids using the Reserved Font Name. Subsetting and embedding in a commercial app is fine; renaming the file is fine; calling your subset "Rajdhani" while modifying it is the part to read carefully.

## Make it reproducible, commit the output

Put the fetch-and-subset in a script that pins the upstream source and the ranges, and **commit the resulting files**. Then:

- A normal build never touches the network.
- Regenerating for an upstream revision or a wider range is one command.
- The ranges are reviewable in a diff instead of living in someone's shell history.

Print the before/after bytes per file as the script runs. That single line of output is what turns the next "wouldn't that be huge?" conversation into a fact.

## Checklist

- [ ] Has anyone actually **measured** the raw files, or is the number folklore?
- [ ] Do you know **what** is big inside them — a script you don't render, or the glyphs you do?
- [ ] Variable release available? Take it over statics.
- [ ] Subsetting with `--layout-features='*'` so kerning survives?
- [ ] Do the ranges include the **punctuation your own strings contain**, not just A–Z?
- [ ] Is each weight really being loaded, or is the renderer faking it from one file?
- [ ] Licence text shipped **and reachable in the UI** if this goes to a store?
- [ ] Subsetting scripted, ranges pinned, output committed?

## Related

- [[monorepo-stale-dist-zod-strip]] — the other kind of committed-artifact staleness: output checked in and silently older than its source.
- [[chase-industry-stats-to-a-primary-source]] — same disease one domain over: a confident number that nobody traced before it became load-bearing.
