# /end — Session End Protocol

Wrap up the development session cleanly. **Execute every step in order. Do not skip.** Applies only to repos with `.claude/protocol.json` (or `docs/CURRENT_STATE.md`); otherwise say so and stop.

Read `.claude/protocol.json` once at the top: `check_command`, `secret_scan`, `push_policy`, `ledger` caps, `file_caps`, `tracks`, `shared_paths`. In a multi-track repo, you declared your track at start; every step below is scoped to it.

**No new work during `/end`.** A user message that arrives mid-wrap is a note or a question: answer briefly or fold it into the docs; do not build.

## Step 0a — Worktree guard (FAIL FAST)

```bash
pwd
git rev-parse --abbrev-ref HEAD
```

If the cwd contains `.claude/worktrees/` OR the branch starts with `claude/`, **STOP**. Do not `/end` from a worktree — it would pollute the handoff log with a `claude/<name>` branch merge. Tell the user to quit without ending (work on disk is preserved) and restart in the main checkout via the CLI. Do not silently fast-forward `main` from a worktree branch.

## Step 0b — Clear phantom-dirty files

```bash
git update-index --really-refresh > /dev/null 2>&1 || true
```

Stale mtimes (a pull, an editor touching files) make git flag unchanged files as modified. This drops only entries byte-identical to HEAD.

## Step 0c — Project check + secret scan (FAIL FAST)

If `check_command` is set, run it (e.g. `pnpm check`: build freshness, contract drift, typecheck). **Non-zero exit → STOP.** Report the failure and fix it, or get an explicit override, before continuing. A tree that fails this guard has silent drift; do not commit and push it.

If `secret_scan` is true (default), run:

```bash
python .claude/scripts/scan-secrets.py
```

**Findings → STOP.** Do not commit. Move the value into an ignored file or a secret store, leave a `.example` sibling with the value blanked, rotate it if it was ever pushed, re-run until clean. `.gitignore` is a blocklist and only protects paths somebody remembered to list; this scan reads content. (Nested sub-repositories are invisible to it — run it inside them separately.)

## Step 0d — File caps + twins (the mechanical half of the size/DRY rule)

```bash
python .claude/scripts/check-file-caps.py
```

It reads the code files THIS session touched (commits since the last wrap + the working tree) against `file_caps` in `protocol.json`.

- **Over the hard cap (default 800) → STOP.** Split the file by a coherent concept now, or get an explicit override; never shave lines to pass.
- **Over the soft cap (default 500), or a new file that shares its name with an existing one → a `[ ]` ledger line per file, right now**, naming the split candidate or the twin (Step 1d will see it). The wrap RECORDS; the split happens at the next quiet point. Do not split during `/end`.
- The judgement half — is anything duplicated, should anything split — runs once per feature close, not per session (global `PROTOCOL.md` → "Feature close"). The mechanical check is what holds the line between those sittings.

## Step 1 — Verify pending index updates

Read `.claude/pending-index-updates.txt`.

- Missing or empty → Step 1b.
- Non-empty → for each path, add a one-line entry to `docs/CODEBASE_INDEX.md` saying what the file does in plain language. Then overwrite the pending file to be empty. **Do not proceed until done.**

## Step 1b — Backstop: diff-based index check

