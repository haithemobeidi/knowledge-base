# <ProjectName> — Current State

**Current phase:** <Phase/Block name> — <one-line status>
**Build status:** not yet tested

_Last updated: <YYYY-MM-DD HH:MM> (<track, if any>)_

> **This file is the state of the APP, not the state of the session.** The test for
> every line: *if we are on 1.0.1, what does that entail?* Version, what is shipped
> where, what works, what is next. Nothing else.
>
> It is injected WHOLE at every session start, so it is the one document whose size
> is always a cost. Keep it small by keeping it to its job:
>
> - **No session narrative.** What happened goes in `docs/HANDOFF_LOG.md`, one entry
>   per session, and only the newest entry per track is ever injected. A "what the
>   last sessions did" section here grew to 58,000 characters on a real project.
> - **No restating a ledger item's status.** Cite the ID. A status written here is a
>   second copy that nothing keeps true — 65 of 146 IDs cited in that same real file
>   were already struck.
> - **No copy of the phase/block list.** That is the spine in `ROADMAP.md`.
> - **Derived fields are generated at `/end`**, not typed.
>
> Overwrite at `/end` after re-reading from disk; never append.

---

## 📍 NEXT ACTION

<ONE unambiguous line — the single next thing to do, matching the spine's CURRENT phase/block. Session start reports it verbatim.>

<!-- Cite the ledger IDs this action depends on (`M-38`, `D-12`). The start hook
     gives FULL TEXT to the items cited here and a one-line title to every other
     open item, so this line is what decides what gets read in depth. -->

<!-- MULTI-TRACK REPOS: one section per track, plus a Shared block. Each session
     rewrites only its own section and the shared facts it changed; the other
     track's section is copied through verbatim.

## 📍 NEXT ACTION — desktop
<one line>

## 📍 NEXT ACTION — mobile
<one line>
-->

## Shipped

<What exists, per track, with the version a user would see. A row is a fact about
the product, not a history of how it got there.>

| Track | Version | Where | Notes |
|---|---|---|---|
| <desktop> | <1.0.1> | <released / in review / internal> | <…> |

## Build status

<working / broken / not yet tested — what was verified, on what, when. Per track in
multi-track repos. Generated at `/end` from the last check run where possible.>

## Shared services

<Multi-track or client+server only. Deploy state both sides consume, each stamped
`(by <track>, <date>)`. Facts about what is live — NOT what a session did to it, and
never a ledger item's status.>

- Server: v<N> live — <what it carries>
- Schema: migration <NNNN> applied

## Active blockers

None.

## Open loops

<Pointer only: "open: L-3, D-8 — see docs/SESSION_LEDGER.md". No prose list;
regenerated prose silently drops items, and a status written here goes stale.>
