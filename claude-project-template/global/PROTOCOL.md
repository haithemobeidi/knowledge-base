# Session Protocol (global)

**Applies to any repo that carries `.claude/protocol.json`.** If the repo you are in has no such file:

- It has its own `PROTOCOL.md` at the root → it is a **not-yet-migrated** protocol project. **Its own `PROTOCOL.md` and its own `/start` / `/end` commands win**; ignore this file (the global work style still applies). Mention once that `MIGRATION.md` in the template brings it onto this layer.
- Otherwise this protocol is off: ignore it entirely and work normally.

**"Integrate the protocol"** (also: "set up / sync / update the protocol", "bring this project onto the template") is the one request that applies in ANY repo, including one where this protocol is off. Do it start to finish; the user should not have to name a single command:

1. **This machine first.** `git pull --ff-only` in the Knowledge Base clone (path at the top of `~/.claude/CLAUDE.md`), then `python "<KB>/claude-project-template/install-global.py"`. If it copied anything, say that open sessions pick it up after a restart, and carry on.
2. **Then this project, by what it is:**
   - has `.claude/protocol.json` → it is on the template: follow `<KB>/claude-project-template/README.md` → "Rolling out a template change" (check drift, `--sync`, `--adopt` if needed, the "Left for you" lines, the budget check, commit).
   - has its own root `PROTOCOL.md` or older start/end commands → `<KB>/claude-project-template/MIGRATION.md` from §0.
   - has neither → `README.md` → "Bootstrap a new project (agent procedure)".
3. **Ask only what is the user's to decide** — which paths each track owns, the check command, the push policy, anything a doc marks as a ruling — as one batch of questions, with a recommended answer for each. Everything mechanical, just do.
4. **Never while another session is open in the same checkout, and never mid-work or mid-wrap.** If either is true, say so and stop.
5. **Finish with a short report:** what changed, the payload size against its budget, anything left for the user, and what to look for in the next fresh session (the newest `MIGRATION.md` section says).

This file is the **single source of truth** for how sessions start, run, and end. It is imported from `~/.claude/CLAUDE.md` on every machine (see "Layering") and is never copied into a project. The step-by-step procedures live in the `/start` and `/end` commands; this file holds the rules. The measured failure behind each rule, with its numbers, is in the template's `DESIGN.md` → "The protocol's evidence, in full".

---

## Why this exists

Every rule here traces to a measured failure on a real project. The general lessons (the sections below are what each one became):

1. **A step with a discretionary skip clause is not a step.**
2. **Overlapping protocol documents drift apart** — one protocol, one copy, imported everywhere.
3. **Heavy end-session ceremony gets skipped** — automation does the reading; the human sees a short report.
4. **End-of-session recall loses facts** — record at the moment of the event.
5. **Concurrent sessions collide** unless tracks, ID prefixes and ownership are declared.
6. **The ledger grew into what it was meant to prevent** — inject titles, read items on demand.
7. **Capping one document moves the mass to another** — measure the total the consumer receives, not the inputs feeding it.
8. **A stale document cannot be caught by comparing it to other documents** — stale documents agree with each other perfectly.
9. **A budget is only as real as the channel it travels through** — measure what arrives, not only what is sent.
10. **A check that cannot fail is a notice.**
11. **A ceiling stops growth; it does not make anything shrink** — anything every reader pays for needs an exit, or it only accumulates.

---

## Which shape is this project on? Read `protocol_version` before anything else

This file is imported live from the Knowledge Base, so it always describes the **newest** shape. A project only follows it once its documents have been migrated. `.claude/protocol.json` → `protocol_version` says which:

| | `protocol_version: 1` (or absent) | `protocol_version: 2` |
|---|---|---|
| CURRENT_STATE | rolling snapshot, injected whole | the state of the **app**, no narrative |
| Ledger at start | every open item's text, truncated at 600 chars | a **manifest** of titles + full text for cited items |
| Handoff | one ~300-char line; last 5 injected | an **I-PASS entry**; only the newest per track injected |
| Closed lines | pruned | **moved** to `SESSION_LEDGER_CLOSED.md` |

