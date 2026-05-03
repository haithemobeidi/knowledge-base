# /end — Session End Protocol

Wrap up the development session cleanly. **Execute every step in order. Do not skip.**

> **Workflow note:** sessions are expected to run **directly in the main checkout** on the `main` branch. Worktrees are explicitly forbidden — Step 0a below is a hard guard.
>
> **Root cause (as of 2026-04-08):** Claude Code **Desktop** force-creates a worktree per session and there is **no setting to disable it** ([anthropics/claude-code#21236](https://github.com/anthropics/claude-code/issues/21236)). The CLI flag `tengu_worktree_mode` in `~/.claude.json` is CLI-only and ignored by desktop. Two known fixes: (1) **use the CLI** instead of the desktop app — `claude` from a terminal in the project root, guaranteed to work; or (2) **Reddit workaround for desktop** — Settings → Claude Code → Desktop: Worktree location → Custom folder location set to `C:\Program Files` (admin-only path makes worktree creation fail and the desktop app falls back to the main checkout).

## Step 0a — Worktree guard (FAIL FAST)

Run:

```bash
pwd
git rev-parse --abbrev-ref HEAD
```

If the cwd contains `.claude/worktrees/` OR the branch starts with `claude/`, **STOP IMMEDIATELY**. Do NOT proceed with `/end`. Tell the user verbatim:

> ⚠️ **Worktree guard tripped at /end.** This session ran inside a git worktree (`<paste pwd>`) on branch `<paste branch>`, which violates the workflow. Wrapping up here would re-pollute the handoff log with another `claude/<name>` branch merge.
>
> **Root cause:** Claude Code Desktop force-creates worktrees per session. The `tengu_worktree_mode` flag is CLI-only and ignored by desktop. See [anthropics/claude-code#21236](https://github.com/anthropics/claude-code/issues/21236).
>
> **Recommended:** do not `/end` from this worktree. Quit without ending (work on disk is preserved). Then either (a) use the CLI from a terminal — `cd` into your project root and run `claude` — or (b) apply the desktop Reddit workaround (Settings → Claude Code → Desktop: Worktree location → Custom = `C:\Program Files`). Start a new session in the main checkout and resume there.
>
> If you absolutely need to commit work from this worktree before quitting, ask explicitly — this protocol will not silently fast-forward main from a worktree branch.

**Only proceed to Step 0b if BOTH** `pwd` does NOT contain `.claude/worktrees/` **AND** the branch is `main`.

## Step 0b — Clear phantom-dirty files

Stale mtimes can come from any fresh checkout (a recent `git pull`, a worktree creation, an editor that touched mtimes without changing content, etc.), making git's stat cache flag unchanged files as "modified" until they're re-hashed. Run this once at the start of `/end` so Steps 1b and 4 see an honest `git status`:

```bash
git update-index --really-refresh > /dev/null 2>&1 || true
```

This is a no-op for files with real content changes — it only drops entries that are byte-identical to HEAD but had their mtime touched.

## Step 1 — Verify pending index updates (primary path)

Read `.claude/pending-index-updates.txt`.

- If the file does not exist or is empty, proceed to Step 1b.
- If non-empty: for each path listed, add a one-line entry to `docs/CODEBASE_INDEX.md` describing what the file does in plain language. Then overwrite `.claude/pending-index-updates.txt` to be empty (write an empty string).
- **Do not proceed until this is done.** This is the enforcement mechanism that replaces past projects' discipline-based approach.

## Step 1b — Backstop: diff-based index check

The Step 1 hook is the primary path (matches both `Write` and `Edit`), but this step remains as a belt-and-suspenders check in case the hook silently fails (python missing, script error, file created by some other tool, etc.).

Run:

```bash
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

For every path returned by either command, ignore it if any of these are true:
- Path contains `.claude/`, `pending-index-updates.txt`, `CODEBASE_INDEX.md`, `CURRENT_STATE.md`, or `HANDOFF_LOG.md` (these are protocol bookkeeping)
- Path is `node_modules/`, `dist/`, `target/`, `.next/`, `build/`, or any other build output
- Path is a lockfile (`pnpm-lock.yaml`, `Cargo.lock`, `package-lock.json`)
- <TODO: add your own ignore prefixes here — e.g. auto-generated icons, native platform gen/ directories>

For every remaining path, check whether it appears verbatim in `docs/CODEBASE_INDEX.md`. If any are missing:

- **Do not silently add them.** Report the missing paths to the user with a note that the PostToolUse hook may have failed to fire this session.
- Then add a one-line entry for each missing path to `docs/CODEBASE_INDEX.md`.
- Add a note to the next-session "things to watch" section of `CURRENT_STATE.md` flagging that the hook missed N files.

## Step 2 — Overwrite `docs/CURRENT_STATE.md`

Replace the file entirely with a fresh snapshot:

- Current phase + sub-phase
- Build status: working / broken / not yet tested
- Last 3 things accomplished this session
- Next 3 priorities
- Any active blockers

This file is always the most recent state. **Overwrite, do not append.**

## Step 3 — Append one line to `docs/HANDOFF_LOG.md`

Get the actual time with: `date '+%Y-%m-%d %H:%M'`

Append a single line at the bottom:
```
YYYY-MM-DD HH:MM | Phase X.Y | <one-line summary> | <build status>
```

## Step 4 — Git commit and push

Run `git status` to confirm what changed. Stage the docs bookkeeping:
- `docs/CURRENT_STATE.md`
- `docs/HANDOFF_LOG.md`
- `docs/CODEBASE_INDEX.md` (if updated)

Commit with message: `Session: <one-line summary>`

Then push to the remote: `git push`

The user has pre-authorized session-end pushes for this project (document in `DECISIONS.md` before relying on it). **Force pushes still require explicit per-instance user confirmation.** If a normal push is rejected (conflicts, etc.), report it and let the user decide — do not retry destructively.

### Step 4a — Clean-tree guarantee (non-negotiable)

After the docs commit succeeds, run `git status --porcelain`. **The output MUST be empty** before proceeding to Step 5.

For each remaining entry, categorize it:

1. **Real in-scope work touched this session** → Stage and commit as a second commit: `Session followup: <short summary>`. Then push again.
2. **Genuinely out-of-scope work the user made mid-session but hasn't reviewed** → STOP. Report the paths to the user and ask: "These files are modified but not part of the session summary. Commit them, stash them, or discard them?" Do not proceed until the user answers.
3. **You don't know which category it is.** → Default to #2. Ask.

**Do not** leave anything unstaged or untracked and call `/end` done.

## Step 5 — Report

Three lines:
1. What was accomplished this session
2. What's next
3. Anything to watch for next session

See [`PROTOCOL.md`](../../PROTOCOL.md) for the complete protocol context.
