# /start — Session Start Protocol

Begin a development session.

> **Workflow note:** sessions run **directly in the main checkout** on the `main` branch. Worktrees are explicitly forbidden — they cause constant friction (random `claude/<name>` branches, shifting file paths, env files needing to be re-positioned, etc.).
>
> **Root cause (as of 2026-04-08):** Claude Code **Desktop** force-creates a git worktree per session and offers **no setting to disable it** (open issue: [anthropics/claude-code#21236](https://github.com/anthropics/claude-code/issues/21236)). The CLI feature flag `tengu_worktree_mode` in `~/.claude.json` is **CLI-only** — the desktop app ignores it entirely. So do `preferred_worktree_method: "disabled"` and `WorktreeCreate` hooks that `exit 1`.
>
> **Two known fixes:**
> 1. **Use the CLI instead of desktop** (guaranteed). Open Git Bash / Windows Terminal, `cd` to the project root, run `claude`. CLI honors `tengu_worktree_mode=false` and lands on `main`.
> 2. **Reddit workaround for desktop:** Settings → Claude Code → Desktop: Worktree location → set Custom folder location to a path requiring admin write (e.g. `C:\Program Files`). The desktop app tries to create the worktree, fails on the permission check, and falls back to the main checkout. Verify the next session lands on `main` before trusting it.
>
> Step 0 below is the belt-and-suspenders check that fires regardless of which workaround is in place.

## Step 0 — Worktree guard (FAIL FAST, do this BEFORE anything else)

Run:

```bash
pwd
git rev-parse --abbrev-ref HEAD
```

If the cwd contains `.claude/worktrees/` OR the branch starts with `claude/`, **STOP IMMEDIATELY**. Do not run Steps 1–5. Do not read other files. Do not edit anything. Tell the user verbatim:

> ⚠️ **Worktree guard tripped.** This session spawned inside a git worktree (`<paste pwd>`) on branch `<paste branch>`, which violates the workflow.
>
> **Root cause:** Claude Code Desktop force-creates a worktree per session. The CLI flag `tengu_worktree_mode` is CLI-only and ignored by desktop. See [anthropics/claude-code#21236](https://github.com/anthropics/claude-code/issues/21236).
>
> **Two fixes — pick one:**
> 1. **Use the CLI (guaranteed).** Quit this session. Open Git Bash / Windows Terminal. `cd` into your project root and run `claude`. The new session will land on `main`.
> 2. **Desktop Reddit workaround.** Settings → Claude Code → Desktop: Worktree location → set Custom folder location to `C:\Program Files` (or any admin-only path). Desktop will fail to create the worktree and fall back to the main checkout. Quit and restart this session to verify.

**Only proceed to Step 1 if BOTH** `pwd` does NOT contain `.claude/worktrees/` **AND** the branch is `main`.

Execute these steps in order:

1. Read `docs/CURRENT_STATE.md` for the latest project snapshot.
2. Read the last 5 lines of `docs/HANDOFF_LOG.md` for recent session summaries.
3. Run `git update-index --really-refresh > /dev/null 2>&1 || true` to clear phantom-dirty stat entries — files git thinks are modified but are byte-identical to HEAD. Stale mtimes can come from any fresh checkout, and the refresh is a cheap no-op when there's nothing to do. Then run `git status` and `git log --oneline -5`. If `git status` still shows changes after the refresh, those are real and must be surfaced to the user in Step 5 — they indicate the previous `/end` did not achieve a clean tree, which is a protocol violation to flag.
4. Run the project's security audit command (e.g. `pnpm audit --prod`, `npm audit`, `cargo audit`). Silent on green — only mention if there are non-zero findings.
5. Read `ROADMAP.md` only if you need context on what phase we're on.
6. Report a 3-line status to the user:
   - Current phase / sub-phase
   - What was accomplished last session
   - What's blocking, or what's next

**Do not** read every handoff or every doc. `CURRENT_STATE.md` is the source of truth. If it's wrong, fix it — don't work around it.

See [`PROTOCOL.md`](../../PROTOCOL.md) for the complete protocol context.
