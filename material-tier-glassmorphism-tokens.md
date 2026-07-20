---
stack: [css, design-system]
kind: pattern
last_verified: 2026-07-08
---

# A 3-tier translucent-surface (glassmorphism) token system, organized by ROLE

**One-liner:** instead of letting every frosted/translucent panel in an app invent its own blur+opacity values, define a small tiered taxonomy keyed to **interaction role** (ambient chrome vs. persistent status vs. focused/modal), not just "how much blur." The non-obvious payoff: the top tier needs a **luminosity bump**, not just more blur and opacity, or it reads as a flat dark box instead of glass.

## The taxonomy

Three tiers + a scrim, each mapped to a role rather than a vibe:

| Tier | Role | Examples |
|---|---|---|
| **Thin** | Ambient, passthrough browsing chrome — present but not the focus | Sidebar, search/filter bar, a floating back-button pill |
| **Regular** | Persistent, in-flow status — always visible while relevant, not blocking interaction | Toast notifications, a docked action bar, an in-page stats panel |
| **Thick** | Focused / blocking — the user's full attention is on this surface | Modal dialogs, lightbox, an in-app overlay over dimmed content |

```css
--material-thin-bg:        rgba(16, 14, 18, 0.45);
--material-thin-blur:      blur(14px) saturate(1.05);
--material-thin-border:    rgba(255, 255, 255, 0.05);

--material-regular-bg:     rgba(22, 20, 26, 0.78);
--material-regular-blur:   blur(22px) saturate(1.1);
--material-regular-border: rgba(255, 255, 255, 0.06);

--material-thick-bg:       rgba(34, 30, 38, 0.82);
--material-thick-blur:     blur(32px) saturate(1.15);
--material-thick-border:   rgba(255, 255, 255, 0.06);

--scrim-bg:                rgba(8, 6, 10, 0.72);
--scrim-blur:               blur(6px) saturate(0.9);
```

Blur and opacity increase together tier-to-tier (14px/0.45 → 22px/0.78 → 32px/0.82) — that part matches every glassmorphism tutorial. The part that doesn't is the background RGB itself: `rgba(16,14,18,...)` → `rgba(22,20,26,...)` → `rgba(34,30,38,...)`. Each channel climbs, not just the alpha.

## Why: "my dialog doesn't look like glass, it looks like a dark box"

When a modal/thick-tier panel sits **over a scrim** (a dimming overlay on the background content), naively scaling up blur+opacity from the lower tiers makes intuitive sense — "more modal = more blur, more opacity" — but it produces a panel that reads as *another dark rectangle stacked on the dimmed backdrop*, not a floating lighter layer of glass above it. The panel and the scrim behind it converge toward the same darkness, so the eye can't separate "the surface" from "the dimmed background it's floating over."

The fix is a **luminosity bump independent of blur/opacity**: the thick tier's background RGB is measurably lighter (34,30,38) than the thin tier's (16,14,18), tuned specifically against whatever the scrim's own darkness value is. This makes the panel read as *sitting above and lit relative to* the dimmed backdrop, rather than blending into it. Treat "does this read as glass" as a **three-variable** tuning problem — blur radius, alpha, and background luminosity — not a single opacity slider that gets cranked up for "more important" surfaces.

## How to apply in a new project

1. **Name tiers by role first**, pick values second. Ask "is this ambient chrome, persistent status, or a focused/blocking surface?" before touching blur radius numbers — the role tells you which tier's values to reach for, and prevents every new component from inventing a bespoke translucency.
2. **When you add a "bigger/more important" tier**, don't just scale blur+opacity — check whether it sits over a scrim, and if so, independently tune the background's lightness against the scrim's own darkness so it separates visually instead of merging into it.
3. **Publish the tiers as CSS custom properties** (or your framework's design-token equivalent) so every surface consumes `var(--material-thin-bg)` etc. instead of a hand-typed `rgba(...)` — this is what makes "we changed how thick surfaces look" a one-line edit instead of a grep-and-replace.
4. Keep the tier count small (3 + scrim was enough for a real app with sidebars, toasts, modals, lightboxes, and an in-game overlay). Resist adding a 4th tier unless a genuinely distinct role emerges — more tiers just re-introduce the "which one do I use" ambiguity the taxonomy was meant to remove.