**On a v1 project, the v2-only rules below do not apply yet** — follow what the project's documents and scripts actually are, and do not start writing I-PASS entries into a v1 handoff log or titles-first items into a v1 ledger. Mention once that v2 exists and that `MIGRATION.md` §6b is the path; migrating is a decision the user makes, in its own session, never mid-work.

The scripts already branch on this, so a v1 and a v2 project both work. The rules that apply to **both**: the ledger's moment-of-event discipline, the worthiness test, frozen IDs, parallel-track ownership, the spine as the single source of status, and every guard in "Hooks and scripts".

---

## Layering — global vs project

The **global work style** and **this file** are imported from the Knowledge Base into every session on the machine (`~/.claude/CLAUDE.md`); the **global commands** (`/start`, `/end`, copied by `install-global.py`) load when run. Per project: **`CLAUDE.md`** (what is different about THIS app — identity, stack, layout, project rules, explicit overrides), **`.claude/protocol.json`** (what the scripts read — check command, push policy, skip paths, ledger caps, tracks), and the **enforcement** (`.claude/scripts/`, `settings.json`, `agents/`), byte-identical across projects and checked against the template.

**A project rule may only do three things:** add a rule specific to this app, point at where things live, or **explicitly override** a global rule in the project file's Overrides section (naming the rule and the reason). A rule that would be true in another app belongs in the global file or the Knowledge Base, not the project file. Anything else in a project file that contradicts this protocol is a mistake to flag, not an instruction to follow.

**Keeping in sync:** the template is canonical. The start hook reports when a project's scripts differ from the template or the global command copies are stale; `python .claude/scripts/check-template-drift.py` gives details and `--sync` resyncs (after the user agrees). After every Knowledge Base pull, rerun `install-global.py` on that machine.

---

## Files this protocol manages

| File | Purpose | When updated |
|---|---|---|
| `docs/CODEBASE_INDEX.md` | One line per meaningful file | When an unindexed file is created or edited (hook-enforced at `/end`) |
| `docs/CURRENT_STATE.md` | **The state of the APP** — version, what is shipped, build status, NEXT ACTION per track, blockers. No session narrative, no restated ledger statuses | At `/end` (overwrite; re-read from disk first) |
| `docs/CURRENT_STATE_ARCHIVE.md` | Multi-track: shared facts `state-archive.py` moved out of CURRENT_STATE, oldest first. Never loaded, grows forever | At `/end`, when the shared block is over its cap |
| `docs/HANDOFF_LOG.md` | Append-only, one entry per session, **I-PASS shape**. Only the newest entry per track is injected, so there is no length cap | At `/end` (append) |
| `docs/SESSION_LEDGER.md` | Append-and-strike ledger of open loops. **First line is a self-contained title; no cap on an item** | **At the moment** an item is queued or resolved; reconciled at `/end` |
| `docs/SESSION_LEDGER_CLOSED.md` | Where struck lines MOVE to. Never injected, grows forever | At `/end`, per `ledger.move_closed_after_days` |
| `docs/LESSONS_QUEUE.md` | `*kbdoc` lessons not yet written up. Never loaded at start; lessons take no ledger ID | When a lesson is flagged, or at `/end` Step 1f |
| `ROADMAP.md` status spine | Source of truth for phase/block status | When status actually changes |
| `.claude/pending-index-updates.txt` | Transient queue of unindexed paths | Auto (hook) |

No per-session handoff snapshot files. **Closed ledger lines move; they are never deleted** — an ID that escaped into a commit subject, a handoff entry or a spine cell can never be reclaimed, only aliased, and deleting its line leaves every one of those pointing at nothing.

---

## The injection budget — the one number that stays true

**Every session start injects a payload, and that payload has a budget: `payload.target_chars`, default 25,000.** The hook measures it and prints the size. It is the only cap that measures what the model actually receives, so it stays honest when the mass moves from one document to another. **Over budget → shrink the contributor; never raise the budget.**

**Delivery:** Claude Code caps one hook string at 10,000 characters (anything longer arrives as a 2,000-character preview the model is not asked to read), so the hook emits the payload as labelled **parts** — read all of them; they arrive in any order. After a compaction only a slim rules reminder is re-injected: the project `CLAUDE.md` comes back by itself, the state docs do not.

