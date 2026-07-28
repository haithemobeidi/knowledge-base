---
stack: [process, research, product, meta]
kind: playbook
last_verified: 2026-07-28
---

# Chase the stat to a primary source before it becomes a constant

**One-liner:** the confident-sounding industry numbers you build a product decision on ("users churn after 7–14 days", "27% are reactivatable on day 1") very often trace to nothing — unattributed vendor marketing copy citing other unattributed vendor marketing copy. Chase every number to a primary source *before* it lands in a slide, a doc, or worse, a constant in your codebase. And when the chase comes up empty, say so out loud rather than quietly keeping the number.

This is a **negative result** as much as a method: for one specific, heavily-marketed question, the data does not exist in public.

## The failure shape

It runs in three stages and takes months:

1. **A number enters a doc with a vague attribution.** "Industry playbooks treat 7–14 days of inactivity as lapsed." "Per GDC talks." No link, or a link to a blog that also has no link.
2. **The doc becomes the citation.** Later work cites *your own doc* rather than the original, which no longer exists as far as anyone can check.
3. **The number becomes a constant.** Someone picks a default — a timeout, a threshold, a window — and writes a code comment justifying it: *"14 sits at the sweet spot of the win-back research (7–14 days)."* Now it is load-bearing and it looks researched.

The tell that you are in stage 3: a comment or a slide that names a *body* of research rather than a *paper*. "The win-back research", "industry convention", "studies show".

## The worked example

A product needed a default for "remind me about this game in N days". The existing constant was 14, justified in a code comment by "the sweet spot of the win-back research (7–14 days)". Chasing it:

**What evaporated.** Every circulating re-engagement-timing figure traced to unattributed vendor blog copy — "up to 27% of players can be reactivated on day 1", "first push between 3–7 days for casual games and 7–14 for deeper session-based games", "65% of users return within 30 days with push enabled" (attributed to a company, no study, no date findable). Searched the vendors who would hold real data — GameAnalytics, deltaDNA, Unity/ironSource, Amplitude, AppsFlyer, Adjust, Airship, Braze, CleverTap, Pushwoosh. **The ones with the data gate it; the ungated pages assert numbers without sourcing.**

**What survived, but meant something else.** There *is* a real 9–14 day convergence, and it is peer-reviewed: Runge et al. (IEEE CIG 2014) define churn as *"14 consecutive days of inactivity"*; Periáñez et al. use 9 days for VIPs and 13 for paying users, chosen because it *"yields less than 10% false churners."* Independent studios landing in the same band is meaningful.

But read what those actually are: **churn-*prediction* thresholds, tuned so a revenue model does not emit false positives.** They answer "when has this player stopped being worth money", not "when would this person enjoy coming back". The original claim had silently swapped one for the other.

**What pointed the opposite way.** The strongest evidence for the actual product was a number nobody had thought to look for: Newzoo's *State of PC and Console Games 2025* reports games **6+ years old are 67% of PC play time**. On PC, returning to an old game is the dominant mode of play — so a mobile live-ops churn window was the wrong reference class by an order of magnitude.

**Net result:** the number stayed roughly the same, but it stopped being a lie about where it came from, and the doc gained a correction entry. That doc had *already* logged one fabricated stat caught the same way (a "14-day gap → 80% never finish" figure attributed to Bethesda/Ubisoft GDC talks that do not exist). Same shape, second occurrence, ~4 weeks apart.

## The method

1. **Grep your own docs and code for numbers with vague attributions.** Search for "studies show", "industry", "research", "GDC", "best practice", and any bare percentage. A number with no link is a number with no source until proven otherwise.
2. **Follow every citation one hop further than feels necessary.** Vendor blog → cited blog → cited blog. If the chain terminates in another marketing page, the number is decoration.
3. **Label what you find, and keep the labels visible.** Three tiers is enough: **hard data** (measured, published, methodology stated), **design convention** (what shipped products do — real evidence of *belief*, not of effectiveness), **opinion** (asserted, unsourced). Put the tier next to the number permanently, not in a review note.
4. **Check the reference class, not just the citation.** A perfectly sound mobile free-to-play statistic can be worthless for a single-player desktop product. This is the failure that survives step 2 — the source is real, and still doesn't apply.
5. **When nothing survives, write down that nothing survived.** "No published curve exists; here is where I looked" is a durable finding that stops the next person spending an afternoon. It is also the honest input to step 6.

## When there is no data: argue from asymmetry instead

The useful move when a number is genuinely unknowable is to stop trying to find the right value and ask **which direction of error is cheaper.** That question often *does* have a rigorous answer, and it usually lives in your own system rather than in the literature.

In the worked example: the reminder's predicate auto-cancels the moment the user returns on their own. So a reminder that fires **too early costs nothing** — it silently never fires. One that fires **too late costs the entire window** and cannot be recovered. Asymmetric cost, one free direction, take it. The default moved down.

That reasoning is defensible, cheap, testable against your own code, and — importantly — it does not decay when someone finally publishes real numbers. Record the asymmetry in the constant's doc comment, not the borrowed statistic.

## Checklist

- [ ] Does this number have a link to a **primary** source (paper, platform report, company engineering post with methodology)?
- [ ] Have I followed the citation chain to its end rather than to the first plausible-looking page?
- [ ] Does the source measure **the thing I am claiming**, or a proxy for it (revenue-model churn ≠ human intent; install-cohort retention ≠ lapsed-veteran return)?
- [ ] Is the **population** mine? Mobile F2P, enterprise SaaS and single-player desktop do not share a timescale.
- [ ] Is the number about to become a **constant**? Raise the bar: comments outlive slides and get trusted more.
- [ ] If the chase failed, have I written "no evidence found, searched X/Y/Z" somewhere durable — and switched to an asymmetry argument?
- [ ] Does the doc holding these numbers have a **corrections log**? Once you have caught one, you will catch more; a log turns that into a visible pattern instead of a repeated surprise.

## Related

- [[instrument-before-patching]] — the same instinct applied to debugging: get the real measurement before acting on the plausible story.