```bash
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

Ignore protocol bookkeeping (`.claude/`, `CODEBASE_INDEX.md`, `CURRENT_STATE.md`, `HANDOFF_LOG.md`, `SESSION_LEDGER.md`), build output, lockfiles, and the `index_skip_prefixes` from `protocol.json`. In a multi-track repo also ignore paths inside the OTHER track's owned paths (they are that session's to index). For each remaining path, check it appears verbatim in `docs/CODEBASE_INDEX.md`. If any are missing: report them (the hook may have failed), add the entries, and note in CURRENT_STATE's watch section that the hook missed N files.

## Step 1c — Phantom-row check

```bash
python .claude/scripts/validate-index.py
```

Remove any reported rows (index entries pointing at files no longer on disk).

## Step 1d — Reconcile `docs/SESSION_LEDGER.md`

Do this **before** writing CURRENT_STATE, so the wrap is written against the ledger rather than end-of-session recall (recall provably loses early-session facts to context compaction).

1. Read the ledger **from disk** (a concurrent session may have edited it).
2. Disposition every `[ ]` item this session touched: `[x]` + `→ DONE <date>: <one line>`, or `[-]` + reason. Untouched items stay `[ ]`. **Never strike an item you merely don't recognise.** Multi-track: only your prefix's lines, plus lines tagged for you or `→all` that you resolved (note "closed by <track>").
3. Append `[ ]` lines for anything this session queued or deferred that isn't captured — scan for "next session", "before release", "check later", riders, gates. Apply the worthiness test (open loop with a done-condition / not tracked elsewhere / can't be done in 10 minutes / one ID per loop). **The first line must be a self-contained TITLE** — it is the only part a future session sees in the manifest, so lead with the headline and put the detail on continuation lines. **There is no length cap**: keep the item whole, here. Multi-track: mint with your prefix; put `→<other track>` / `→all` right after the ID (`D-9 →mobile (2026-09-09) …`).
4. **MOVE** `[x]`/`[-]` lines dispositioned more than `ledger.move_closed_after_days` ago into `docs/SESSION_LEDGER_CLOSED.md` (create it if absent; append, never reorder). **Never delete them.** That file is never injected and may grow forever. An ID cited in a commit subject, a handoff entry or a spine cell has to stay resolvable — deleting its line leaves every citation pointing at nothing.
5. Count the open items. Over `open_soft_max` → **route or close the two oldest stale items now** (items past `stale_after_days`), proposing a disposition for each and letting the user rule. Two items, not a triage sitting: a level-based cap that has been exceeded for months is not a cap, and a rate you would not bother skipping is.

## Step 1e — `check-ledger-refs.py` (the copy-forward guard)

```bash
python .claude/scripts/check-ledger-refs.py
```

Every ledger ID cited in `CURRENT_STATE.md` and the spine, classified open / struck / absent. Read each **struck** line and decide: does it still describe the item as pending (fix it in Step 2), or as history (correct as written, leave it)? *Absent* means the line has moved to the closed file — informational, not a finding.

This exists because copy-forward is the default editing action: every wrap re-reads the file and rewrites the parts it was thinking about, so a line nobody was thinking about survives untouched. One real project's CURRENT_STATE cited 146 IDs and 65 were already struck. The `/start` cross-check cannot catch it — the documents agree with each other perfectly.

**Multi-track:** a stale line in another track's section is not yours to edit. Put it on the ledger tagged for that track.

## Step 2 — Reconcile the spine, then overwrite `docs/CURRENT_STATE.md`

**First, the source of truth.** If this session completed or started a phase/block or changed scope, update the status spine in `ROADMAP.md` (and the matching section header). **Never renumber** — a cut item stays a labeled gap. **Spine cells stay at-a-glance short:** a status marker, the gate holding it open, at most a pointer. Do not append session narrative into a cell — that history lives in `HANDOFF_LOG.md`; when a session materially advances an item, REPLACE the cell's summary.

**Then re-read `docs/CURRENT_STATE.md` from disk** before overwriting (`git log --oneline -2 -- docs/CURRENT_STATE.md`, or compare against the session-start copy). Concurrent sessions share the checkout; if another session wrapped mid-flight, fold its facts in rather than clobbering.

**Then** replace it. Single track — the whole file; multi-track — **only your track's sections and the Shared facts you changed** (the other track's sections are copied through verbatim).

**v2: this file is the state of the APP, not the state of the session.** The test for every line is *if we are on 1.0.1, what does that entail?* Required shape:

- **📍 NEXT ACTION** (one per track) — ONE unambiguous line matching the spine's CURRENT marker, **citing the ledger IDs it depends on** (those are the items the next session gets in full).
- **Shipped** — version per track, and where it is (released / in review / internal).
- **Build status** — working / broken / not yet tested, what was verified, on what, when.
- **Shared services** (multi-track or client+server) — deploy state both sides consume, stamped `(by <track>, <date>)`.
- **Active blockers**, and **Open loops** as a pointer to ledger IDs only.

**Not here:** session narrative (that is the handoff entry) · any ledger item's *status* (cite the ID) · a copy of the phase/block list (that is the spine) · a "things to watch" pile. On one project those turned this file into 92,000 characters, 63% of it a 30-session narrative, injected whole at every session start. Overwrite, do not append.

## Step 3 — Append one entry to `docs/HANDOFF_LOG.md`

Get the time with `date '+%Y-%m-%d %H:%M'`. Append at the bottom, in **I-PASS shape**:

```
## YYYY-MM-DD HH:MM | <track> | <Phase/Block or area>
**Status:** green | yellow | red — <what was verified, on what, when>
**Changed:** <the delta this session — NOT a re-summary of the project>
**Next:** <the first move, with enough context to make it>
**If it fails:** <the contingency — what to try, or what it would mean>
**Confirm:** <the one thing the next session must restate before starting>
```

Single-track repos drop the `<track>` field.

**No length cap** — only this entry is injected next session, so it can be as long as the next session needs. But keep it to the **delta**: the reader has CURRENT_STATE, and a meta-analysis of 1,590 handovers found *excessive non-essential information* among the leading causes of the omissions handovers exist to prevent.

**If it fails** and **Confirm** are not optional. They are the two elements the handover literature finds missing most often, and they are what turn a summary into something the next session can act on when the happy path does not happen. If you cannot write **Confirm**, the entry is not finished.

A post-`/end` mini-wrap appends an entry covering ONLY the delta since the previous one.

## Step 3b — Payload budget

```bash
python .claude/scripts/check-payload-budget.py
```

Reports the assembled session-start payload against `payload.target_chars`. Over budget → **shrink the largest contributor, never raise the budget.** The budget is the only cap that stays honest when mass moves between documents; raising it is how the last one failed.

## Step 4 — Commit and push

`git status` to confirm what changed. Stage **explicit paths** — never `git add -A` / `git add .`:

- `docs/CURRENT_STATE.md`, `docs/HANDOFF_LOG.md`, `docs/SESSION_LEDGER.md`, `docs/CODEBASE_INDEX.md` (if updated), `ROADMAP.md` (if the spine changed)
- Any other files the user confirmed should be committed — in a multi-track repo, only files inside your owned paths or the shared paths.

Commit message: `Session: <one-line summary>` — multi-track: `Session (<track>): <summary>`.

Push per `push_policy`: `standing` → push now (the authorisation is recorded in DECISIONS.md); `ask` → ask first. **Force pushes always need explicit per-instance confirmation.** If a push is rejected, report it and let the user decide; never retry destructively.

**Multi-track:** before pushing, run `git log origin/main..HEAD` and name in the report any commit that is not yours — a push publishes the whole branch. If the user has said the other track's commits are not ready, do not push.

### Step 4a — Clean-tree guarantee (non-negotiable)

After the commit, `git status --porcelain`. For each remaining entry:

1. **Real in-scope work this session touched** → second commit `Session followup: <summary>` (with `(<track>)`), push again per policy.
2. **The other track's files** (multi-track; inside its owned paths, or in shared paths where the user has said they belong to that session) → leave them, and say so explicitly in the report.
3. **Out-of-scope work the user hasn't reviewed** → STOP and ask: commit, stash, or discard?
4. **Unknown** → treat as 3. Ask.

The only acceptable exit state: every remaining dirty path is accounted for in the report. The Stop hook enforces this.

### Step 4b — Confirm the mainline is published

```bash
git fetch origin main
git rev-parse HEAD
git rev-parse origin/main
```

If a push was made, both must match; if they differ, the push didn't land — report it, do not force. If policy was `ask` and the user declined, note that the remote is behind.

## Step 5 — Report

1. What was accomplished this session (track named)
2. What's next
3. Anything to watch for next session (incl. the other track's files left in the tree, and any commits of theirs your push carried)
4. Open ledger items: N (IDs that gate the next action; count vs soft max; stale items listed)

## After `/end` — the mini-wrap rule

Work regularly continues after a completed `/end`. It must close with a **mini-wrap**: disposition/append ledger lines → ONE delta-only handoff line → CURRENT_STATE only if NEXT ACTION or build status changed → `Session followup:` commit, push per policy, clean tree. Never a second full re-summary — that is how work gets recorded twice.
