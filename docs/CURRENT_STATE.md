# Knowledge Base — Current State

_Last updated: 2026-11-18_

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

**Checkpoint syncs to the 2026-11-18 template and does its one-time cleanup, in its own session** (`MIGRATION.md` §6e: tag per-track bullets → `state-archive.py --apply` → `shared_owner` → retag `→all` items → park what waits on an event → the gate passes with `--ratchet`). Two parts of it are the user's rulings, not work: which track owns the shared paths (`shared_owner`), and dispositions of one track's items made by another. Then hear back on its first fresh session (§6e's three checks). The 2026-11-12 question is answered: the first fresh Checkpoint session (2026-11-12 21:37) ran `--track social` as its very first command, followed the PAGE line and reported its payload. Other projects pick up the template in their own sessions — the user says "integrate the protocol" there — never from here.

## Template rollout

The template is the KB's real deliverable. This table is what "where do we stand" means here.

| Project | Protocol | Synced to template | Notes |
|---|---|---|---|
| `claude-project-template` | **v2**; load by track, the `/end` budget gate and the lessons queue since 2026-11-12 (`23dc02b`); shared-state exit, one owner per item, parked items since 2026-11-18 | — | canonical |
| Playmoir / Checkpoint | **v2** (migrated 2026-09-22) | synced to 2026-11-12 (its `3975110b`); **behind 2026-11-18** — its cleanup session (`checkpoint-fd`) takes it | 5 tracks at 140–173% of budget on 2026-11-18 (desktop 43,340 · android 41,835 · ios 34,975 · steamos 35,734 · social 40,944), each just under its ceiling. Rehearsal of §6e on a copy with simulated dispositions: 22,629–32,667 (ios and steamos inside the budget) |
| BuddySystem | **v2** (bootstrapped 2026-10-02) | behind — still on the pre-2026-10-20 single hook wiring | 3 tracks; inside budget on a copy (≤42%). Its CURRENT_STATE is 2,356 chars of tables, so the 2026-11-18 shared cap has nothing to do there; 7 of its 10 open items are `→all` (only new ones are stopped) |
| Cove, Cove-ACS-Expert, Zendesk-Copilot, armada-astra2, final-fantasy-resonance-ultrawide | v2, single track | behind the 2026-11-12 template | start payload unchanged by it and by 2026-11-18 (verified byte-identical on Cove, Zendesk-Copilot, armada-astra2, Tagsmith, Interview-Prep); they gain the gate + lessons queue + parking |
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

**Shared state with an exit, one owner, parked items (2026-11-18).** Answers
Checkpoint's D-106 second round: the ceilings held, nothing shrank. A
CURRENT_STATE bullet tagged `- →<track>` loads only for that track; the
untagged shared bullets are capped (`state.shared_max_chars`, 5,000) and
`state-archive.py` moves the oldest to `docs/CURRENT_STATE_ARCHIVE.md`;
`shared_owner` in protocol.json; ledger `[~]` parked items counted by the event
they wait on (`ledger-archive.py --park/--unpark/--parked`); the gate
(`--track <name>`) stops on a shared block over its cap, a new `→all` item from
the wrapping track, or a parked item with no event. One parser for all three
readers (`protocol_config.state_segments`). A sync now adds any script the
template gained in one run. `PROTOCOL.md` #11, `DESIGN.md` "Found after
shipping … (2026-11-18)", `MIGRATION.md` §6e.

## Open loops

- **Unproven in a live session:** the phrase "integrate the protocol" (2026-11-12),
  and everything from 2026-11-18 (rehearsed on copies of Checkpoint's documents
  only). The `--track` load is proven: 6 of the 7 working Checkpoint sessions
  since 2026-11-12 ran it as their first or second command; the seventh, a
  20-call audit of another session's fix (2026-11-13 01:03), never loaded a
  track — worth knowing, not worth a rule yet.
- **Offered to the user 2026-11-12, not asked for — do not start unasked:**
  (a) keep a small working-notes file per session and re-inject it after a
  compaction (11 of 18 Checkpoint sessions auto-compacted; about 1,000
  characters of rules come back and none of the state); (b) the mini-wrap entry
  replaces the full handoff entry the next session needs (recorded in
  Checkpoint's D-106); (c) a "how we do this" line in the handoff for routines;
  (d) one resumed session received 4 of 8 hook parts (seen once, 2026-11-01,
  cause not found). ((e), a triage table for Checkpoint's shared state and
  `→all` items, became the 2026-11-18 template change and Checkpoint's §6e
  cleanup.)
- **Lessons flagged, not written:** a check that only reports gets ignored; it
  has to be able to stop the work (Checkpoint's budget, seven weeks). And
  2026-11-18: a ceiling stops growth but shrinks nothing — whatever every reader
  pays for needs an exit, or it only accumulates (`PROTOCOL.md` #11).
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
