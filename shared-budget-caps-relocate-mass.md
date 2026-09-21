---
stack: [any, llm-agents, context-engineering, docs, observability]
kind: gotcha
last_verified: 2026-09-21
---

# Capping one contributor to a shared budget just moves the mass — measure the total the consumer receives

**One-liner:** when several independently-maintained things feed one fixed budget — context window, bundle, page weight, query plan, a startup payload — a cap on the worst contributor does not reduce the total. It relocates it to whichever neighbour has no cap, and the move is invisible precisely *because* the metric everyone was watching improved.

## The shape

You have a consumer with a finite budget, fed by N producers that grow independently. One producer bloats. You cap it. The metric recovers. Everyone moves on.

What actually happened: the *demand* that filled that producer did not go away. It had a reason to exist — someone needed that information near the consumer — and it re-lands in the producer with the loosest rules. Usually the one with no cap at all, because nobody has thought about it yet, because it has never been a problem.

Then the failure is slower and quieter than the first one, because the first one had a champion and a number. The second has neither.

## The measured case (Claude Code session protocol, 2026-09)

A session-start hook injected four project documents into every agent session. 2026-09-08: the ledger had reached 99 open items averaging 2,500 characters, ~250KB per session start. Hard caps were added — 600 chars per item, truncation at injection, a soft cap on the open count. They worked. The ledger went from 397KB to 259KB and stayed down.

Twelve days later:

```
date          CURRENT_STATE.md     SESSION_LEDGER.md
2026-09-08           5,968              317,160      <- caps land
2026-09-12          23,202              287,838
2026-09-20          92,900              258,951
```

The capped file kept shrinking. The uncapped neighbour went **15.6x in twelve days**, and the total injection reached 163,478 characters — about 41,000 tokens, roughly five times a normal full startup payload for that tool. 63% of the bloat was a single section that had quietly become a 30-session narrative log duplicating another file's job.

Three structural reasons nobody caught it, all worth stealing as checks:

1. **The audit measured the diagnosed producer, not the payload.** It counted the ledger, because the ledger was the suspect. Nobody summed what the consumer received. A per-producer cap can only ever tell you about that producer.
2. **The fix created the surface.** That same change introduced new document sections (per-track state blocks). They were empty on the day they shipped, so they looked fine. **A structural change is the moment to schedule the next measurement**, precisely because new structure is empty when you ship it.
3. **The template could not exhibit the bug.** The canonical copy of the system had placeholder documents of 48 lines. Any growth check validated there passes forever. See `negative-control-before-trusting-a-probe.md`.

## The fix: one budget on the assembled artifact

Not "more caps." **One cap, on what the consumer actually gets**, with the per-producer caps demoted to hints:

- **Measure the assembled thing, not a reconstruction of it.** Have the producer emit its real output in a measure mode and read that back. Re-deriving sizes from the inputs measures a different artifact than the one that ships — see `verify-the-artifact-your-user-receives.md`.
- **Print the number every time**, not on request. The failure mode is nobody looking; a number that appears unbidden at every start cannot be discovered twelve days late.
- **Name the largest contributor in the output.** "Over budget" is a fact; "over budget, 56% of it is X" is an action.
- **Say "shrink the contributor, never raise the budget" in the tool itself.** Raising it is the path of least resistance and it is how the previous cap failed.

## Capping the VIEW is not capping the file

The subtle half. The original cap truncated items *at injection* — the file kept growing, the payload looked disciplined. On the live system, items averaged 1,150 characters against a 600-character cap, and the cap had never once been enforced on disk. It was hiding the overage rather than preventing it.

That is not automatically wrong. It becomes the right answer once you accept the corollary: **a file that is never read whole has no size problem.** Which points at the real fix.

## What replaces the per-item cap: catalog plus fetch-on-demand

Instead of shrinking each item so the whole set fits, inject a **complete one-line catalog** and fetch full text only for the few items actually in play.

Measured on the same system: 88 open items rendered as full text (truncated) cost 60,494 characters; the same 88 as one-line titles cost 9,782 — **a 6x cut with nothing hidden**, because every item is still listed. Items then need no cap at all and can stay whole, which also removes the only place a size rule could lose someone's words.

Three rules that make it work:

- **The first line must stand alone as a title.** The catalog is built from it and a reader decides whether to open the item from that line alone. This is the one authoring discipline the pattern requires, and it is the whole thing.
- **Rank for depth, never for presence.** Aider's repo map fits a token budget by dropping the lowest-ranked entries, which is right for code structure and wrong for a to-do list: a dropped item is an *absence*, and absences produce no signal (`write-triggered-enforcement-blind-to-deletion.md`). Keep every item in the catalog; let ranking decide only which ones also get full text.
- **One level of routing, not two.** A controlled study of progressive disclosure (arXiv:2607.17598, 2026-07) found one routing level beats reading raw documents once a corpus is too big to browse, but a second, deeper level *"never helps and sometimes breaks accuracy outright."* So: catalog line → whole item. Not catalog → capped item → side file, which is what the original design had built.

Prior art worth knowing: Claude Code's own memory system is this pattern with numbers on it — an index capped at 200 lines or 25KB, topic files loaded only on demand; its Skills catalog caps each entry at 1,536 characters with bodies loaded on trigger. Cline's "Memory Bank," which reads six files *in full every task* with no size or staleness rule anywhere, is the control group: users report ~300,000 tokens after about five iterations.

## Where else this shape shows up

Any fixed budget with independent producers: bundle size (cap one entry point, weight moves to a lazy chunk that nobody is watching); page weight (compress the images, the JS grows); a query plan's cost (index one join, the optimizer moves the cost to another); a log budget (silence one noisy component, another fills the quota); an SLO error budget across services. The tell is always the same — **the number you were watching improved and the user's experience did not.**

## What to do about it, concretely

1. Find the consumer's real budget and measure the **assembled** artifact against it.
2. Emit that number automatically, every time, with the largest contributor named.
3. Make the tool say to shrink the contributor rather than raise the budget.
4. When you cap a producer, ask *where the demand will go* — that neighbour is the next incident, and it looks healthy today because it is empty today.

Related: `verify-the-artifact-your-user-receives.md` (measure what ships, not your copy), `instrument-before-patching.md` (the surface logs its own decisions before fix N+1), `n-copies-of-truth-drift-guard.md` (docs don't run; scripts do), `suspect-the-statistic-before-the-threshold.md` (when a rule misfires broadly, the measure is the bug).
