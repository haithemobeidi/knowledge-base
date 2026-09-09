# Session Protocol (global)

**Applies to any repo that carries `.claude/protocol.json`.** If the repo you are in has no such file:

- It has its own `PROTOCOL.md` at the root → it is a **not-yet-migrated** protocol project. **Its own `PROTOCOL.md` and its own `/start` / `/end` commands win**; ignore this file (the global work style still applies). Mention once that `MIGRATION.md` in the template brings it onto this layer.
- Otherwise this protocol is off: ignore it entirely and work normally.

This file is the **single source of truth** for how sessions start, run, and end. It is imported from `~/.claude/CLAUDE.md` on every machine (see "Layering") and is never copied into a project. The step-by-step procedures live in the `/start` and `/end` commands; this file holds the rules and the reasons.

---

## Why this exists

Every rule here traces to a measured failure on a real project:

1. **The codebase index drifted silently** because updating it relied on discipline at the worst moment (end of session, context full), and its one escape hatch ("skip if no major changes") was taken even when major changes existed. → Enforced by a hook + a mandatory `/end` gate. General lesson: a protocol step with a discretionary skip clause is not a step.
2. **Overlapping protocol documents drifted apart.** → One protocol, one copy, imported everywhere.
3. **Heavy end-session ceremony got skipped.** → Automation does the reading; the human-visible part is a 4-line report.
4. **End-of-session recall lost facts** (a passed test vanished from a wrap; shipped work sat listed as open; the same work was recorded twice). → The ledger is written at the moment of the event, and post-wrap work gets a delta-only mini-wrap.
5. **Two concurrent sessions collided** (seven ID-collision repair commits in one month; the other session's files staged by accident). → Parallel tracks are declared, IDs are prefixed per track, ownership is explicit.
6. **The ledger grew into what it was meant to prevent** (99 open items averaging 2,500 characters, ~250KB injected at every session start). → Hard size caps, truncation at injection, age flags.

---

## Layering — global vs project

| Layer | Lives in | Loaded | Holds |
|---|---|---|---|
| **Global work style** | `<KB>/claude-project-template/global/WORK_STYLE.md` (+ `_DETAIL`) | Every session on this machine, via `~/.claude/CLAUDE.md` import | How the user works with Claude, in any app |
| **Global protocol** | this file | Every session | Session lifecycle, ledger, tracks, hooks |
| **Global commands** | `~/.claude/commands/start.md`, `end.md` (copied by `install-global.py`) | On `/start`, `/end` | The step lists |
| **Project file** | `<repo>/CLAUDE.md` | Every session in that repo | What is different about THIS app: identity, stack, layout, project rules, explicit overrides |
| **Project settings** | `<repo>/.claude/protocol.json` | Read by the scripts | Check command, push policy, skip paths, ledger caps, tracks |
| **Enforcement** | `<repo>/.claude/scripts/`, `settings.json`, `agents/` | Hooks | Byte-identical across projects; checked against the template |

**A project rule may only do three things:** add a rule specific to this app, point at where things live, or **explicitly override** a global rule in the project file's Overrides section (naming the rule and the reason). A rule that would be true in another app belongs in the global file or the Knowledge Base, not the project file. Anything else in a project file that contradicts this protocol is a mistake to flag, not an instruction to follow.

**Keeping in sync:** the template is canonical. The start hook reports when a project's scripts differ from the template or the global command copies are stale; `python .claude/scripts/check-template-drift.py` gives details and `--sync` resyncs (after the user agrees). After every Knowledge Base pull, rerun `install-global.py` on that machine.

---

## Files this protocol manages

| File | Purpose | When updated |
|---|---|---|
| `docs/CODEBASE_INDEX.md` | One line per meaningful file | When an unindexed file is created or edited (hook-enforced at `/end`) |
| `docs/CURRENT_STATE.md` | Rolling snapshot: NEXT ACTION (one per track) + this-session deltas + shared state | At `/end` (overwrite; re-read from disk first) |
| `docs/HANDOFF_LOG.md` | Append-only one-line-per-session history | At `/end` (append) |
| `docs/SESSION_LEDGER.md` | Append-and-strike ledger of open session-scoped items | **At the moment** an item is queued or resolved; reconciled at `/end` |
| `ROADMAP.md` status spine | Source of truth for phase/block status | When status actually changes |
| `.claude/pending-index-updates.txt` | Transient queue of unindexed paths | Auto (hook) |

No per-session handoff snapshot files: past projects accumulated 30+ and nobody read past the newest.

---

## Where-are-we: one source of truth, frozen numbers

The **"status at a glance" spine table in `ROADMAP.md`** is the sole answer to "where does the project stand?" (heading configurable via `spine_heading`). `CURRENT_STATE.md` points at it and never keeps its own copy of the list. Two docs answering the same question is the most reliable way to drift a project.

**Numbers are frozen.** Identity is the name; the number is a permanent label. A cut item stays as a labeled gap, never reused, never resequenced.

**Spine cells stay short:** a status marker, the gate holding the item open, at most a pointer. Session history goes to `HANDOFF_LOG.md`. (One cell grew to 62KB of narrative and rode into every session start; the hook now warns at 1,500 characters.)

---

## Session start

Mostly automatic: the `SessionStart` hook runs the worktree guard, checks the global rules are installed, fetches origin, and injects the state docs plus the cross-check directive. `/start` exists for when the hook did not fire. In order:

0. **Worktree guard** — never work from `.claude/worktrees/` or a `claude/*` branch.
0.5 **Sync guard** — `git fetch` before reading any doc. Behind + clean → `git pull --ff-only`. Behind + dirty, or diverged → stop and surface. Offline → proceed, report currency as unverified. `git status` saying "up to date" without a fetch proves nothing; a stale checkout looks complete, not broken.
0.7 **Track gate** (multi-track repos only) — know which track this session is before reading or editing anything (see "Parallel tracks").
1–5. Read CURRENT_STATE (your track's NEXT ACTION), the open ledger items, the last handoff lines (yours), the spine; run the working-tree check and the project's `audit_command` if set.
6. **CROSS-CHECK (mandatory):** NEXT ACTION vs spine CURRENT vs last handoff "Next:" vs open gates. Contradiction → stop and surface; never pick one silently.
7. Report: track (if any) / where we are (name + number) / last session's result / the single NEXT ACTION / open items with gates / **sync line** stating currency.

---

## During the session

**Code quality** (stack-specific rules live in the project file; these hold everywhere): files do one thing, 500-line soft cap and 800 hard, propose splits before 500; DRY at 3+ uses (2 only when the shape is certain AND drift has real cost — when the abstraction might be wrong, duplication is cheaper than the wrong abstraction); group by feature, not by type — no `utils/` or `helpers/` dumping grounds; comments explain why; no premature abstractions.

**Git:** commit each verified pause-point, never one big wrap commit. Never commit without the user confirming the feature works. Push per `push_policy` (`ask` unless the project set `standing` and recorded it in DECISIONS.md). Stage explicit paths — never `git add -A`.

**Codebase index:** the hook queues any unindexed file you Write or Edit; `/end` cannot complete while the queue is non-empty. Descriptions go in the index, not in file headers.

**Narrative docs only at `/end`:** CURRENT_STATE, HANDOFF_LOG, CODEBASE_INDEX. Pause-point feedback reframes work; mid-session doc edits get rewritten and pollute history.

**The ledger at the moment of the event** — the scoped exception:
- The moment work is queued or deferred ("next session", "before release", "check later", a rider, a gate) → append a `[ ]` line right then.
- The moment it resolves → strike right then: `[x]` + `→ DONE <date>: <one line>`, or `[-]` + reason.
- **Worthiness — all four must hold for a line to earn an ID:** (1) it is an open loop a future session must act on, with a concrete done-condition; (2) it is not tracked elsewhere (bugs → the bug doc, deferred features → the backlog, status → the spine); (3) it cannot just be done now (under ~10 minutes ⇒ do it); (4) one ID per loop — sub-facts ride the parent.
- **Size (hard):** one item ≤ `ledger.item_max_chars` (default 600). Analysis longer than that goes to a bug entry, a backlog entry, a `docs/notes/<ID>.md`, or a DECISIONS entry; the ledger line keeps the loop and a pointer. The start hook truncates over-cap items and names them. A closed line's evidence is one line.
- **Count (soft):** over `open_soft_max` (default 30) → `/end` says so and offers a triage pass. Items older than `stale_after_days` (default 45) are listed at `/end` as route-or-close.
- Never strike a line you merely don't recognise; never renumber; IDs are permanent.

**Check stale messages before re-changing:** after a fix lands, confirm the issue is still current before changing the code again — the user may have queued the message before testing.

---

## Parallel tracks — two versions of the app, two sessions, one checkout

Declared in `protocol.json` → `tracks` (name, ID prefix, owned paths) and `shared_paths`. With fewer than two tracks none of this applies. With two or more:

1. **Declare your track before anything else.** From the user's first message if it names it; otherwise ask and wait. The report's first line is `Track: <name>`. Commit subjects carry it: `Session (desktop): …`, `Session followup (mobile): …`.
2. **IDs are prefixed per track and counters are independent.** Desktop mints `D-1, D-2…`, mobile `M-1, M-2…`. Two writers can append at once without colliding. Legacy unprefixed IDs stay as they are forever (frozen references). The prefix says who wrote it; a tag `→<track>` or `→all` **right after the ID** (`M-3 →desktop (2026-09-09) …`; also accepted after the date) says who acts on it. Legacy unprefixed items get that tag once, at migration, so they scope to a track without renumbering. If a collision ever happens anyway: renumber the later-referenced item and keep the alias in the surviving line.
3. **Ownership.** Edit only your track's owned paths and the shared paths. Never edit the other track's owned paths, its ledger lines, or its section of CURRENT_STATE. You may strike a line tagged for you or `→all` that you resolved (note "closed by <track>").
4. **Shared paths are announced.** A change in a shared path (core package, server, schema) gets a ledger line tagged `→all` or `→<other track>` saying what changed and what the other side must do (rebuild, redeploy, run a migration). Deploy state of shared services is recorded in CURRENT_STATE's Shared block.
5. **The tree is not yours alone.** The other session's uncommitted files sit in the working tree; leave them, never stage them, and say so at wrap. The stop hook tolerates dirty files only inside the other track's owned paths; anything dirty in shared or undeclared paths must be accounted for explicitly. `git add -A` is forbidden.
6. **A push publishes the whole branch.** Before pushing, `git log origin/main..HEAD`; name any commits that are not yours in the report. Never push if the user has said the other track's commits are not ready.
7. **State docs are per track.** CURRENT_STATE has one NEXT ACTION section per track plus a Shared block; at `/end` re-read it from disk and rewrite only your section and the shared facts you changed. HANDOFF lines carry the track as the second field; the cross-check uses your track's last line, not the last line overall. The spine may carry one CURRENT marker per track, `⬅ CURRENT (desktop)`.
8. **Keep one checkout.** Both sessions run on the same branch in the same folder on purpose: they see each other's work instantly and the mobile build tests against the live server the desktop track deploys. Separate clones would need a merge before either side saw a shared change. The rules above are the price of that.

---

## Session end (`/end`)

0. Worktree guard; phantom-dirty refresh; **project check** (`check_command`, stop on failure); **secret scan** (`secret_scan`, stop on findings).
1. Index: drain the pending queue; diff backstop; phantom-row check.
1d. Reconcile the ledger from disk BEFORE writing CURRENT_STATE: disposition what you touched, append what you queued, prune closed lines older than `prune_closed_after_days`, report count vs soft max and stale items.
2. Reconcile the spine (short cells), then re-read and overwrite CURRENT_STATE (your track's section only in multi-track repos).
3. Append ONE handoff line (~300-char summary cap; track field in multi-track repos).
4. Commit `Session: …` (with `(track)` if any); push per policy; **clean-tree guarantee** — categorise every remaining dirty path; confirm the mainline is published.
5. Report: accomplished / next / watch / open items (+ any commits pushed that were not yours).

**Between sessions:** `/clear`, new session, the hook does the rest. Do not `/start` in the session that just ran `/end`. If one small follow-up is still coming, do not `/end` yet — wrap once at the real stopping point (the mini-wrap below is for work that arrives *after* a wrap, not a licence to wrap early).

**Post-wrap work → mini-wrap (non-negotiable):** disposition/append ledger lines → ONE delta-only handoff line → CURRENT_STATE only if NEXT ACTION or build status changed → `Session followup:` commit, push per policy, clean tree. Never a second full re-summary.

---

## Hooks and scripts (wired in the project's `.claude/settings.json`)

| Hook | Script | Does |
|---|---|---|
| `SessionStart` (`startup\|resume\|clear`) | `session-start-context.py` | Worktree guard → global-install check → fetch + stale refusal → injects tracks, CURRENT_STATE, open ledger items (truncated, grouped by track), spine (bloat warning), last handoff lines (+ per track), template-drift note, cross-check / track-gate directive |
| `PostToolUse` (`Write\|Edit`) | `track-new-file.py` | Queues unindexed paths (skip prefixes from `protocol.json`) |
| `Stop` | `stop-clean-tree-check.py` | Blocks a stop only when a Session commit just landed and files this track is responsible for are still dirty |

Not hooks: `validate-index.py` (phantom rows, `/end` 1c), `scan-secrets.py` (content scan, `/end` 0c; `--history` audits everything pushable), `check-template-drift.py` (resync), `statusline.py` (prompt line). All scripts are silent on failure and never edited per project — `protocol.json` carries the differences.

---

## Why this file is short

A 300-line protocol gets skimmed. Under ~200 lines with numbered steps and one source of truth per fact gets followed. Brevity is a feature.
