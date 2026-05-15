# <ProjectName> — Session Protocol

This is the **single source of truth** for how Claude Code sessions work in this project. `CLAUDE.md` references this file — do not duplicate session rules elsewhere.

## Why this exists

Past projects hit three problems:

1. **Codebase index drifted silently** because updating it relied on agent discipline at the worst possible moment (end of session, context full, user impatient). Loopholes like *"skip if no major changes"* were taken even when major changes existed.
2. **Multiple overlapping protocol documents** drifted apart over time.
3. **Heavy end-session ceremony** made the protocol too expensive to follow consistently. Steps got skipped.

This protocol fixes all three with **automation, single source of truth, and minimum ceremony**.

---

## Files this protocol manages

| File | Purpose | When updated |
|---|---|---|
| `docs/CODEBASE_INDEX.md` | What every meaningful file in the project does | Whenever a new file is created (enforced by hook) |
| `docs/CURRENT_STATE.md` | Latest project state — overwritten each session | At session end |
| `docs/HANDOFF_LOG.md` | Append-only one-line session history | At session end |
| `.claude/pending-index-updates.txt` | Transient list of files needing index entries | Auto-managed by `PostToolUse` hook |

**Why no per-session handoff snapshot files?** Past projects accumulated 30+ of them and nobody read past the most recent one. Replaced with one rolling state doc + an append-only one-line log. Same information value, no noise, no drift.

---

## Session Start Protocol

**Mostly automatic.** A `SessionStart` hook (`.claude/scripts/session-start-context.py`) runs the worktree guard and injects `CURRENT_STATE.md` + the last 5 lines of `HANDOFF_LOG.md` at the top of the first turn. So Claude can give the 3-line status report without the user typing `/start`.

The user can still type `/start` explicitly to force the full protocol (e.g. after the hook fails). When they do — or when they say "start session" — execute these steps in order:

1. **Worktree guard first** — if cwd contains `.claude/worktrees/` OR the branch starts with `claude/`, STOP and tell the user. Do not proceed with any other steps. (See `.claude/commands/start.md` for the exact verbatim message.) The SessionStart hook also catches this, but typing `/start` re-runs the check.
2. If `CURRENT_STATE.md` and the last 5 handoff lines are NOT already in context (the SessionStart hook would have injected them), read them now.
3. Run `git update-index --really-refresh` (clears phantom-dirty stat entries), then `git status` and `git log --oneline -5`. If `git status` still shows changes after the refresh, those are real and must be surfaced to the user — they indicate the previous `/end` did not achieve a clean tree, which is a protocol violation worth flagging.
4. **Security audit on session start.** Run the package-manager's audit command for the project's primary lockfile (`pnpm audit --prod`, `npm audit`, `cargo audit`, etc.). Report only if non-zero findings — silent on green. Catches supply-chain regressions before they ride into the next session's work.
5. Read `ROADMAP.md` only if you need context on the current phase.
6. Report a 3-line status to the user:
   - Current phase / sub-phase
   - What was accomplished last session
   - What's blocking, or what's next

**Do not** read every handoff or every doc. `CURRENT_STATE.md` is the source of truth. If it's wrong, fix it — don't work around it.

---

## During-Session Rules

### Code quality (non-negotiable, also in CLAUDE.md)
- Files: 500-line soft cap, 800-line hard cap. Propose splits before passing 500.
- No DRY violations. 3+ uses = extract by default; extract at 2 uses when shape is certain AND drift has real cost.
- No `utils/` or `helpers/` dumping grounds. Organize by feature.
- TypeScript strict, no `any` without justification.
- Zod at every boundary.
- Comments explain *why*, not *what*.

### Git
- Commit working features incrementally — never let changes pile up across sessions.
- Never commit without explicit user confirmation that the feature works.
- Never push without explicit user request (see `/end` Step 4 for the standing end-session authorization).

### Codebase index discipline (enforced by hook)
- Every time you `Write` or `Edit` a file whose path is **not yet in `docs/CODEBASE_INDEX.md`**, a `PostToolUse` hook appends the path to `.claude/pending-index-updates.txt`. Already-indexed files are ignored, so editing existing files never re-queues them.
- The `/end` command **cannot complete** while that file is non-empty.
- This replaces the discipline-based approach that failed in past projects.

### Docs updates: at `/end` only, never mid-session
- `docs/CODEBASE_INDEX.md`, `docs/CURRENT_STATE.md`, and `docs/HANDOFF_LOG.md` get refreshed at `/end`. Do NOT edit them mid-session.
- **Why:** pause-point feedback during a session can reframe the work (a bug surfaces, scope shifts, a feature gets split into two phases). Doc edits made mid-session get rewritten by the time `/end` lands, and the intermediate version pollutes git history.
- The hook still queues new-file pending entries mid-session — that's the bookkeeping mechanism, not user-facing docs.

### Check stale messages before re-changing
- After a fix lands, ask the user whether the issue is still happening before changing the code again.
- **Why:** the user may have queued a follow-up message before testing your previous fix. Acting on the queued message blindly re-changes code that's already correct. Confirm the issue is current before iterating.
- Phrasing: "Just confirming — does it still <repro>? Or was that an earlier observation before the last fix landed?"

---

## Session End Protocol

Triggered when the user types `/end`, says "end session," or asks to wrap up.

### Step 0 — Worktree guard + phantom-dirty refresh

