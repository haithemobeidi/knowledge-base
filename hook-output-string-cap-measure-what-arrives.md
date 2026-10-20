---
stack: [any, claude-code, llm-agents, context-engineering, observability]
kind: gotcha
last_verified: 2026-10-20
---

# A budget is only as real as the channel it travels through — Claude Code caps one hook string at 10,000 characters

**One-liner:** Claude Code caps every string a hook returns (`additionalContext`, `systemMessage`, `initialUserMessage`, plain stdout) at 10,000 characters, measured per string, and replaces anything longer with a 2,000-character preview plus the path of a file it does **not** ask the model to read. A session-start payload budgeted at 25,000 characters therefore arrived as its first 2,000 for a month, every session, and nothing in the protocol could see it because the protocol measured what was sent and never what arrived.

## The shape

You design a budget for something a consumer receives. You pick the number from a ceiling you know about (here: the 25KB Claude Code puts on its own auto-loaded `MEMORY.md`). You measure your producer against that number faithfully. But the artifact does not reach the consumer directly — it goes through a channel with its own, lower, cap, and the channel degrades silently: it does not fail, it delivers a *plausible* truncation that looks like the whole thing to a reader with no memory of what the whole thing should be.

The telltale: the receiver behaves as if the first screen of content is all there is. Directives placed at the end of the payload for recency are the first casualty.

## The measured case (Claude Code session protocol, 2026-09-20 → 2026-10-19)

A `SessionStart` hook assembled state docs, a ledger manifest, a spine, handoff entries and a cross-check directive into one `additionalContext` string. The budget was 25,000 characters; the live project's payload was 160,000 before its v2 migration and 47,813 after. Evidence on disk in the session directories (`tool-results/hook-*-additionalContext.txt`):

```
overflow files written by the harness:   38 session starts, 2026-09-20 → 2026-10-02
size before migration:                   160K – 179K
size after migration:                    38K – 49K
smallest overflow file anywhere:         11,186 chars   (none under 10,000 — the cap is real)
sessions that read the file back whole:  7 of 38
```

The docs (code.claude.com, hooks reference) state it plainly: strings "are capped at 10,000 characters"; "Claude Code measures each string on its own, even when several hooks run for the same event"; over the limit it "saves the output to a file in the session directory and replaces it with the file path and a preview of up to the first 2,000 characters"; "Claude Code doesn't ask Claude to read the file." No setting raises the cap.

What the 2,000-character preview contained: the sync line and the top of CURRENT_STATE. What it did not: the track-gate directive, the manifest, the spine, the handoff entry — everything the budget had been designed to protect. A budget checker ran at every `/end` and reported 172–191% of budget, which everyone read as "shrink the docs", not "nothing is arriving".

## The fix pattern

1. **Split delivery, keep the budget.** The cap is per string, so wire the same hook N times (`--part 1 … --part N`); each invocation emits one slice under the cap. The budget (25,000) stays the enforced number; the deliverable ceiling (N × slice) is a safety net, not a licence.
2. **One decision, many emitters.** Parallel invocations must not each fetch and each decide. Invocation 1 builds everything, writes the slices to a per-session cache keyed by the hook's `session_id`, and emits slice 1; the others wait for a cache newer than their own start (a `resume` re-fires the hook with the same id, so an old cache must not count) and emit their slice or nothing. A "refuse, you are behind origin" verdict is then one part and silence from the rest, never a refusal in one part and stale documents in six others.
3. **Label every part** ("part n of m") because the harness gives no ordering guarantee, and put the directive in part 1 — the only part guaranteed to exist.
4. **Make overflow loud.** Parts beyond the wired entries cannot be delivered; the last deliverable part must say which sections were dropped. An absence produces no signal.
5. **Measure delivery, not just size.** The budget checker now reports parts, entries wired, and fails on "undeliverable" separately from "over budget". The same check also flags the legacy wiring (hook wired once, payload over 10,000) — the exact state that went unnoticed for a month.

## The general lesson

Measure what arrives, not only what is sent. Every hop between producer and consumer — a hook output cap, a message size limit, a log line truncation, a UI that shows the first N characters, an email client that clips — can substitute a plausible fragment for the whole, and the fragment is most convincing to the reader who has never seen the whole. When you set a budget, find the lowest cap on the path and verify the first real delivery end to end (here: `grep` the session directory for overflow files; seven of them with a same-size sibling meant the file *was* sometimes read back, which is why the failure was intermittent rather than total).

Related: [shared-budget-caps-relocate-mass.md](./shared-budget-caps-relocate-mass.md) (the budget this cap sat above, and why the total is the only honest number), [handoff-for-a-reader-with-no-memory.md](./handoff-for-a-reader-with-no-memory.md) (why a truncated handoff reads as complete).
