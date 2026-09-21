# Knowledge Base — Handoff Log

Append-only, newest at the bottom. One entry per session that did multi-step work here — a template change, a mining pass, a site rebuild. A single lesson written and committed does not need one; its commit message is the record.

Format and rationale: `claude-project-template/project/docs/HANDOFF_LOG.md`. Same I-PASS shape, not re-explained here.

---

## 2026-09-20/21 | Protocol v2 — audit, research, build

**Status:** green — all scripts syntax-checked; both new checks validated against Playmoir's real documents and made to fail on purpose; the v1 path verified unchanged (hook still emits valid JSON at its usual size). Committed and pushed as `70dc989`.

**Changed:** Audited the v1 harness against a live 3-track project and measured session start at 163,478 chars (~41,000 tokens) — five times a normal full Claude Code startup payload, 56% of it `CURRENT_STATE.md`. Traced the cause: the 2026-09-08 ledger caps worked and the mass moved to the one adjacent uncapped document, growing it from 5,968 to 92,900 characters in twelve days. Researched context engineering, agent memory systems, and human shift-handover practice (four subagents, findings in the session scratchpad). Wrote `DESIGN.md`, then built v2: one budget on the assembled payload plus `check-payload-budget.py`; a ledger manifest (61,376 → 12,813 chars measured, all 89 items still listed); `check-ledger-refs.py` for struck IDs still cited in state docs; three v2 document shapes; the I-PASS handoff format; an ACCEPT read-back at `/start`. Fixed two v1 bugs found in the audit: a no-upstream branch reporting "checkout is current" from a fetch that proved nothing, and the ledger's 3,071-char rules header being injected every session despite living in `PROTOCOL.md`.

**Next:** Write `migrate-docs-v2.py`. It must write `.new` files beside the originals and never replace anything — every verb in the migration is *append* or *move*, never delete or summarize. The big piece is mechanical: all 30 session blocks in Playmoir's `CURRENT_STATE.md` carry an ordinal (153rd down to 120th) and all 30 have a matching `HANDOFF_LOG` line, so the narrative merges by joining on the ordinal. The only judgment call is the 38 "Things to watch" bullets, which go to the user as one table (still live / standing fact / obsolete), the same shape `MIGRATION.md` already uses for legacy tag triage.

**If it fails:** If the ordinal join misses entries, do not fall back to summarizing — leave the unmatched blocks in place and report them. Losing detail is worse than a partial migration; the whole design rests on nothing being rewritten. If the migrated payload lands above 25,000 chars, shrink the largest contributor rather than raising the budget: raising it is how v1 failed.

**Confirm:** v2 is **inert** until a project sets `protocol_version: 2`. Before touching Playmoir, restate that syncing the scripts alone changes nothing, and that the 95KB `CURRENT_STATE` comes down only when the documents are migrated — not when the scripts are.

**Also worth knowing:** two claims made during this session were wrong and retracted — that a count of 22 open ledger items citing closed items indicated missed closures (they are provenance and sequencing citations; the ledger is well-kept), and a routing-detection check built on that premise (dropped; it would have false-positived on the first case examined). Do not resurrect either without new evidence. The four research findings files are in the session scratchpad only and will not survive; `DESIGN.md` carries the citations that mattered.

## 2026-09-21 01:40 | Protocol v2 — the three unbuilt pieces, and the lessons

**Status:** green — all scripts syntax-checked and exercised against real data; `ledger-archive.py` dry-run on Playmoir (5 items would move), `end-derive.py` run against this repo, the drift check confirmed fetching. Pushed as `f9bce60` plus the lessons commit.

**Changed:** Closed every gap between what `DESIGN.md` specified and what existed. `check-template-drift.py` now fetches the Knowledge Base clone before comparing against it — it was diffing projects against whatever copy sat on that machine's disk, so a stale clone printed "up to date" about the source of truth for the rules themselves, and that would have bitten on the first attempt to sync the laptop. Added `ledger-archive.py` (moves struck lines to `SESSION_LEDGER_CLOSED.md`; dry run by default, refuses a dirty ledger, balances its line count) and `end-derive.py` (the facts git can prove for a wrap; deliberately does not derive build status). Wrote the two owed KB lessons and the prune-then-dangle extension, regenerated `kb-browser.html` (96 lessons).

**Next:** Nothing is owed here. The Playmoir/Checkpoint migration is the remaining work and belongs in a Checkpoint session with the agent that has that project's context — `MIGRATION.md` §6b is the procedure and the 62-bullet triage happens there, not here.

**If it fails:** If the migration's payload lands above 25,000 chars after the documents are migrated, that is expected and the cause is the ledger's open count (87 items ≈ 12,590 chars of manifest), not the document shapes. Shrink the ledger; do not raise the budget.

**Confirm:** v2 is inert until a project sets `protocol_version: 2`. Restate that before touching any project — syncing the scripts alone changes nothing except two bug fixes.

**Also:** the hosted KB site at the URL in the README is now stale; republish `kb-browser.artifact.html` against that URL when convenient.

## 2026-09-21 01:55 | Protocol v2 — discoverability (delta)

**Status:** green — v1 notice verified firing on Checkpoint and silent on a v2 preview; `kb-browser.html` regenerated. Pushed through `6a67818`.

**Changed:** Delta since 01:40 only. `PROTOCOL.md` mentioned `protocol_version` zero times, so a v1 project loaded the live v2 protocol as if it were in force while running v1 scripts and documents — the two-sources-disagreeing failure, introduced by the v2 work itself. Fixed with a "which shape is this project on?" table in `PROTOCOL.md`, a start-hook notice on any v1 project, and a README row so "update this project to v2" routes to the procedure. Then seeded `CURRENT_PROTOCOL_VERSION` + `UPGRADE_SCRIPTS` and stopped, at the user's call.

**Next:** The upgrade path, generically — see this repo's NEXT ACTION. The v2-specific strings in the hook, `PROTOCOL.md` and the README are the thing to replace.

**If it fails:** If a generic hook message proves too noisy on v1 projects, fold it into the existing template-drift note rather than dropping it — a project silently following the wrong shape is worse than a line of nag.

**Confirm:** Restate that the three v2-mentioning strings exist and where, before writing the generic version — otherwise the generic path lands alongside the hardcoded one instead of replacing it.

