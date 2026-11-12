# Knowledge Base — Current State

_Last updated: 2026-11-12 01:50_

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

**Hear back on the first live Checkpoint session after its 2026-11-12 sync** (Open loops, first item): did it run the `--track` load command after the track was named, before any other read or edit? That is the one part of the 2026-11-12 template that was never proven. If it did, nothing is owed here; if it did not, tighten the directive in `session-start-context.py`. Other projects pick up the template in their own sessions — the user says "integrate the protocol" there — never from here.

## Template rollout

The template is the KB's real deliverable. This table is what "where do we stand" means here.

| Project | Protocol | Synced to template | Notes |
|---|---|---|---|
| `claude-project-template` | **v2**; load by track, the `/end` budget gate and the lessons queue since 2026-11-12 (`23dc02b`) | — | canonical |
| Playmoir / Checkpoint | **v2** (migrated 2026-09-22) | **yes** — synced and adopted 2026-11-12 (its `3975110b`) | 5 tracks. Per-track start payload 34K–43K (was 76.8K for every session), each with a ceiling; 113 open ledger items after 11 lessons moved to its queue. Still 137–171% of budget: ~15K of shared CURRENT_STATE every track loads + 42 `→all` items — a triage sitting with the user |
| BuddySystem | **v2** (bootstrapped 2026-10-02) | behind — still on the pre-2026-10-20 single hook wiring | 3 tracks; the only other project whose session start changes with the 2026-11-12 template. Inside budget on a copy (≤42%) |
| Cove, Cove-ACS-Expert, Zendesk-Copilot, armada-astra2, final-fantasy-resonance-ultrawide | v2, single track | behind the 2026-11-12 template | start payload unchanged by it (verified byte-identical on Cove, Zendesk-Copilot, armada-astra2); they gain the gate + lessons queue |
| Interview-Prep, Stash, Texsmith, Nuveen-Reporting, Tagsmith, armada-odin3 | v1, single track | behind (the last three also predate the 2026-10-20 parts wiring) | same: nothing about their start changes |
| TrainerKit, CLI-LLM-Hub, D4-Optimizer, MPV-Cinema, namesmith | pre-layering (own root PROTOCOL.md) | never installed | migration per `MIGRATION.md` §1–6 |

How any of them catches up: in that project's own session the user says **"integrate the protocol"** (`PROTOCOL.md`, top) — the agent pulls the KB, reruns the install script, syncs, adopts, commits. What runs per machine vs per project: template `README.md` → "Rolling out a template change".

**Machines:** global layer installed and current on this Windows desktop
(`install-global.py` rerun 2026-11-12). The ARM laptop has never run
`install-global.py` (Checkpoint ledger D-1, open since 2026-09-09); the Linux
laptop's state is unknown. Both need `git pull` **and** `install-global.py`
— until then their `/start` and `/end` are the old copies, which still work
(the rules are written so older scripts and commands keep their behaviour).

## Protocol v2 — what is built

Built and committed in `70dc989` (2026-09-21): the payload budget and its guard, the
ledger manifest, the struck-ID guard, the three v2 document shapes, the I-PASS
handoff format, the ACCEPT step. Reasoning and sources are in
`claude-project-template/DESIGN.md`. **v2 is inert until a project opts in**
(`protocol_version` defaults to 1).

**Delivery in parts (2026-10-20, `b956737`).** Claude Code caps one hook string at
10,000 characters and swaps anything longer for a 2,000-character preview plus a
file path it never asks the model to read — so for a month every Checkpoint
session start received the preview, not the payload. The start hook now packs
the payload into labelled parts under `payload.part_chars` (9,000); `settings.json`
wires it 8× (`--part 1..8`) plus a `compact` entry (`--slim`). Part 1 builds,
prints the payload size and caches per session; the rest wait for the cache and
emit their slice. With it: manifest lines render `ID →tag (date) TITLE`; gating is
per NEXT ACTION section with capped expansions; `check-payload-budget.py` reports
delivery and fails on UNDELIVERABLE; the index hook skips binaries; a track may
declare its own `check_command`. `PROTOCOL.md` #9, `DESIGN.md` "Found after
shipping", `MIGRATION.md` §6c record it; lesson
`hook-output-string-cap-measure-what-arrives.md`.