**The budget is a gate, not a report.** `/end` runs `check-payload-budget.py --strict --ratchet`; a wrap that leaves a payload over its **limit** stops before the commit. The limit is the budget, or — for a payload already over it when the gate arrived — a **ceiling** in `payload.ceiling_chars`, which only moves down: every smaller wrap lowers it, it is removed once the payload is inside the budget, no script raises it. An over-budget project can wrap; it cannot grow. The ceiling sits 500–1,000 characters above the payload, so past it a wrap that opens a ledger item closes or routes one. Raising `target_chars` or a ceiling is the user's decision, recorded in DECISIONS.md.

**A multi-track session loads its own track** (v2, two or more tracks). The hook injects only the **core** (sync result, track list, directive); once the track is known, `python .claude/scripts/session-start-context.py --track <name>` prints that track's NEXT ACTION, the CURRENT_STATE that is not another track's section or bullet, the ledger items tagged for it, `→all` or unassigned, the spine, and its newest handoff entry. Budget and limit are **per track**. An item tagged `→all` is in every track's payload — tag for the tracks that act on it, not for visibility.

**What every track loads has an exit** (multi-track v2). Outside the NEXT ACTION sections, a bullet that is one track's state starts with its tag (`- →android **Android 1.3.0 — in review** …`) and only that track loads it. The untagged bullets may total `state.shared_max_chars` (5,000); `/end` runs `state-archive.py`, which moves the oldest (by the newest date in each; undated counts as oldest) to `docs/CURRENT_STATE_ARCHIVE.md` until the rest fits. A fact every track still needs goes back with today's stamp, shorter; a ruling lives in DECISIONS.md and the NEXT ACTION of the tracks it constrains. Never counted or moved: blocker sections, and Shipped / Build status (`state.never_move`) — tag their rows instead.

What is injected (single-track) or loaded by track (multi-track), and what is not:

- **Injected:** CURRENT_STATE whole (it is small by construction) · a **manifest** of every open ledger item, one line each as `ID →tag (date) TITLE` (the provenance parenthetical is never shown — the title is) · the **full text, capped at `gating_item_max_chars`,** of the items each track's NEXT ACTION section cites (`max_gating_items` per section) · the spine · your track's newest handoff entry · the directive.
- **Not injected, read on demand:** every other ledger item (grep its ID) · closed items · parked items (counted by the event they wait on) · older handoff entries · CODEBASE_INDEX · the lessons queue · the CURRENT_STATE archive · notes, bug and backlog docs · in a multi-track repo, the other tracks' NEXT ACTION sections, bullets, items and handoff entries.

A document that is never injected is free and may grow without limit. That is why nothing needs to be summarized or deleted to stay in budget.

---

## Where-are-we: one source of truth, frozen numbers

The **"status at a glance" spine table in `ROADMAP.md`** is the sole answer to "where does the project stand?" (heading configurable via `spine_heading`). `CURRENT_STATE.md` points at it and never keeps its own copy of the list. Two docs answering the same question is the most reliable way to drift a project.

**Numbers are frozen.** Identity is the name; the number is a permanent label. A cut item stays as a labeled gap, never reused, never resequenced.

**Spine cells stay short:** a status marker, the gate holding the item open, at most a pointer. Session history goes to `HANDOFF_LOG.md`; the hook warns at 1,500 characters.

**The spine never names next work.** What a track does next, and what gates its next release, live in CURRENT_STATE's NEXT ACTION and nowhere else; a spine cell that copies them goes stale the first time a mini-wrap changes the NEXT ACTION, because a mini-wrap does not touch the spine.

---

## Session start

Mostly automatic: the `SessionStart` hook runs the guards, fetches origin, and injects the state docs plus the cross-check directive — as several labelled parts; read all of them. `/start` holds the full step list, for when the hook did not fire. Never skipped, whether or not the directive repeats them:

