# Claude Code Project Template

A copy-in-and-customize skeleton for new projects that want the session protocol, code quality rules, and automated codebase-index discipline developed on the Checkpoint project.

## What this gets you

- **Auto-loaded `CLAUDE.md`** — project rules + work style that every session starts with.
- **`PROTOCOL.md`** — the single source of truth for session lifecycle (start / during / end).
- **`/start` + `/end` slash commands** — wired session begin/close with worktree guard, clean-tree guarantee, and auto-push.
- **PostToolUse hook** — enforces `CODEBASE_INDEX.md` updates automatically. New file created → hook appends to pending queue → `/end` refuses to complete until every entry is indexed.
- **Session docs skeleton** — `CURRENT_STATE.md`, `HANDOFF_LOG.md`, `CODEBASE_INDEX.md` with the conventions baked in.

## How to apply to a new project

1. **Copy files into the new project root.** The template mirrors the target layout — `.claude/` stays as-is, `docs/` stays as-is, the `.md` files go at the repo root.

   ```bash
   # from the new project's root:
   cp -r "C:/Users/haith/Documents/Vibe Projects/Knowledge Base/claude-project-template/." .
   ```

   (On Windows Git Bash; adjust for PowerShell with `robocopy`.)

2. **Customize `CLAUDE.md`** — search for `<ProjectName>`, `<project-name>`, and `<TODO>` markers. Fill in:
   - Project name + one-line purpose
   - Locked technical decisions table (frontend, backend, DB, etc.)
   - Delete any "Work style" sections that don't apply (e.g. drop "mock before you build" for non-UI projects)

3. **Customize `PROTOCOL.md`** — generally works as-is. Only edit if your project has unusual session conventions.

4. **Customize `.claude/commands/start.md` + `end.md`** — search for `<project-dir>` and replace with the absolute path to your new project. This is only used in the worktree-guard diagnostic message.

5. **Prime the docs** — `docs/CURRENT_STATE.md` has placeholders for Day 1. `docs/HANDOFF_LOG.md` is just a header. `docs/CODEBASE_INDEX.md` starts empty but grows with every `/end` as the PostToolUse hook captures new files.

6. **Verify the hook works** — open Claude Code in the new project, create a test file via `Write`, then check `.claude/pending-index-updates.txt` is non-empty. If yes, hook is live.

7. **Optional but recommended:** Add a `DECISIONS.md` at the repo root for architectural decision records. The `/end` protocol references it as the home for "pre-authorized push" consent and major tech choices.

## What's opinionated vs. generic

| Layer | Opinionated? | Why |
|---|---|---|
| Code quality rules (500/800 line caps, no `utils/`, Zod at boundaries, DRY 3+) | Yes | These are the template author's standing preferences; drop/edit to taste |
| Session lifecycle (overwrite `CURRENT_STATE`, append `HANDOFF_LOG`, auto-push) | Mostly | The protocol shape is generic; the auto-push consent requires your sign-off per project |
| PostToolUse hook for index tracking | Yes | Addresses a real discipline-failure mode; strongly recommended |
| Worktree guard on `/start` + `/end` | Yes | Claude Code Desktop force-creates worktrees; this flagbreaks the user out of them. Only relevant if you hit the same problem |
| Mock-before-build workflow | No | Only applies to UI-heavy projects. Drop the section in `CLAUDE.md` for backend/CLI projects |

## Where to put what — CLAUDE.md vs memory vs DECISIONS.md

The template uses three separate places for "things Claude needs to remember." Picking the right one matters because each has different cost and lifetime.

| Place | Lifetime | Auto-loaded? | Use for |
|---|---|---|---|
| `CLAUDE.md` (in repo) | Project-wide | Every turn | **Non-negotiable rules** that apply to every change. File caps, DRY policy, Zod-at-boundaries. Keep it lean — every line costs context. Long-form rules go in `docs/WORK_STYLE.md`. |
| `DECISIONS.md` (in repo) | Project-wide | On demand | **Architectural decisions with rationale.** Why you picked Cloudflare D1, why session-end auto-push is pre-authorized, why you banned worktrees. Append-only; never overwrite. |
| `~/.claude/projects/<slug>/memory/` (auto-loaded by harness) | Per-user, per-project | Every turn (the index) | **Cross-session learnings about THIS user on THIS project** — feedback they've given you, project-specific context not in code, references to external systems. Save these as you discover them; don't restate them in `CLAUDE.md`. |

### What to save to memory

The harness manages four memory types: `user` (who they are), `feedback` (corrections + validated approaches), `project` (current state, who's doing what, deadlines), `reference` (where to look in external systems). Save freely; the harness has its own discipline about what's worth keeping.

**Examples of memory-worthy moments on a typical project session:**

- User says "stop using `any` even in test files — we want strict everywhere" → `feedback` memory.
- User mentions "the CRDT logic in this repo is based on Yjs, see https://docs.yjs.dev/" → `reference` memory.
- User says "we're cutting v0.3 next Friday so let's not start anything that won't finish by Wednesday" → `project` memory (with absolute date).
- User confirms a non-obvious architectural choice ("yeah, keeping the migration runner inline was the right call here, splitting it would just be ceremony") → `feedback` memory (validated judgment, not a correction).

### What NOT to save to memory

- Anything already in `CLAUDE.md` or `docs/CODEBASE_INDEX.md` — duplicates rot.
- Recent git history or "what was done last session" — `git log` and `CURRENT_STATE.md` are authoritative.
- Code patterns that are obvious from reading the code itself.
- Bug fixes you just made — the commit message is the record.

The rule of thumb: memory is for things that would be hard to figure out by reading the repo today.

## What this template does NOT include

- **Tech stack choices** — no frontend framework, no DB, no deployment target. Each project picks its own and records them in its `CLAUDE.md` "Locked technical decisions" table.
- **A `ROADMAP.md`** — your project's phases are your project's business. `CLAUDE.md` references this file as optional context.
- **Per-folder `README.md` conventions** — mentioned in `CLAUDE.md` rule #9 because they're useful once a codebase has multiple features. Write them incrementally as the project grows; don't seed empty ones.

## Provenance

Extracted from Checkpoint (C:\Users\haith\Documents\Vibe Projects\Checkpoint) on 2026-04-20 after the Pass A audit consolidated the project's conventions into a stable shape. Source of truth for future template updates: whatever Checkpoint is doing at the time you decide to resync.
