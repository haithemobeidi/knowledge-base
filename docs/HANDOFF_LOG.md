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


## 2026-10-02 02:10 | Two lessons + ledger-archive fix (from BuddySystem)

**Status:** green — fixed `ledger-archive.py` dry-run against BuddySystem's fresh v2 ledger reports nothing to move (before the fix it listed the header comment's example lines L-1, L-2 as closed items). `kb-browser.html` regenerated.

**Changed:** New lessons `wireless-adb-refused-means-unpaired.md` and `on-device-llm-refuses-profane-input.md`, each with a README one-liner. `ledger-archive.py` now skips chunks inside HTML comment blocks, the same way `session-start-context.py` already did (additive only). BuddySystem added to the rollout table. Hosted KB browser not republished.

**Next:** Projects pick up the script fix with `check-template-drift.py --sync`. BuddySystem is the one that hit it.

**If it fails:** If a ledger ever puts real items inside a comment on purpose, they'll now never move. That's the intended trade: never archive what the start hook doesn't count.

**Confirm:** The fix only adds a comment-state check before the `[x]/[-]` match; nothing else in the script changed.


## 2026-10-20 01:09 | Template — start hook delivers in parts (the 10,000-char hook cap)
**Status:** green — verified on a throwaway copy of Checkpoint's real documents: 7 parts, every one under 9,000 chars, zero legacy lines missing from the reassembled parts, one-part cache silences parts 2..8, slim reminder 1,078 chars; then live on Checkpoint after its resync (`b18cefb0`): 6 parts, 8 entries wired, no UNDELIVERABLE, drift "up to date". KB pushed as `b956737`; hosted site republished (129 lessons); `install-global.py` rerun here.

**Changed:** The audit of the session protocol against current harness facts found the load-bearing one: Claude Code caps a hook string at 10,000 characters and injects a 2,000-char preview plus an unread file path beyond it (38 overflow files on disk for Checkpoint, 2026-09-20 → 10-02; 7 read back). `session-start-context.py` now packs whole sections into parts under `payload.part_chars` (9,000 minus a header reserve), part 1 builds + prints the payload size + writes a per-session cache in the temp dir keyed by the hook's `session_id`, parts 2..8 wait for a cache newer than their own start and emit their slice or nothing; overflow beyond the wired entries is announced in the last part. `settings.json` wires `--part 1..8` (timeout 90) and a `compact` entry running `--slim`. Manifest lines are `ID →tag (date) TITLE` (bold title after the provenance parenthetical; 0 of 94 Checkpoint lines come back titleless, median 136 chars). Gating is per NEXT ACTION section (`max_gating_items`, default 4) with `gating_item_max_chars` 1,200. `check-payload-budget.py` prints a Delivery block and fails on UNDELIVERABLE separately from OVER BUDGET, and flags the legacy single wiring. `track-new-file.py` skips binaries/media (+ `index_skip_suffixes`). Tracks may carry `check_command` (`None` = repo-wide, `""` = none; `end.md` Step 0c says so). Docs: `PROTOCOL.md` #9 + budget section + hooks table (now 202 lines), `DESIGN.md` "Found after shipping", `MIGRATION.md` §6c, template README ledger paragraph, this repo's rollout table. Lesson `hook-output-string-cap-measure-what-arrives.md` + README line. Carried the Checkpoint social session's three KB files (news-graphics lesson, README line, social-posts skill rows). Checkpoint's own side (its session, `c5967d68` + `b18cefb0`): protocol.json stale keys, CLAUDE.md iOS rows, SO-7/SO-8 cross-track lines, DECISIONS tail order, the six synced files, `max_gating_items` 3, social `check_command` "".

**Next:** Nothing owed here. The user has four harness-plugin decisions open (CURRENT_STATE → Open loops); BuddySystem and the v1 projects need the §6c resync in their own sessions. Trim `PROTOCOL.md` by a paragraph next time it is touched.

**If it fails:** If a session start ever shows only part 1, or "incomplete" from part 2, part 1 did not finish within `part_wait_seconds` (45) — usually a slow `git fetch`; the user runs `/start` by hand and we raise the wait or move the fetch. If parts arrive but the directive is missing, check that `settings.json` was synced (legacy single wiring is what the budget checker now calls out). If a `resume` shows stale content, the cache freshness rule (mtime ≥ process start − 5 s) is what to inspect.

**Confirm:** Restate that the budget is still 25,000 and that the 8 × 9,000 deliverable ceiling is a safety net, not a licence — Checkpoint at ~200% of budget is a Checkpoint cleanup (SO-5), not a template change.
