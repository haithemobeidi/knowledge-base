---
stack: [any, design-systems, dataviz, accessibility, css]
kind: gotcha
last_verified: 2026-08-04
---

# Don't eyeball a categorical palette — validate it, and check whether colour was doing any work at all

**One-liner:** a hand-picked set of "obviously distinct" colours routinely fails colour-blind separation, and you cannot tell by looking — running a ΔE validator takes about thirty seconds and kills bad palettes before they ship. The bigger lesson sits one level up: when the measurement fails, the right move is usually *not* a better palette, because the spacing/gaps between marks were often carrying the distinction already, and the colour was decoration you were about to spend accessibility budget defending.

## The setup

A per-month "rotation strip" in a journaling app: a 4px horizontal bar split into segments, one per game played that month, width proportional to share. The obvious design was a colour per game.

It even looked free. The app **already derived a per-game accent colour** from cover art (a Vibrant → DarkVibrant → Muted → … cascade with a WCAG 3:1 floor against the background). So each segment could wear "the colour that game *is*" — Borderlands red, Stardew green — at zero cost, and it satisfied the categorical-colour rule that **colour must follow the entity, never its rank** (sort segments by share and colour by position, and the same game changes colour month to month).

The user asked the question that broke it: *"what if it's 10 different games, how many colours can we use?"*

## What the measurement said

Running the five mock colours through a palette validator (OKLab ΔE, dark surface `#171517`):

```
[FAIL] Lightness band      4 of 5 outside band
[FAIL] CVD separation      worst adjacent pair ΔE 4.8 (protan)
[PASS] Normal-vision floor worst adjacent ΔE 17.5
[PASS] Contrast vs surface all 5 >= 3:1
```

**ΔE 4.8 under protanopia** means two of those segments are the same colour to a red-blind viewer. Nothing about the mock looked wrong.

The obvious fallback — one hue, five lightness steps — failed *worse*:

```
[FAIL] Normal-vision floor  worst adjacent ΔE 9.2 — below the floor of 15
```

Under 15 means people with **full colour vision** can't reliably tell the steps apart. Five distinguishable segments in a 4px bar is hard in *any* scheme.

## The generalisable findings

**1. Art-extracted / user-derived colours can never be validated in advance.** The existing contrast floor guaranteed each colour was readable **against the background**. It said nothing about whether two colours were distinguishable **from each other**, and it structurally can't — the palette isn't known until runtime. Two dark-fantasy covers can both extract to the same muddy brown and no floor will notice. *If your palette is derived from user content, mutual separation is not a property you can guarantee. Don't build an encoding that depends on it.*

**2. The gaps were doing the work.** The segments already had a 2px surface-coloured gap between them (a standard stacked-bar spec). Once that was noticed, the fix wrote itself: **one colour, gap-separated, width = share.** Segment count still reads as "how many," widths still read as "in what proportion," and:

- N colours for N entities becomes a non-problem — 10 items is the same problem as 2
- It cannot fail colour-blindness, because nothing needs telling apart *by colour*
- It stops fighting a design language built on a single accent

**3. Cap the segments anyway, for a different reason.** Ten hairline slivers in a 4px bar is unreadable at any palette. Top N + a dimmed "+N more" is a *legibility* limit, not a colour one — worth stating in the code comment so the next person doesn't "fix" it by reintroducing hues.

**4. Ask what the mark is actually encoding.** A legend-less strip encoding *identity* by colour needs a key, which it doesn't have. But this strip's job was **shape** — how many, in what proportion — with identity available on hover and from the rows below it. Identity was never colour's job; realising that is what made the palette optional.

## The rule worth carrying

> Before choosing categorical colours: run the validator. When it fails, don't reach for a better palette first — ask whether spacing, position, or size is already carrying the distinction. Very often colour was decoration, and deleting it is cheaper and more accessible than defending it.

And the corollary that costs nothing:

> Any colour derived from user content (cover art, avatars, uploaded images, tenant branding) can be floored for contrast against a *background*, never for separation from *each other*. Don't design an encoding that assumes otherwise.

## Cheap checks

- **ΔE ≥ 8 (OKLab ×100) between adjacent categorical colours** for colour-vision-deficiency safety; **≥ 15 for normal vision** as a hard floor.
- Validate against the **actual surface colour**, and separately for light and dark — a dark-mode palette is a selection, not an automatic inversion.
- 2px surface-coloured gaps between stacked segments. Frequently the whole fix.

## Related

- [n-copies-of-truth-drift-guard.md](./n-copies-of-truth-drift-guard.md) — same instinct in a different domain: compute the check, don't rely on discipline.
