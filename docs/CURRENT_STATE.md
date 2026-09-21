# Knowledge Base — Current State

_Last updated: 2026-09-21 01:05_

> **Deliberately minimal.** This repo is a reference library and the home of the
> project template, not an app — so it carries two documents and no machinery:
> this file and `HANDOFF_LOG.md`. No hooks, no ledger, no scripts, no `/start`.
> Nothing auto-loads them; a session working on this repo reads them first.
>
> They exist because multi-session work happens here — a template change, a
> mining pass, a site rebuild — and until now that work lived entirely in one
> session's context. A session that ended mid-build left nothing behind. That is
> the exact failure the template's protocol exists to prevent, and this repo did
> not have it.
>
> Keep this file to the state of the **repo**: what the template is at, what is
> rolled out where, what is in flight. Session narrative goes in the handoff log.

---

## 📍 NEXT ACTION

Migrate Playmoir/Checkpoint to v2, in a session where no other session is open in that checkout: `check-template-drift.py --sync`, run `migrate-docs-v2.py`, take the 62-bullet triage table to the user (K/L/A per bullet), fill the new **Shipped** section by hand, replace the originals, then set `protocol_version: 2`.

Dry run already done (2026-09-21, output in a scratchpad that will not survive — re-run it): **167,474 → 31,004 chars, ~41,000 → ~7,751 tokens.** CURRENT_STATE 95,107 → 8,939. Struck-ID citations 150 → 20. Conservation checked: 90,453 left CURRENT_STATE, 91,698 arrived in the archive.

Still 124% of the 25,000 budget afterwards, and the largest contributor is then the ledger manifest (12,590 chars, 87 open items). Getting under needs the one-time ledger triage that has been deferred as Playmoir's L-114 — the v2 two-per-wrap rate would take ~29 sessions on its own. **Shrink the contributor; do not raise the budget.**

## Template rollout

The template is the KB's real deliverable. This table is what "where do we stand" means here.

| Project | Protocol | Synced to template | Notes |
|---|---|---|---|
| `claude-project-template` | **v2** (`70dc989`) | — | canonical |
| Playmoir / Checkpoint | v1 | behind | 3 tracks, 89 open ledger items, 95KB CURRENT_STATE — the migration case |
| everything else | v1 | unknown | not surveyed |

**Machines:** global layer installed on this Windows desktop. The ARM laptop and
the Linux laptop have not pulled since `70dc989` — they need `git pull` **and**
`install-global.py` (the `@import`s are live, the command and agent copies are not).

## Protocol v2 — what is built

Built and committed in `70dc989`: the payload budget and its guard, the ledger
manifest, the struck-ID guard, the three v2 document shapes, the I-PASS handoff
format, the ACCEPT step, and two v1 bug fixes. Reasoning and sources are in
`claude-project-template/DESIGN.md`.

**v2 is inert until a project opts in.** `protocol_version` defaults to 1, so a
project that syncs the scripts behaves exactly as it did before.

`migrate-docs-v2.py` is written and dry-run against Playmoir. Not built:
`end-derive.py` (the derived build-status and changed-files fields), and the
recurring `SESSION_LEDGER_CLOSED.md` move at `/end` — the migration script does
the one-time move, but the ongoing one is specified in `end.md` Step 1d.4 with
no script behind it, which by this protocol's own standard means it will not
happen.

## Open loops

- `migrate-docs-v2.py` — written; dry-run verified against Playmoir, not yet applied
- `end-derive.py` — not written
- The closed-line move is prose-only, no script
- Three KB lessons are owed from this work: the shared-payload-budget lesson
  (its incident is already in `DECISIONS.md` 2026-09-08 and was never distilled),
  catalog-plus-fetch as an information-architecture pattern, and writing state
  for a reader with no memory of the session that wrote it. Two extensions:
  a prune-then-dangle case in `parallel-writers-minting-ids-collide.md`, and the
  growth-default half beside `n-copies-of-truth-drift-guard.md`.

## Active blockers

None.
