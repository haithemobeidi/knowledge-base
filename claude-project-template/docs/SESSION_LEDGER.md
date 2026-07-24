# Session Ledger — open items that must not get lost

> **What this is:** the append-and-strike ledger for session-scoped open items —
> queued tests, pre-release gates, riders, deferred decisions, watch items.
> Anything phrased like "next session," "before release," "rider candidate,"
> "queued," or "check later" gets a line HERE at the moment it's said.
>
> **Rules (full rationale in `PROTOCOL.md` → "Open-item ledger discipline"):**
>
> - **Append at the moment of queueing; strike at the moment of resolution.**
>   Never wait for /end — end-of-session recall is what loses items (long
>   sessions get context-compacted; minute-5 facts don't survive to an
>   hour-4 wrap).
> - Never rewrite or regenerate this file. Lines are only appended, or edited
>   in place from `[ ]` to `[x]` (done — append `→ DONE <date>: <one-line
>   evidence>`) or `[-]` (dropped — append the reason).
> - Don't delete or strike an open item you don't recognize — it may belong to
>   a concurrent session running in this same checkout.
> - `/end` reconciles: disposition every `[ ]`, append anything this session
>   queued but didn't capture, prune `[x]`/`[-]` lines older than 7 days
>   (their history lives in git).
> - Not for bugs, feature ideas, or phase/block status — those keep their own
>   homes (bug tracker doc, feature backlog doc, ROADMAP spine). One concept,
>   one home.
> - IDs increment forever (L-1, L-2, …); never reuse a number.

<!-- Items start here. Example shapes:
- [ ] L-1 (YYYY-MM-DD) Live round-trip test of the backup export (queued as "first thing next session")
- [x] L-1 (YYYY-MM-DD) Live round-trip test … → DONE YYYY-MM-DD: passed, counts matched manifest
- [-] L-2 (YYYY-MM-DD) Migrate X to Y → dropped YYYY-MM-DD: superseded by Z
-->
