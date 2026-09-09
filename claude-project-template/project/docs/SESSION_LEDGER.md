# Session Ledger — open items that must not get lost

> **What this is:** the append-and-strike ledger for session-scoped open items —
> queued tests, pre-release gates, riders, deferred decisions, watch items.
> Anything phrased like "next session," "before release," "rider," "queued,"
> or "check later" gets a line HERE at the moment it's said.
>
> **Rules** (full rationale in the global `PROTOCOL.md` → "The ledger at the moment of the event"):
>
> - **Append at the moment of queueing; strike at the moment of resolution.**
>   Never wait for /end — end-of-session recall is what loses items (long
>   sessions get context-compacted; minute-5 facts don't survive to an
>   hour-4 wrap).
> - **Worthiness — all four must hold for a line to earn an ID:** (1) an open
>   loop a future session must act on, with a concrete done-condition;
>   (2) not tracked elsewhere (bugs → the bug doc, features → the backlog,
>   status → the spine); (3) can't just be done now (under ~10 minutes ⇒ do
>   it); (4) one ID per loop — sub-facts ride the parent item.
> - **Size — HARD cap per item** (`.claude/protocol.json` → `ledger.item_max_chars`,
>   default 600): the ID line plus its continuation lines. Longer analysis
>   goes to a bug entry, a backlog entry, `docs/notes/<ID>.md`, or a DECISIONS
>   entry; the ledger line keeps the loop and a pointer. The start hook
>   truncates over-cap items and names them. Closure evidence is one line.
> - Never rewrite or regenerate this file. Lines are only appended, or edited
>   in place from `[ ]` to `[x]` (done — append `→ DONE <date>: <one line>`)
>   or `[-]` (dropped — append the reason).
> - Don't delete or strike an open item you don't recognise — it may belong
>   to a concurrent session running in this same checkout.
> - `/end` reconciles: disposition every `[ ]` you touched, append anything
>   this session queued but didn't capture, prune `[x]`/`[-]` lines older
>   than `prune_closed_after_days` (history lives in git), report the open
>   count against `open_soft_max` and list items older than `stale_after_days`
>   as route-or-close.
> - **IDs are permanent and never reused.** Single-track: `L-1, L-2, …`.
>   **Multi-track** (tracks declared in `protocol.json`): each track mints with
>   its own prefix and its own counter — `D-1, D-2, …` and `M-1, M-2, …` — so
>   two sessions can append at once without colliding. The prefix says who
>   WROTE it. A tag right after the date says who ACTS on it: `→mobile`,
>   `→desktop`, or `→all`; no tag = the writer's own track. Legacy `L-` items
>   keep their numbers forever. If a collision ever lands anyway, renumber the
>   later-referenced item and keep the alias in the surviving line.

<!-- Items start here. Shapes:

Single-track:
- [ ] L-1 (2026-09-08) Live round-trip test of the backup export — done when export → import on a clean install matches the manifest counts.
- [x] L-1 (2026-09-08) Live round-trip test of the backup export … → DONE 2026-09-09: passed, counts matched
- [-] L-2 (2026-09-08) Migrate X to Y → dropped 2026-09-10: superseded by Z

Multi-track:
- [ ] D-1 (2026-09-08) Verify sync status stays steady through a full copy-up — done when the hub mark reads "Backing up" once for the whole run.
- [ ] D-2 (2026-09-08) →mobile Server v134 deployed with the wipe stamp (migration 0030); phone must re-sync before testing wipe-aftermath copy.
- [ ] M-1 (2026-09-08) →all packages/core: `Entry.milestone` is now nullable — rebuild core and re-run the drift guard before the next commit on either track.
-->
