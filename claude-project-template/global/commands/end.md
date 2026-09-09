# /end — Session End Protocol

Wrap up the development session cleanly. **Execute every step in order. Do not skip.** Applies only to repos with `.claude/protocol.json` (or `docs/CURRENT_STATE.md`); otherwise say so and stop.

Read `.claude/protocol.json` once at the top: `check_command`, `secret_scan`, `push_policy`, `ledger` caps, `tracks`, `shared_paths`. In a multi-track repo, you declared your track at start; every step below is scoped to it.

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
3. Append `[ ]` lines for anything this session queued or deferred that isn't captured — scan for "next session", "before release", "check later", riders, gates. Apply the worthiness test (open loop with a done-condition / not tracked elsewhere / can't be done in 10 minutes / one ID per loop) and the size cap: an item over `ledger.item_max_chars` gets shortened, its analysis moved to a bug entry, backlog entry, `docs/notes/<ID>.md`, or DECISIONS entry, and a pointer left behind. Multi-track: mint with your prefix; put `→<other track>` / `→all` right after the ID when someone else acts on it (`D-9 →mobile (2026-09-09) …`).
4. Prune `[x]`/`[-]` lines dispositioned more than `prune_closed_after_days` ago (history lives in git).
5. Count the open items. Over `open_soft_max` → say so in the report and offer a triage pass. List items older than `stale_after_days` as route-or-close (the user decides in a batch; do not close them yourself).

## Step 2 — Reconcile the spine, then overwrite `docs/CURRENT_STATE.md`

**First, the source of truth.** If this session completed or started a phase/block or changed scope, update the status spine in `ROADMAP.md` (and the matching section header). **Never renumber** — a cut item stays a labeled gap. **Spine cells stay at-a-glance short:** a status marker, the gate holding it open, at most a pointer. Do not append session narrative into a cell — that history lives in `HANDOFF_LOG.md`; when a session materially advances an item, REPLACE the cell's summary.

**Then re-read `docs/CURRENT_STATE.md` from disk** before overwriting (`git log --oneline -2 -- docs/CURRENT_STATE.md`, or compare against the session-start copy). Concurrent sessions share the checkout; if another session wrapped mid-flight, fold its facts in rather than clobbering.

**Then** replace it. Single track — the whole file; multi-track — **only your track's sections and the Shared facts you changed** (the other track's sections are copied through verbatim). Required shape:

- **📍 NEXT ACTION** (one per track) — ONE unambiguous line matching the spine's CURRENT marker. Session start reports it verbatim.
- **Shared** (multi-track) — deploy state of shared services, schema/migration version, anything both tracks consume, each stamped `(by <track>, <date>)`.
- Build status: working / broken / not yet tested (per track).
- Optional loose ends — **point at open ledger IDs**; no separate prose list (regenerated prose silently drops items). Clearly marked as NOT the next step.
- Last things accomplished this session (your track).
- Active blockers + things to watch.

**Do NOT keep a copy of the phase/block-status list here** — point at the spine. Overwrite, do not append.

## Step 3 — Append one line to `docs/HANDOFF_LOG.md`

Get the time with `date '+%Y-%m-%d %H:%M'`. Append at the bottom:

```
YYYY-MM-DD HH:MM | <Phase/Block name or area> | <one-line summary incl. "Next:"> | <build status>
```

Multi-track repos add the track as the second field:

```
YYYY-MM-DD HH:MM | <track> | <Phase/Block name or area> | <summary incl. "Next:"> | <build status>
```

**Summary hard cap ~300 characters** — it is a scannable index entry; fact-grade detail belongs in the ledger and CURRENT_STATE. A post-`/end` mini-wrap line covers ONLY the delta since the previous wrap line.

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
