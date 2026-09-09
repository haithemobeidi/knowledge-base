# /start — Session Start Protocol

Begin a development session. **Applies only to repos with `.claude/protocol.json`** (or `docs/CURRENT_STATE.md`); otherwise say "this repo has no session protocol" and stop.

> **Normally you do not need to type this.** The `SessionStart` hook runs Steps 0–6 automatically and injects the state docs. Use `/start` when the hook did not fire (python missing, hook disabled, global rules not installed) or to redo the check mid-session.

> **Workflow note:** sessions run **directly in the main checkout** on the `main` branch. Worktrees are forbidden: they shift file paths and strand gitignored env files, which breaks builds in confusing ways. Claude Code **Desktop** force-creates a worktree per session and offers no setting to disable it ([anthropics/claude-code#21236](https://github.com/anthropics/claude-code/issues/21236)); the CLI flag `tengu_worktree_mode` is CLI-only. Two fixes: (1) **use the CLI** — `cd` into the project root in a terminal and run `claude`; or (2) **desktop workaround** — Settings → Claude Code → Desktop: Worktree location → Custom folder = `C:\Program Files` (an admin-only path makes creation fail and desktop falls back to the main checkout).

## Step 0 — Worktree guard (FAIL FAST, before anything else)

```bash
pwd
git rev-parse --abbrev-ref HEAD
```

If the cwd contains `.claude/worktrees/` OR the branch starts with `claude/`, **STOP IMMEDIATELY**. Do not run the later steps, read files, or edit. Report the path, the branch, and the two fixes above, and wait.

## Step 0.3 — Global rules installed?

`~/.claude/CLAUDE.md` must import `claude-project-template/global/PROTOCOL.md`. If it does not (the hook will have said so), the session has no work-style rules and no protocol: locate the Knowledge Base clone on this machine, run `python "<KB>/claude-project-template/install-global.py"`, and restart. Tell the user first.

## Step 0.5 — Sync guard (BEFORE reading a single doc)

```bash
git fetch origin --prune
git status -sb
```

**`git status` reporting "up to date with 'origin/main'" is NOT a live check** — it compares HEAD against the local remote-tracking ref, which only moves on fetch/pull/push.

| State | Action |
|---|---|
| Up to date | Proceed. |
| `[behind N]`, tree clean | `git pull --ff-only`, then proceed. Report the pull in Step 7. |
| `[behind N]`, tree dirty | **STOP.** Surface both. Do not stash, do not merge. (Multi-track: the dirty files may be the other session's — say so; still the user's call.) |
| `[ahead N, behind M]` (diverged) | **STOP.** Surface it. Never auto-merge or rebase at session start. |
| Fetch failed (offline) | Proceed, but report currency as **unverified** in Step 7. |

Every file the later steps read is a tracked repo file. Reading them from a checkout that is behind origin loads a snapshot of the past, and the cross-check cannot catch it: it only tests whether the docs agree with each other, and stale docs agree perfectly. A stale checkout does not look broken; it looks complete. **Any protocol step that reads a git-backed source of truth must pull first** — this includes sibling repos a session reads (the Knowledge Base, shared config).

## Step 0.7 — Track gate (multi-track repos only)

If `.claude/protocol.json` declares two or more `tracks`: establish which track this session is on **before reading or editing anything**. Take it from the user's first message if stated; otherwise ask ("Which track is this session: desktop or mobile?") and wait. Everything below is scoped to your track — its NEXT ACTION section, its ID prefix, its last handoff line, its owned paths.

## Steps 1–7

1. Read `docs/CURRENT_STATE.md` — the **📍 NEXT ACTION** line(s) above all (your track's, in multi-track repos) and the Shared block.
2. Read the **open `[ ]` lines only** of `docs/SESSION_LEDGER.md`. Grep `- [ ]` rather than reading the whole file: closed lines keep their pre-closure text and are history, not context. Count the open items; note any that gate the NEXT ACTION (yours, `→all`, and unassigned legacy items in a multi-track repo). Items over the configured character cap are flagged — do not read past the cap unless the item is the next action.
3. Read the last 5 lines of `docs/HANDOFF_LOG.md`, plus (multi-track) the last line whose track field is yours.
4. Read the **status spine in `ROADMAP.md`** (heading per `spine_heading`) — the single source of truth for which phase/block is CURRENT (per track, if marked).
5. **Working-tree check** (Step 0.5 handled the remote). Run `git update-index --really-refresh > /dev/null 2>&1 || true` to clear phantom-dirty entries, then `git status` and `git log --oneline -5`. Changes surviving the refresh are real: surface them, since they mean the previous `/end` did not reach a clean tree — unless (multi-track) they sit in the other track's owned paths, in which case name them as theirs.
6. If `protocol.json` sets `audit_command`, run it. Silent on green; mention only findings.
7. **CROSS-CHECK (mandatory — the step that prevents drift).** Does the NEXT ACTION agree with (a) the spine's CURRENT marker (for your track), (b) the last HANDOFF line's "Next:" (your track's), (c) recent commits, and (d) no open ledger gate? **If any contradict, STOP and surface it — do not pick one and proceed.** A stale CURRENT_STATE leading with a minor loose end while the spine and handoff point at the real next work is exactly what this catches.

Then report, 4 lines plus a sync line (5 plus track in multi-track repos):

- **Track:** <name> *(multi-track only)*
- Where we are (phase/block **name + number** from the spine)
- What last session accomplished (your track's)
- The single **NEXT ACTION** — or the flagged contradiction
- Open ledger items: N (call out gates; multi-track: yours + `→all` + unassigned)
- **Sync:** `synced to origin @ <short-sha>`, plus `(pulled N)` or `(⚠️ fetch failed — currency unverified)`

**Trust, but verify.** CURRENT_STATE is hand-written and CAN be wrong. The spine wins any status disagreement, and CURRENT_STATE gets fixed — never silently work around either. Numbers are frozen. **Do not** read every handoff or every doc.

Full rules: the global `PROTOCOL.md` (already in context).