Same worktree guard as `/start`. Then run `git update-index --really-refresh > /dev/null 2>&1 || true` so subsequent `git status` calls see an honest tree.

### Step 1 — Verify pending index updates

Read `.claude/pending-index-updates.txt`.

- If empty, proceed to Step 1b.
- If non-empty: for each path listed, add a one-line entry to `docs/CODEBASE_INDEX.md` describing what the file does. Then overwrite the pending file to be empty. **Do not proceed until this is done.**

### Step 1b — Backstop: diff-based index check

Run `git diff --name-only HEAD` + `git ls-files --others --exclude-standard`. For every returned path (ignoring protocol bookkeeping, build output, and lockfiles), verify the path appears in `docs/CODEBASE_INDEX.md`. If any are missing, report to the user that the hook may have silently failed, then add them manually.

### Step 2 — Overwrite `docs/CURRENT_STATE.md`

Replace the file entirely with a fresh snapshot:

- Current phase + sub-phase
- Build status: working / broken / not yet tested
- Last 3 things accomplished this session
- Next 3 priorities
- Any active blockers

This file is always the most recent state. **Overwrite, do not append.**

### Step 3 — Append one line to `docs/HANDOFF_LOG.md`

Get the actual time with: `date '+%Y-%m-%d %H:%M'`

Append a single line at the bottom:
```
YYYY-MM-DD HH:MM | Phase X.Y | <one-line summary> | <build status>
```

### Step 4 — Git commit and push

Stage docs bookkeeping + commit with message: `Session: <one-line summary>`. Then push.

**Standing authorization for session-end pushes:** The user pre-authorizes `git push` as part of `/end` so they can continue work from another machine without manual ceremony. Project-specific; document in `DECISIONS.md` before relying on it. Covers normal pushes only — **force pushes still require explicit per-instance user confirmation.** If a push fails (rejected, conflicts, network), report it and let the user decide; do not retry destructively.

### Step 4a — Clean-tree guarantee (non-negotiable)

After the docs commit, run `git status --porcelain`. **Output MUST be empty** before Step 5. If anything remains:

1. **Real in-scope work** → stage and commit as a second commit: `Session followup: <short summary>`. Push again.
2. **Out-of-scope work the user hasn't reviewed** → STOP. Ask: commit, stash, or discard?
3. **Unknown category** → default to #2.

**Do not** leave anything unstaged or untracked and call `/end` done.

### Step 5 — Report

Three lines:
1. What was accomplished this session
2. What's next
3. Anything to watch for next session

---

## Between Sessions — What The User Does After `/end`

Once `/end` completes successfully, the session is over. The user should:

1. **Clear context** (`/clear` in Claude Code, or just close the window).
2. **Open a new session** whenever they're ready to work again.
3. **Type `/start`** in that new session. Claude will re-read `CURRENT_STATE.md` and `HANDOFF_LOG.md` and pick up exactly where the previous session left off.

**Do not run `/start` in the same session that just ran `/end`.** That session's context is already stale — re-reading docs Claude just wrote won't help, and you'll be wasting the context window on superseded tool output.

**Why this works:** `CURRENT_STATE.md` + `HANDOFF_LOG.md` are designed to be the *entire* memory that crosses session boundaries. A fresh context window + `/start` is strictly better than a full context window carried over, because Claude reads the definitive files instead of relying on drifting in-memory assumptions.

---

## Hooks Reference

Configured in `.claude/settings.json`:

| Hook | Trigger | Action |
|---|---|---|
| `SessionStart` (matcher: `startup\|resume\|clear`) | When a session starts, resumes, or clears | Runs `python .claude/scripts/session-start-context.py`. Performs the worktree guard, reads `docs/CURRENT_STATE.md` + last 5 lines of `docs/HANDOFF_LOG.md`, injects them as `additionalContext` so Claude can give the 3-line status report without the user typing `/start`. |
| `PostToolUse` (matcher: `Write\|Edit`) | After any `Write` or `Edit` tool call | Runs `python .claude/scripts/track-new-file.py`. Appends the path to `.claude/pending-index-updates.txt` only if the path is not already present in `docs/CODEBASE_INDEX.md` (so editing existing files doesn't re-queue them). |
| `Stop` (no matcher) | When Claude finishes a turn | Runs `python .claude/scripts/stop-clean-tree-check.py`. Silent during normal work; only blocks the stop if a `Session:` commit was just made within the last 5 minutes AND `git status --porcelain` is still non-empty (i.e. /end Step 4a was skipped). Acts as a fail-safe for the clean-tree guarantee. |

The hook script is silent on failure (never blocks Claude's work) and skips meta files (the index, current state, handoff log, anything inside `.claude/`, build outputs).

### Statusline (not a hook, but wired in `settings.json`)

`statusline.py` runs on every prompt-line render. It reads phase + build status from `docs/CURRENT_STATE.md` and adds the current branch + dirty-file count from git. Configured under the top-level `statusLine` key in `.claude/settings.json`, not `hooks` — listed here so every moving part of the template is documented in one place.

---

## Slash Commands

Defined in `.claude/commands/`:

| Command | What it does |
|---|---|
| `/start` | Triggers Session Start Protocol |
| `/end` | Triggers Session End Protocol |

---

## Why this protocol is short

If a protocol is 300 lines, agents skim it and miss steps. If it's under 200 lines and has clear numbered steps with one source of truth per fact, agents follow it. **Brevity is a feature, not a limitation.**
