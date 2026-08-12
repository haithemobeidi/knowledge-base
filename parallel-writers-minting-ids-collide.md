---
stack: [process, multi-agent, docs, git]
kind: gotcha
last_verified: 2026-08-12
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

## Related

- [write-triggered-enforcement-blind-to-deletion.md](./write-triggered-enforcement-blind-to-deletion.md) — "enforce invariants, not events" is the same shape: the invariant here (IDs are unique) needs enforcement at mint time, not discovery at read time.
- [n-copies-of-truth-drift-guard.md](./n-copies-of-truth-drift-guard.md) — the sibling failure for *content* rather than *allocation*: N copies of one truth drifting apart.
