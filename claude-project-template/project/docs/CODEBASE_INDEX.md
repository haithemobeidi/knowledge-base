# <ProjectName> — Codebase Index

**Purpose:** A one-line description of every meaningful file in the project. Future sessions read this to understand what each file does without re-reading the source.

**Maintenance:** Enforced by a `PostToolUse` hook. When you Write or Edit a file that is not listed here, its path is queued in `.claude/pending-index-updates.txt`; `/end` refuses to complete until every queued path has a row. `validate-index.py` (run at `/end`) flags rows whose files no longer exist.

**Last updated:** <TODO: set at the end of your first session.>

---

## Project root

| File | Purpose |
|---|---|
| `README.md` | Top-level project intro and documentation map |
| `CLAUDE.md` | Project file — what is different about this app; augments the global work style + protocol (auto-loaded from the Knowledge Base) |
| `ROADMAP.md` | Phased plan; holds the "status at a glance" spine (source of truth for phase/block status) |
| `DECISIONS.md` | Append-only architecture decision log with rationale |
| `.gitignore` | Git ignore rules |
| `.mcp.json.template` | Opt-in MCP server bundle. Rename to `.mcp.json` to enable. |

## docs/

| File | Purpose |
|---|---|
| `docs/CURRENT_STATE.md` | Rolling snapshot: NEXT ACTION (per track) + this-session deltas + shared state. Overwritten at `/end`. |
| `docs/HANDOFF_LOG.md` | Append-only one-line history of session ends. |
| `docs/SESSION_LEDGER.md` | Append-and-strike ledger of open session-scoped items; written at the moment of the event. |
| `docs/CODEBASE_INDEX.md` | This file. |

## .claude/

| File | Purpose |
|---|---|
| `.claude/protocol.json` | Per-project settings the protocol scripts read (check command, push policy, skip paths, ledger caps, tracks). The only protocol file edited per project. |
| `.claude/settings.json` | Hook wiring (SessionStart / PostToolUse / Stop) + statusline. Identical across projects. |
| `.claude/agents/planner.md` | Read-only planner subagent — implementation plans with declared pause-points. |
| `.claude/agents/reviewer.md` | Read-only reviewer subagent — independent diff review against the rules. |
| `.claude/agents/explorer.md` | Read-only explorer subagent — adjacent questions with `file:line` citations. |
| `.claude/scripts/protocol_config.py` | Shared loader for `protocol.json` + template-drift helpers; imported by every script. |
| `.claude/scripts/session-start-context.py` | SessionStart hook — worktree guard, global-install check, fetch + stale refusal, injects state docs + tracks + cross-check directive. |
| `.claude/scripts/track-new-file.py` | PostToolUse hook — queues unindexed paths to `pending-index-updates.txt`. |
| `.claude/scripts/stop-clean-tree-check.py` | Stop hook — blocks a stop when a Session commit just landed and this track's files are still dirty. |
| `.claude/scripts/validate-index.py` | `/end` Step 1c — flags index rows pointing at deleted files. |
| `.claude/scripts/scan-secrets.py` | `/end` Step 0c — content-based secret scan of everything heading for a commit; `--history` audits everything pushable. |
| `.claude/scripts/check-template-drift.py` | Compares this project's protocol machinery against the Knowledge Base template; `--sync` resyncs. |
| `.claude/scripts/statusline.py` | Statusline — phase + build status from CURRENT_STATE, branch + dirty count from git. |

<!-- Entries are added as files are created. Organise with ## subheadings as sections emerge (Frontend, Backend, Migrations, …). -->
