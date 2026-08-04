---
stack: [any, image-processing, ux]
kind: gotcha
last_verified: 2026-08-03
---

# When a classifier is wrong on many inputs, suspect the STATISTIC before the THRESHOLD

**One-liner:** a rule of the form `if measure(x) < T then treat x specially` has two places to be wrong, and the threshold is the seductive one because it is a single number you can nudge; when the rule misfires on a *large fraction* of inputs, the number is almost never the problem — the thing you are measuring is. Measured case: a "is this logo too dark to see?" check misclassified **86 of 419** inputs, and no value of `T` could have fixed it, because two independent flaws in the measure were compounding.

## The shape

You need a yes/no judgement about a piece of content: is this image too dark, is this audio too quiet, is this text too long, is this response too slow. So you reduce it to one number and compare against a constant.

That is the right architecture. The trap is what happens when it misbehaves:

1. Someone reports a wrong call on input A. You nudge `T`.
2. Input B breaks the other way. You nudge back.
3. Now A and C are wrong. You start talking about "tuning."

**Threshold-tuning cannot fix a bad statistic.** If the measure doesn't separate the two populations, no cut point does either — you're choosing which errors to make, not removing them. The diagnostic is cheap and nobody runs it:

> Dump the measure for a batch of known-good and known-bad inputs and **look at the two distributions.** If they overlap, stop touching `T`.

A good statistic looks like this (real numbers from the case below):

```
should-treat:   0, 0, 0, 0, 0, 0, 0, 0, 5, 20, 37, 40
should-not:     120, 164, 169, 204, 211, 222, 253, ...
                          ^^^^^^ enormous gap ^^^^^^
```

A bad one has the two lists interleaved. Then the threshold is a coin flip dressed as a parameter.

## The case: "is this logo too dark to draw on a dark background?"

Steam ships each game a transparent-PNG wordmark. Some are pure black and vanish against a dark banner, so those get flipped to a white silhouette. Everything else draws as authored.

First implementation, and it looks completely reasonable:

```ts
// mean Rec. 601 luma over every pixel with alpha > 16
lum += 0.299*r + 0.587*g + 0.114*b;
const isDark = lum / inkCount < 90;
```

It flagged **98 of 419** logos as dark. The true number is 12. Users hit five wrongly-bleached logos within minutes of looking.

Two independent bugs, both invisible in code review, both obvious in the data.

### Flaw 1 — luma underrates saturated colour

Rec. 601 luma weights green at `0.587` and blue at `0.114`. That is correct for *perceived brightness* and wrong for *"can you see it."*

| colour | luma | max channel |
|---|---|---|
| pure red `#FF0000` | **76** | 255 |
| pure blue `#0000FF` | **29** | 255 |
| mid grey `#4C4C4C` | 76 | 76 |

**Pure blue scores 29.** A vivid blue wordmark and a near-black one are indistinguishable to a luma threshold. The live example was a red wordmark scoring luma 68 — bleached to white, then invisible against light artwork. Its max-channel score was 120.

> **Rule of thumb:** use luma when you're asking *how bright does this look*. Use max channel (HSV **value**) when you're asking *is there anything here at all*. They diverge exactly on saturated colour, which is what logos and brand marks are made of.

### Flaw 2 — the mean is eaten by anti-aliasing and glow

Logos carry feathered edges and soft outer glows. Those pixels are semi-transparent with near-black RGB, they pass a permissive alpha cutoff, and **there are a lot of them**.

One logo measured **48% solid pixels**. Its mean read 53. The wordmark a human sees reads 204. The average was describing the halo, not the mark.

The question is never "what does this image average." It is "**is the brightest substantial part visible.**" That is a high percentile over the *solid* pixels:

```ts
// alpha >= 128 is the mark; below that is glow and anti-aliasing
if (a >= ALPHA_SOLID) hist[Math.max(r, g, b)]++;
// ...then walk the histogram to the 80th percentile
```

A 256-bucket histogram gives you any percentile in `O(n)` with fixed memory, so **the percentile costs nothing over the mean** — there is no performance argument for the worse statistic.

### Result

| | flagged as "dark" | of |
|---|---|---|
| mean of luma over all ink | 98 | 419 |
| p80 of max-channel over solid ink | **12** | 419 |

Same threshold-shaped rule. Same architecture. 86 fewer wrong answers, and the surviving separation is so wide that the exact cut point stopped mattering — anything from ~50 to ~100 gives identical results.

**That last property is the tell of a good statistic: the threshold becomes boring.** If your results swing wildly on small changes to `T`, you have not found the right measure yet.

## Generalising

The two flaws are instances of two general failure modes. Both apply well outside images.

**1. The measure is weighted for a different question than the one you're asking.** Luma answers "perceived brightness," you asked "visibility." Similar mismatches:

- **p50 latency** to answer "is this fast enough" — users experience the tail; use p95/p99.
- **Average session length** to answer "is this engaging" — one 8-hour idle session drowns fifty real ones.
- **Overall accuracy** on imbalanced classes — 99% accuracy is worthless at 1% base rate.
- **Character count** to answer "will this fit" — proportional fonts, CJK width, emoji clusters.

**2. The aggregate is dominated by a population you don't care about.** The glow pixels outnumbered the mark. Similar:

- Mean response time swamped by cached responses.
- Average file size swamped by thousands of tiny assets.
- Mean colour of a photo with a large flat background.

The fix in both cases is the same two moves: **restrict the population** (solid pixels only / uncached only / real sessions only), then **pick an order statistic instead of a mean** (p80, p95, median) so outliers and long tails stop steering.

## Checklist

When a threshold rule misfires:

1. **Count the failures.** One wrong input is a threshold problem. A large fraction is a statistic problem. This is the whole diagnostic and it takes a minute.
2. **Dump both distributions** for known-good and known-bad. Overlap means stop tuning.
3. **Ask what the measure is weighted for**, and whether that is your actual question.
4. **Ask what population it averages over**, and whether most of it is stuff you care about.
5. **Restrict, then use a percentile.** Cheap with a histogram.
6. **Re-derive the threshold from the new gap** and write the measured numbers into the code comment. A threshold with its calibration data next to it survives; a bare constant invites the next person to nudge it.

## Anti-patterns

- ❌ **Tuning the threshold twice.** If the second nudge is needed, the first was treating a symptom. Go look at the distributions.
- ❌ **Hand-maintaining an exception list.** Per-input overrides are threshold-tuning with extra steps, and the list grows forever.
- ❌ **Trusting a plausible detector without checking false positives.** A first attempt here used per-row edge-energy to spot letterboxed images; it *looked* principled and flagged two obviously-correct inputs. Always test a detector against inputs you are certain about, in *both* directions — a detector validated only on true positives is not validated.
- ❌ **Shipping a bare magic number.** Write down what you measured, on how many inputs, and where the gap was.

## Related

- [instrument-before-patching.md](./instrument-before-patching.md) — the sibling failure: when the pipeline's *decisions* are invisible rather than its *measure* being wrong. Both are "stop writing patches, go get data," applied one layer apart.
- [chase-industry-stats-to-a-primary-source.md](./chase-industry-stats-to-a-primary-source.md) — same instinct pointed at external numbers instead of your own.
