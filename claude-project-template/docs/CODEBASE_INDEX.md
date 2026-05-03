# <ProjectName> — Codebase Index

**Purpose:** A one-line description of every meaningful file in the project. Future Claude sessions read this to understand what each file does without re-reading the source.

**Maintenance:** Updates are enforced by a `PostToolUse` hook. When you create a new file with `Write`, it's automatically added to `.claude/pending-index-updates.txt`. The `/end` slash command refuses to complete until every pending file has an entry in this index.

**Last updated:** <TODO: will be updated at the end of your first session.>

---

## Project root

| File | Purpose |
|---|---|
| `README.md` | Top-level project intro and documentation map |
| `CLAUDE.md` | Project context auto-loaded by Claude every session — locked decisions and code quality rules |
| `PROTOCOL.md` | Single source of truth for session lifecycle (start / during / end / hooks / commands) |
| `ROADMAP.md` | Phased development plan |
| `DECISIONS.md` | Architecture decision log — append-only with rationale for every major choice |
| `.gitignore` | Git ignore rules |
| `package.json` | <TODO if JS project — or delete row> |

## docs/

| File | Purpose |
|---|---|
| `docs/WORK_STYLE.md` | Long-form work-style rules — mock-before-build, don't-reinvent-the-wheel, pause-at-milestones. Read on demand, not auto-loaded. |
| `docs/CURRENT_STATE.md` | Latest project snapshot (phase, build status, recent work, next priorities). Overwritten each `/end`. |
| `docs/HANDOFF_LOG.md` | Append-only one-line history of session ends. |

## .claude/agents/

| File | Purpose |
|---|---|
| `.claude/agents/planner.md` | Read-only planner subagent. Designs implementation plans with declared pause-points before code is written. |
| `.claude/agents/reviewer.md` | Read-only reviewer subagent. Independent diff review against CLAUDE.md rules. |
| `.claude/agents/explorer.md` | Read-only explorer subagent. Researches adjacent questions without derailing current work. |

## .claude/scripts/

| File | Purpose |
|---|---|
| `.claude/scripts/track-new-file.py` | PostToolUse hook — queues undocumented file paths to `pending-index-updates.txt` so `/end` enforces index updates. |
| `.claude/scripts/session-start-context.py` | SessionStart hook — runs worktree guard, injects `CURRENT_STATE.md` + last 5 handoff lines so the user doesn't have to type `/start`. |
| `.claude/scripts/stop-clean-tree-check.py` | Stop hook — fail-safe for `/end` Step 4a; blocks the stop if a `Session:` commit just landed but tree is still dirty. |
| `.claude/scripts/statusline.py` | Statusline command — reads phase + build status from `CURRENT_STATE.md`, adds branch + dirty count from git. |

<!-- Entries are added automatically as files are created.
     At each /end, the PostToolUse hook forces the pending queue to be addressed.
     Organize with ## subheadings as sections emerge (Frontend, Backend, Migrations, etc.). -->