**Load by track, the budget gate, the lessons queue (2026-11-12, `23dc02b`).**
Answers Checkpoint's D-106 ("fix it for good"). A v2 project with two or more
tracks gets a ~5,000-character core from the hook and each session loads its own
track with `session-start-context.py --track <name>`; single-track and v1 output
is byte-identical to before. `/end` Step 3b is a gate
(`check-payload-budget.py --strict --ratchet`); a project already over budget
gets a per-track ceiling once, at adoption, and it only moves down. Unwritten
lessons go to `docs/LESSONS_QUEUE.md`, not the ledger; titles starting `DECIDE:`
are listed first as the user's calls. `check-template-drift.py --sync` does the
adoption (`--adopt` alone for the first hop). `PROTOCOL.md` #10 and "Integrate
the protocol", `DESIGN.md` "Found after shipping … (2026-11-12)", `MIGRATION.md`
§6d, template `README.md` "Rolling out a template change".

## Open loops

- **Unproven in a live session (2026-11-12):** that a session runs the `--track`
  command once the track is named. Rehearsed on copies and adopted for real on
  Checkpoint, but the first fresh Checkpoint session had not been observed when
  this was written. Also unproven: the phrase "integrate the protocol" in a live
  session.
- **Offered to the user 2026-11-12, not asked for — do not start unasked:**
  (a) keep a small working-notes file per session and re-inject it after a
  compaction (11 of 18 Checkpoint sessions auto-compacted; about 1,000
  characters of rules come back and none of the state); (b) the mini-wrap entry
  replaces the full handoff entry the next session needs (recorded in
  Checkpoint's D-106); (c) a "how we do this" line in the handoff for routines;
  (d) one resumed session received 4 of 8 hook parts (seen once, 2026-11-01,
  cause not found); (e) a triage table for Checkpoint's shared state and `→all`
  items.
- **Lesson flagged, not written:** a check that only reports gets ignored; it
  has to be able to stop the work (Checkpoint's budget, seven weeks).
- **Harness repo as a plugin for the buddy** (user asked "can we do that", 2026-10-20;
  plan given, four decisions unanswered): private or public · scripts in the plugin
  vs copied per repo · buddy on `main` under track rules vs his own branch with a
  light mode · keep the Checkpoint-grown defaults or strip to the core. Separate
  repo, not in the KB. Unverified before building: whether plugin skills answer to
  plain `/start` or need a `harness:` prefix, and whether Claude Code prompts a
  collaborator to install a project-enabled plugin. Do not start unasked.
- **A version-agnostic upgrade path** (user, 2026-09-21). The v1-vs-v2 notice
  hardcodes "v2" in the hook, `PROTOCOL.md` and the README. Seed in place:
  `protocol_config.CURRENT_PROTOCOL_VERSION` + `UPGRADE_SCRIPTS`, both unused.
  Not built: a global `/upgrade` command, a generic start-hook message naming the
  two version numbers, multi-hop dispatch. Do this before v3, not after.
- **Sync the other protocol projects** to the current template, each in its own
  session ("integrate the protocol"): BuddySystem first (v2, 3 tracks), then the
  single-track ones at any quiet point. Procedure: `MIGRATION.md` §6d (it
  includes §6c's parts wiring, since the sync copies `settings.json`).
- **Two untracked files at the KB root await the user's call** (never delete):
  `react19.md` (2026-09-09; drop it + one pointer in `references.md`, or turn it
  into a verified checklist) and `do_for_checkpoint.md` (2026-09-21; the v2
  migration brief, obsolete since 2026-09-22).
- `PROTOCOL.md` is at 221 lines against its own "~200 lines" rule (202 before
  2026-11-12; this session added to it and trimmed nothing). It wants a real
  trim, as its own sitting.
