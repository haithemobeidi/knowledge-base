# Knowledge Base — Current State

_Last updated: 2026-10-20 01:09_

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

Nothing is owed in this repo. The next build here waits on the user's four harness-plugin decisions (Open loops, first item); until they answer, the standing item is the version-agnostic upgrade path (second item). Other projects pick up the 2026-10-20 template in their own sessions with `check-template-drift.py --sync` — never from here.

## Template rollout

The template is the KB's real deliverable. This table is what "where do we stand" means here.

| Project | Protocol | Synced to template | Notes |
|---|---|---|---|
| `claude-project-template` | **v2**, hook delivers in parts since 2026-10-20 (`b956737`) | — | canonical |
| Playmoir / Checkpoint | **v2** (migrated 2026-09-22) | **yes** — resynced 2026-10-20 (`b18cefb0`), 6 parts, all under 9,000 | 5 tracks (D, M, I, S, SO), 94 open ledger items, 20KB CURRENT_STATE — ~200% of budget; its SO-5 cleanup |
| BuddySystem | **v2** (bootstrapped 2026-10-02) | behind — needs the 2026-10-20 resync | 3 tracks (coping C, impulse I, rephrase R); until resynced its start context is a 2,000-char preview if over 10K |
| Nuveen-Reporting | v1 | behind | single track |
| Tagsmith, armada-odin3 | protocol.json without a version (v1) | behind | not surveyed further |
| TrainerKit, CLI-LLM-Hub, D4-Optimizer, MPV-Cinema, namesmith | pre-layering (own root PROTOCOL.md) | never installed | migration per `MIGRATION.md` §1–6 |

**Machines:** global layer installed and current on this Windows desktop
(`install-global.py` rerun 2026-10-20). The ARM laptop has never run
`install-global.py` (Checkpoint ledger D-1, open since 2026-09-09); the Linux
laptop's state is unknown. Both need `git pull` **and** `install-global.py`.

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

## Open loops

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
- **Resync the other protocol projects** to the 2026-10-20 template, each in its
  own session: BuddySystem first (v2, 3 tracks), then Nuveen, Tagsmith,
  armada-odin3. Procedure: `MIGRATION.md` §6c.
- **Two untracked files at the KB root await the user's call** (never delete):
  `react19.md` (2026-09-09; drop it + one pointer in `references.md`, or turn it
  into a verified checklist) and `do_for_checkpoint.md` (2026-09-21; the v2
  migration brief, obsolete since 2026-09-22).
- `PROTOCOL.md` is at 202 lines against its own "~200 lines" rule; trim a paragraph
  the next time it is touched.