- **Fetch before reading any doc** (behind + clean → `git pull --ff-only`; behind + dirty, or diverged → stop and surface; offline → say currency is unverified). `git status` saying "up to date" without a fetch proves nothing; a stale checkout looks complete, not broken. Never work from `.claude/worktrees/`, a `claude/*` branch, or a `protected_branches` branch. A fork's `upstream_ref` drift is reported, never acted on at start — catching up is a session decision at a quiet point.
- **Multi-track: know your track** before reading or editing anything. When the hook's directive says the repo loads by track (v2, synced), load it with the one `--track` command, never by reading the state docs whole; otherwise the hook injected everything and you read it as it is.
- **Working tree:** `git status` after reading — changes that survive `git update-index --really-refresh` mean the last `/end` did not reach a clean tree; surface them (multi-track: name another track's as theirs). Run `audit_command` if the project sets one.
- **CROSS-CHECK:** NEXT ACTION vs spine CURRENT vs the handoff's "Next:" vs open gates — a contradiction → stop and surface; never pick one silently. **ACCEPT:** stale documents agree perfectly, so also **restate the NEXT ACTION in your own words and name what would make it wrong**; a handoff that cannot support that is reported as insufficient.
- **Report:** track (if any) / where we are (name + number) / last session's result / the NEXT ACTION as restated / open items with gates / your calls (the `DECIDE:` items, if any) / sync line / payload size against budget.

---

## During the session

**Code quality** (stack-specific rules live in the project file; these hold everywhere): files do one thing, 500-line soft cap and 800 hard, propose splits before 500; DRY at 3+ uses (2 only when the shape is certain AND drift has real cost — when the abstraction might be wrong, duplication is cheaper than the wrong abstraction); group by feature, not by type — no `utils/` or `helpers/` dumping grounds; comments explain why; no premature abstractions.

**Feature close — the judgement half of the size/DRY rule** (`/end`'s file caps are the mechanical half). ONCE PER FEATURE, when its ledger item closes and the shape is settled: read the feature's files for reuse, duplication and extraction, put every split or dedupe on the ledger as its own line with the concept named, and do them at a quiet point — never inside the wrap, never per session (that is the reshuffle-for-feel audit the work style forbids). (User ruling 2026-09-17.)

**Git:** commit each verified pause-point, never one big wrap commit. Never commit without the user confirming the feature works. Push per `push_policy` (`ask` unless the project set `standing` and recorded it in DECISIONS.md). Stage explicit paths — never `git add -A`.

**Codebase index:** the hook queues any unindexed file you Write or Edit; `/end` cannot complete while the queue is non-empty. Descriptions go in the index, not in file headers.

**Narrative docs only at `/end`:** CURRENT_STATE, HANDOFF_LOG, CODEBASE_INDEX. Pause-point feedback reframes work; mid-session doc edits get rewritten and pollute history.

**The ledger at the moment of the event** — the scoped exception:
- The moment work is queued or deferred ("next session", "before release", "check later", a rider, a gate) → append a `[ ]` line right then.
- The moment it resolves → strike right then: `[x]` + `→ DONE <date>: <one line>`, or `[-]` + reason.
- **Worthiness — all four must hold for a line to earn an ID:** (1) it is an open loop a future session must act on, with a concrete done-condition; (2) it is not tracked elsewhere (bugs → the bug doc, deferred features and ideas → the backlog, status → the spine, **lessons → `docs/LESSONS_QUEUE.md`**, a standing fact or a ruling already made → DECISIONS.md or CURRENT_STATE); (3) it cannot just be done now (under ~10 minutes ⇒ do it); (4) one ID per loop — sub-facts ride the parent. What fails the test is routed to where it belongs, not minted.
- **An item that waits on the user's ruling starts its title with `DECIDE:`.** It is still an open loop, but no session can close it by working. Session start lists those first, as the user's calls, and the report names them.
- **An item no session can act on until a named event is PARKED:** `[~]` plus a line `→ PARKED <date> until <event>` (`ledger-archive.py --park <IDs> --until "<event>"` writes both). Session start counts parked items by their event instead of listing them; when the event happens, the session that sees it unparks them (`--unpark`). A parked item the NEXT ACTION cites, or a `DECIDE:` item, is still listed. Parking without an event stops the wrap: an item that waits on nothing in particular is a deletion that looks like a deferral.
- **The first line is a self-contained TITLE.** Session start injects a manifest built from first lines, so a future session decides whether to open an item from that line alone. Lead with the headline; analysis goes on continuation lines. This is the rule the whole budget rests on.
- **No cap on an item.** Items stay whole, here, forever — nothing is shortened, summarized or moved to a side file; the manifest protects the budget. Manifest line → whole item, never a third hop.
- **Count (soft):** over `open_soft_max` (default 30; parked items do not count), `/end` routes, parks or closes **the two oldest stale items** — a rate, not a sitting.
- Never strike a line you merely don't recognise; never renumber; IDs are permanent.
- **Citations are provenance, not resolution.** Items record where they came from (`from D-4 Pause D`, `user mid-M-9 Pause B`) and what they wait on (`After M-35`). A cited item closing does NOT close the citing item — a child is spun out precisely so it outlives its parent. Only the done-condition closes an item.

**Check stale messages before re-changing:** after a fix lands, confirm the issue is still current before changing the code again — the user may have queued the message before testing.

---

## Parallel tracks — two versions of the app, two sessions, one checkout

Declared in `protocol.json` → `tracks` (name, ID prefix, owned paths) and `shared_paths`. With fewer than two tracks none of this applies. With two or more:

1. **Declare your track before anything else.** From the user's first message if it names it; otherwise ask and wait. The report's first line is `Track: <name>`. Commit subjects carry it: `Session (desktop): …`, `Session followup (mobile): …`.
2. **IDs are prefixed per track and counters are independent.** Desktop mints `D-1, D-2…`, mobile `M-1, M-2…`. Legacy unprefixed IDs stay as they are forever (frozen references). The prefix says who wrote it; a tag `→<track>` **right after the ID** (`M-3 →desktop (2026-09-09) …`; also accepted after the date) says who acts on it — `ledger-archive.py --retag <IDs> --to <track>` hands items over. Legacy unprefixed items get that tag once, at migration, so they scope to a track without renumbering. If a collision ever happens anyway: renumber the later-referenced item and keep the alias in the surviving line.
3. **Ownership.** Edit only your track's owned paths and the shared paths. Never edit the other track's owned paths, its ledger lines, or its section of CURRENT_STATE. You may strike a line tagged for you or `→all` that you resolved (note "closed by <track>").
4. **Shared paths: one owner, and only who must act.** A shared-path change another track must ACT on (rebuild, redeploy, run a migration) gets a ledger line tagged for exactly those tracks, by name (`→desktop/ios`). A change nobody must act on is a stamped fact in CURRENT_STATE's Shared block, not an item. An open problem found on a shared path (an advisory, a warning, a shared script's bug) gets ONE owner — `protocol.json` → `shared_owner`, else the track that will fix it. New items are not tagged `→all`; the `/end` gate stops a wrap that adds one (naming every track is allowed — it has to be deliberate).
5. **The tree is not yours alone.** The other session's uncommitted files sit in the working tree; leave them, never stage them, and say so at wrap. The stop hook tolerates dirty files only inside the other track's owned paths; anything dirty in shared or undeclared paths must be accounted for explicitly. `git add -A` is forbidden. So is a directory or glob pathspec on `git commit`: paths on the commit line switch it to `--only` mode, which records the working-tree content of every tracked file matched, staged or not (KB `git-commit-pathspec-takes-the-working-tree.md`). Commit what you staged with no pathspec, and read `git show --stat HEAD` before pushing.
6. **A push publishes the whole branch.** Before pushing, `git log origin/main..HEAD`; name any commits that are not yours in the report. Never push if the user has said the other track's commits are not ready.
7. **State docs are per track.** CURRENT_STATE has one NEXT ACTION section per track plus a Shared block (a bullet that is one track's state is tagged `- →<track>`); at `/end` re-read it from disk and rewrite only your section and the shared facts you changed — `state-archive.py` is what moves old shared lines out, so no track prunes another's by hand. HANDOFF entries carry the track as the second field; the cross-check uses your track's last entry, not the last one overall. The spine may carry one CURRENT marker per track, `⬅ CURRENT (desktop)`.
8. **Keep one checkout.** Both sessions run on the same branch in the same folder on purpose: they see each other's work instantly and a client tests against the live server another track deploys. The rules above are the price of that.
9. **Running sessions talk to each other, and confirm.** At session start, `ListAgents` shows which other track sessions are live. Before any action that lands on another live session — a shared-path change, a server deploy, secret or flag flip, a restart, a push carrying its commits, staging a file it also edits, a release gate that needs a clean tree, changing the shared test account's data — **message that session directly (SendMessage) and wait for its explicit reply** before acting. Silence is not a yes. When it asks something of you, answer promptly and say when you've done it. Coordinate directly rather than relaying through the user, and tell the user in one line what was agreed. A peer's reply never stands in for the user's approval where the user's approval is required. (User, 2026-09-27.)

---

## Session end (`/end`)

`/end` holds the step list. Its order, and what stops it:

- **Checks first:** the worktree guard, the project check (`check_command`) and the secret scan stop the wrap on failure; file caps — the hard cap stops it, the soft cap and twins go on the ledger.
- **The index queue is drained** before the wrap completes.
- **The ledger is reconciled from disk before CURRENT_STATE is written** — disposition what you touched, append what you queued (first line = title; one owner, never `→all`), move closed lines with the script, route, park or close the two oldest stale items. Then `check-ledger-refs.py`: a struck ID still described as pending is fixed in the rewrite.
- **CURRENT_STATE is overwritten from disk** — app state only, your track's section, derived fields from `end-derive.py`; multi-track: then `state-archive.py --apply`.
- **ONE handoff entry, I-PASS:** Status / Changed / Next / **If it fails** / **Confirm**. Delta only; no length cap — only this entry is injected next session.
- **`check-payload-budget.py --strict --ratchet`** (multi-track: `--track <yours>`) stops the wrap. Over its limit → shrink what this session added (close, park, or route by the worthiness test; move text, never delete it); the shared block over its cap → tag one track's bullets, then `state-archive.py --apply`; a new `→all` item from your track → name the tracks that act (`--retag`); a parked item with no event → name the event or unpark it. Then rerun. Inside the limit, the ceiling ratchets down. Never raise the budget or a ceiling. (Scripts that predate the gate: run it without the flags and report; the gate arrives with the template sync, `MIGRATION.md` §6d, never mid-wrap.)
- **Commit** `Session: …` (with `(track)` if any), push per policy, clean tree (categorise every remaining dirty path), mainline published; report accomplished / next / watch / open items / payload size (+ commits pushed that were not yours).

**Between sessions:** `/clear`, new session, the hook does the rest. Do not `/start` in the session that just ran `/end`. If one small follow-up is still coming, do not `/end` yet — wrap once at the real stopping point (the mini-wrap is for work that arrives *after* a wrap, not a licence to wrap early).

**Post-wrap work → mini-wrap (non-negotiable):** disposition/append ledger lines → ONE delta-only handoff line → CURRENT_STATE only if NEXT ACTION or build status changed (and if the NEXT ACTION changed, check your track's spine cell does not restate it) → `Session followup:` commit, push per policy, clean tree. Never a second full re-summary.

---

## Hooks and scripts

Hooks (`.claude/settings.json`): `SessionStart` → `session-start-context.py` (guards, fetch, the payload in parts; `--track <name>` prints a track's load; `compact` → `--slim`, the rules after a compaction) · `PostToolUse` → `track-new-file.py` (queues unindexed files, after shell calls too) · `Stop` → `stop-clean-tree-check.py` (no stop with this track's files dirty after a Session commit).

Scripts `/end` runs, or you run by hand: `validate-index.py` · `scan-secrets.py` · `check-file-caps.py` · `check-ledger-refs.py` · `check-payload-budget.py` · `ledger-archive.py` (closed lines out; `--park` / `--unpark` / `--parked`; `--retag <IDs> --to <track>`) · `state-archive.py` · `end-derive.py` · `check-template-drift.py` (fetches the KB clone first; `--sync`) · `statusline.py`. Each one's docstring says what it does. All are silent on failure and never edited per project — `protocol.json` carries the differences.

**Validating a check:** never against this template — its state docs are placeholders, so a check run there examines an empty set and goes green forever. Validate against a real project's real documents, and make the check fail on purpose once before trusting it.

---

## Why this file is short

Every session on every machine loads this file whole — in every project, protocol or not — so its length is paid in every session, the way a start payload is. Keep it to the rules a session must apply without having run a command: procedures go in `/start` and `/end`, evidence and numbers in `DESIGN.md`, script detail in the scripts. Measure it in bytes (`wc -c`), not lines — one line here can be a paragraph. **Ceiling: its size on 2026-11-18, about 29,000 bytes.** Like a payload ceiling it only moves down: a new rule moves something out (to `/start`, `/end`, `DESIGN.md` or a docstring) or replaces an old one.
