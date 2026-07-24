# Claude Code Project Template

A copy-in-and-customize skeleton for new projects that want the session protocol, code quality rules, and automated codebase-index discipline developed on a real Tauri + Cloudflare project.

## Prerequisites

The template's hooks rely on one harness-provided environment variable:

- **`CLAUDE_PROJECT_DIR`** — the absolute path of the project root. Claude Code sets this automatically when launching, so the Python scripts in `.claude/scripts/` resolve project-relative paths correctly. **You should not need to set it yourself.**

If hooks are silently doing nothing (see Troubleshooting), the most common cause is that `CLAUDE_PROJECT_DIR` is unset because Claude Code was launched from outside the project root, or because a wrapper / IDE plugin stripped it. Verify with `python -c "import os; print(os.environ.get('CLAUDE_PROJECT_DIR'))"` from inside Claude Code's Bash tool.

Other prerequisites: `python3` on `PATH`, `git`, and a Claude Code version recent enough to support `SessionStart`, `PostToolUse`, and `Stop` hooks (any 2025-Q4 build or later).

## What this gets you

- **Auto-loaded `CLAUDE.md`** — project rules + work style that every session starts with.
- **`PROTOCOL.md`** — the single source of truth for session lifecycle (start / during / end).
- **`/start` + `/end` slash commands** — wired session begin/close with worktree guard, clean-tree guarantee, auto-push, and a mandatory start-of-session **CROSS-CHECK** (NEXT ACTION vs the status spine vs the last handoff → flag contradictions instead of trusting one file).
- **Anti-drift status model** — a single "status at a glance" **spine** table in `ROADMAP.md` is the sole source of truth for where the project stands; `CURRENT_STATE.md` only points at it. Phase/block numbers are **frozen** (a cut item stays a labeled gap, never renumbered). This kills the "which phase are we on?" drift that happens when two docs both keep a status list. The `SessionStart` hook injects the spine and the cross-check directive automatically.
- **Open-item ledger (`docs/SESSION_LEDGER.md`)** — an append-and-strike ledger for queued tests, pre-release gates, riders, and watch items, written **at the moment** things are queued or resolved instead of recalled at `/end`. Added 2026-07-24 after a drift audit on the source project found four measured failure modes in recap-based wrap-ups (facts lost, wrong, duplicated, or read stale — a passed smoke test literally vanished from a wrap because long sessions get context-compacted). `/end` reconciles the ledger mechanically (Step 1d), `/start` and the hook surface it, and a **mini-wrap rule** covers post-`/end` follow-up work with delta-only records.
- **Bidirectional `CODEBASE_INDEX.md` discipline** — the `PostToolUse` hook covers the forward direction (new file on disk → appended to a pending queue → `/end` refuses to complete until it's indexed); `validate-index.py` (run at `/end` Step 1c) covers the reverse (index rows pointing at files that no longer exist → flagged for removal).
- **Session docs skeleton** — `CURRENT_STATE.md` (NEXT-ACTION-first shape), `HANDOFF_LOG.md`, `CODEBASE_INDEX.md` with the conventions baked in.
- **`.mcp.json.template`** — opt-in Cloudflare MCP server bundle (Workers Bindings, observability, browser rendering). Rename to `.mcp.json` and follow the inline comments to enable.

## How to apply to a new project

1. **Copy files into the new project root.** The template mirrors the target layout — `.claude/` stays as-is, `docs/` stays as-is, the `.md` files go at the repo root.

   First, set `KB_TEMPLATE_DIR` to wherever your Knowledge Base lives (one-time per shell, or persist via your profile / `[Environment]::SetEnvironmentVariable`):

   PowerShell:

   ```powershell
   $env:KB_TEMPLATE_DIR = "C:\path\to\Knowledge Base\claude-project-template"
   # from the new project's root:
   robocopy "$env:KB_TEMPLATE_DIR" . /E /XD .git
   ```

   Git Bash / WSL / macOS / Linux:

   ```bash
   export KB_TEMPLATE_DIR="$HOME/path/to/Knowledge Base/claude-project-template"
   # from the new project's root:
   cp -r "$KB_TEMPLATE_DIR/." .
   ```

   After copying:
   - Rename `.gitignore.template` → `.gitignore`.
   - Verify `.claude/pending-index-updates.txt` is empty (template ships drained; if not, empty it before `/end`).
   - If you plan to use Cloudflare MCP servers, rename `.mcp.json.template` → `.mcp.json` and follow the comments inside.

2. **Customize `CLAUDE.md`** — search for `<ProjectName>`, `<project-name>`, and `<TODO>` markers. Fill in:
   - Project name + one-line purpose
   - Locked technical decisions table (frontend, backend, DB, etc.)
   - Delete any "Work style" sections that don't apply (e.g. drop "mock before you build" for non-UI projects)

3. **Customize `PROTOCOL.md`** — generally works as-is. Only edit if your project has unusual session conventions.

4. **Customize `.claude/commands/start.md` + `end.md`** — these now use generic phrasing ("`cd` into your project root and run `claude`") so no path substitution is required. Edit only if you want to add project-specific guidance.

5. **Prime the docs** — `docs/CURRENT_STATE.md` has placeholders for Day 1; fill in the single **📍 NEXT ACTION** line (session-start reports it verbatim). `docs/HANDOFF_LOG.md` is just a header. `docs/CODEBASE_INDEX.md` starts empty but grows with every `/end` as the PostToolUse hook captures new files. `docs/SESSION_LEDGER.md` ships with rules + no items — it fills itself the first time work gets queued for later ("next session," "before release," …).

6. **Create the status spine (when the roadmap lands)** — the anti-drift model depends on one authoritative status list. When you write `ROADMAP.md`, give it a **"📊 status at a glance" spine table** (one row per phase/block + its status, with a CURRENT marker). `CURRENT_STATE.md` and the `/start` cross-check read from it; do **not** duplicate the phase list anywhere else. Until the spine exists, the hook and cross-check simply skip it — nothing breaks, you just don't get drift protection yet.

7. **Verify the hook works** — open Claude Code in the new project, then ask it to `Write` a throwaway file at `tmp-hook-check.md`. Then read `.claude/pending-index-updates.txt`:
   - **Contains `tmp-hook-check.md`** → hook is live. Delete the throwaway file and clear the pending entry.
   - **Empty or missing** → hook didn't fire. See "Troubleshooting" below before continuing.

   (An empty pending file in normal operation means "no undocumented files queued." Right after writing a brand-new file, it should be non-empty.)

8. **Optional but recommended:** Add a `DECISIONS.md` at the repo root for architectural decision records. The `/end` protocol references it as the home for "pre-authorized push" consent and major tech choices.

## Troubleshooting

### Hooks don't seem to be firing

Symptoms: you write a new file, but `.claude/pending-index-updates.txt` stays empty. Or `/end` completes despite undocumented files in the diff.

Diagnostic order:

1. **Confirm hook is wired.** `cat .claude/settings.json | python -c "import sys, json; print(json.load(sys.stdin)['hooks'].get('PostToolUse'))"`. Should print a non-empty list referencing `track-new-file.py`.
2. **Confirm Python is on PATH.** Run `python --version` (or `python3 --version`) from inside Claude Code's Bash tool. The hook command in `settings.json` invokes `python` literally.
3. **Confirm `CLAUDE_PROJECT_DIR` is set.** Inside Claude Code, run `python -c "import os; print(os.environ.get('CLAUDE_PROJECT_DIR'))"`. Empty output = hooks will silently no-op (the script returns early when the var is unset; see `track-new-file.py:68`).
4. **Run the hook manually.** Pipe a synthetic event into the script:
   ```bash
   echo '{"tool_name":"Write","tool_input":{"file_path":"<absolute path to a test file>"}}' \
     | CLAUDE_PROJECT_DIR=$(pwd) python .claude/scripts/track-new-file.py
   ```
   Then check `.claude/pending-index-updates.txt`. If this works manually but not in-session, the harness isn't passing the env var or isn't matching `Write|Edit`.
5. **Check the matcher.** The hook is registered with matcher `Write|Edit`. If your Claude Code version uses a different tool name (e.g. `WriteFile`), the matcher misses every event silently.

### `/end` reports paths as missing from the index, but the hook should have caught them

This is Step 1b doing its job. The hook is the primary path; Step 1b is the belt-and-suspenders backstop that runs `git diff --name-only HEAD` + `git ls-files --others --exclude-standard`. Trust the backstop, add the missing entries, and add a "things to watch" note in `CURRENT_STATE.md` so next session knows the hook silently dropped events.

### Worktree guard trips on every session

You're on Claude Code Desktop, which force-creates worktrees. See the linked GitHub issue + Reddit workaround in `.claude/commands/start.md`. Or switch to the CLI.

## What's opinionated vs. generic

| Layer | Opinionated? | Why |
|---|---|---|
| Code quality rules (500/800 line caps, no `utils/`, Zod at boundaries, DRY 3+) | Yes | These are the template author's standing preferences; drop/edit to taste |
| Session lifecycle (overwrite `CURRENT_STATE`, append `HANDOFF_LOG`, auto-push) | Mostly | The protocol shape is generic; the auto-push consent requires your sign-off per project |
| PostToolUse hook + `validate-index.py` for bidirectional index tracking | Yes | Addresses a real discipline-failure mode; strongly recommended |
| Status spine as single source of truth + `/start` cross-check + frozen numbers | No | Generic anti-drift mechanism — helps any project that keeps a running status doc. Costs nothing until you create the spine |
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
- **A `ROADMAP.md`** — your project's phases are your project's business. `CLAUDE.md` references this file as optional context. **When you do create it, give it a "📊 status at a glance" spine table** — one row per phase/block with its status. That table is the single source of truth the protocol's `/start` cross-check and the SessionStart hook read from (see `PROTOCOL.md` → "Where-are-we: one source of truth, frozen numbers"). Until the spine exists, the hook simply skips it — nothing breaks.
- **Per-folder `README.md` conventions** — mentioned in `CLAUDE.md` rule #9 because they're useful once a codebase has multiple features. Write them incrementally as the project grows; don't seed empty ones.

## Provenance

Extracted from a Tauri 2 + Cloudflare Worker desktop app on 2026-04-20 after a project-wide audit consolidated the conventions into a stable shape. The source project's exact path is environment-specific; treat this template as the canonical version and resync upstream conventions when they meaningfully evolve.

**Resync 2026-07-24:** ported the source project's drift-audit fixes — `docs/SESSION_LEDGER.md` (moment-of-event open-item ledger), `/end` Step 1d ledger reconciliation, the re-read-CURRENT_STATE-from-disk concurrency guard, ~300-char handoff-line cap, the post-`/end` mini-wrap rule, and ledger injection in the SessionStart hook + `/start` cross-check.
