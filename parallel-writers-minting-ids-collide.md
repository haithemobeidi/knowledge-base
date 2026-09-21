---
stack: [process, multi-agent, docs, git]
kind: gotcha
last_verified: 2026-09-21
---

# Parallel writers minting "the next ID" from a shared ledger collide — and downstream references freeze the collisions in

**One-liner:** two concurrent agents (or humans) appending to one shared append-only ledger each read the tail and allocate "the next number" — a textbook unsynchronized counter, except the cost isn't the collision itself: it's that commit subjects, wrap documents, and chat transcripts immediately reference the colliding IDs and are immutable, so even a prompt renumber leaves permanently wrong pointers behind.

## The symptom

Two Claude Code sessions ran the same project concurrently (one per platform track),
both appending items to the shared markdown ledger that assigns sequential IDs
(L-343, L-344, …). **Three collisions in one night:** each session read the ledger's
tail at a different moment, minted the same "next" number for different items, and
kept working. One item ended up renumbered **twice** — its first replacement number
collided with a number the *other* session had minted in the meantime, invisible to
the renumberer.

## The mechanism

Read-increment-append with no lock and no re-read at write time. Every fix a database
would apply (atomic sequence, CAS, unique constraint) is absent from a markdown file,
and git doesn't save you: both sessions worked the same checkout, so there wasn't even
a merge conflict to force awareness — appends interleave cleanly.

The compounding trap is **reference freezing**: by the time a collision is noticed,
the stale IDs are already in immutable places — commit subjects, the other session's
wrap summary, the user's own messages. Renumbering fixes the ledger and leaves every
frozen pointer wrong, so the renumber note has to travel in the ledger line itself
("the 87th's wrap calls this L-343; THIS line is the item") forever.

## The fixes, in preference order

1. **Namespace per writer** — track-prefixed IDs (`A-12`, `D-31`) make collisions
   structurally impossible and cost nothing. The right default the moment a second
   concurrent writer becomes a pattern.
2. **Single mint authority** — one session owns allocation; others request or use a
   reserved block. Correct but adds coordination latency between agents.
3. **Mint at commit, re-read first** — allocate the number in the same action that
   appends the line, after re-reading the tail (CAS-flavored). Narrows the window;
   doesn't close it.
4. **What doesn't work:** "be careful" — the sessions had no visibility into each
   other's unwritten intentions, and being careful cannot read another writer's
   working memory.

If a collision does land: renumber the *later-referenced* item, and put the alias
history in the surviving line itself, because that line is the only mutable place the
frozen references can be redirected from.

## The general rule

Sequential IDs are a concurrency primitive wearing a documentation costume. The
moment a ledger has two concurrent writers, treat allocation like the distributed-
systems problem it is — namespace it, own it, or CAS it — and assume any ID that
escaped into an immutable reference can never be reclaimed, only aliased.

## The prune variant: deleting a closed line dangles every citation to it

Same thesis — a mutable ledger with immutable references to it — different trigger. Not collision and renumbering, but **housekeeping**.

A ledger accumulates closed items, so someone writes a sensible-looking rule: prune `[x]` lines older than N days, history lives in git. It is wrong for exactly the reason above. By the time an item closes, its ID has escaped into commit subjects, handoff entries, roadmap cells and the user's own messages — and those are all append-only. Deleting the line does not tidy anything; it converts every one of those citations into a pointer at nothing.

Measured on one project after the prune rule had been running: **51 of 72 IDs cited in the roadmap's status table no longer resolved to any ledger line.** They were not wrong, they were unreachable. And "history lives in git" is technically true and practically useless — nobody runs `git log -p` on a docs file to decode a reference they hit mid-session. Text you cannot grep is functionally text you do not have.

**Fix: move, never delete.** Struck lines get appended to a closed-items file that is never loaded into context and may therefore grow forever. Same working-file size, every citation still resolves, nothing lost. The cost of keeping it is zero the moment nothing reads it whole — see [shared-budget-caps-relocate-mass.md](./shared-budget-caps-relocate-mass.md).

Two details worth copying: make the move a **script** and not a documented step (the prune rule that produced those 51 dangling IDs was prose in a wrap checklist, and separately, 88 closed lines were still sitting in that ledger *unpruned* under a 7-day rule — the rule failed in both directions at once); and have any checker that classifies citations use **three** classes — open, closed, and *not found* — because after a move-or-prune the third class is mostly legitimate history and treating it as a finding buries the real ones.

## Related

- [write-triggered-enforcement-blind-to-deletion.md](./write-triggered-enforcement-blind-to-deletion.md) — "enforce invariants, not events" is the same shape: the invariant here (IDs are unique) needs enforcement at mint time, not discovery at read time.
- [n-copies-of-truth-drift-guard.md](./n-copies-of-truth-drift-guard.md) — the sibling failure for *content* rather than *allocation*: N copies of one truth drifting apart.
- [handoff-for-a-reader-with-no-memory.md](./handoff-for-a-reader-with-no-memory.md) — where those immutable citations live, and the copy-forward evidence for why nobody re-verifies them.
