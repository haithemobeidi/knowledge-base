# Knowledge Base — Current State

_Last updated: 2026-09-21 02:05_

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

Build the version-agnostic upgrade path (see Open loops): a global `/upgrade` command beside `/start` and `/end`, and a start-hook message that compares `protocol_version` against `CURRENT_PROTOCOL_VERSION` instead of naming v2. Do it before v3 exists, not after.

Separately and **not this repo's job**: migrating Playmoir/Checkpoint to v2 happens in a Checkpoint session with the agent that has that project's context — `MIGRATION.md` §6b, and the 62-bullet triage belongs there. Dry run done 2026-09-21: **167,474 → 31,004 chars, ~41,000 → ~7,751 tokens**; CURRENT_STATE 95,107 → 8,939; conservation checked (90,453 out, 91,698 in). It lands at 124% of the 25,000 budget, and the cause is the ledger's 87 open items, not the document shapes — shrink the contributor, not the budget.

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

Everything `DESIGN.md` specifies is now built. `migrate-docs-v2.py` is written
and dry-run against Playmoir; `ledger-archive.py` does the recurring closed-line
move; `end-derive.py` supplies the wrap's facts from git. The drift check now
fetches the KB clone before comparing against it, and the start hook warns when
this machine's clone has gone quiet — that gap would have bitten on the first
attempt to sync the laptop.

## Open loops

- Playmoir migration not yet applied (its own session, with the Checkpoint agent)
- **A version-agnostic upgrade path** (user, 2026-09-21). v2 will not be the last
  shape, and the v1-vs-v2 notice shipped in `66d8b6c` hardcodes "v2" in the hook,
  `PROTOCOL.md` and the README — all three need rewriting at v3. The seed is in
  place: `protocol_config.CURRENT_PROTOCOL_VERSION` and the `UPGRADE_SCRIPTS`
  map (target version → the script that migrates into it, one hop each), both
  currently unused. What is NOT built, deliberately: a global `/upgrade` command
  alongside `/start` and `/end` (installed by `install-global.py`, so the user
  types one word in any project), a generic start-hook message that names the
  two version numbers instead of mentioning v2, and multi-hop dispatch for a
  project two shapes behind. Do this before v3, not after.
- The three owed lessons are written: `shared-budget-caps-relocate-mass.md`
  (which absorbed catalog-plus-fetch as its fix section rather than splitting one
  idea across two files) and `handoff-for-a-reader-with-no-memory.md`, plus the
  prune-then-dangle extension inside `parallel-writers-minting-ids-collide.md`.
