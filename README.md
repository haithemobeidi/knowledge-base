# Knowledge Base

Reusable patterns and lessons learned from vibe coding projects. Reference these when starting new projects to avoid re-learning the same things.

---

## Agent instructions — copying this into a new project

> **If you are an AI agent (Claude Code or similar)** and the user has told you any of the following:
> - "copy the KB over"
> - "set this project up with the template"
> - "scaffold this with my Claude Code template"
> - "bootstrap this project from the Knowledge Base"
> - or anything semantically equivalent
>
> ...follow this procedure exactly. Do not improvise.

### Step 1 — Confirm target & stack with one question

Ask the user a single question if you don't already know the answer:

> "What stack is this project? (e.g. Tauri + Cloudflare, Next.js, plain CLI, Python, etc.) I'll customize CLAUDE.md and trim work-style rules that don't apply."

If the user already told you the stack, skip the question.

### Step 2 — Copy ONLY the template directory

The template lives at `<KB_ROOT>/claude-project-template/`. The KB root is wherever this `README.md` lives — typically `~/Documents/Vibe Projects/Knowledge Base/` on the original author's machine, but ask the user if you don't know.

Use the user's shell:

- **PowerShell:** `robocopy "<KB_ROOT>/claude-project-template" . /E /XD .git`
- **Git Bash / WSL / macOS / Linux:** `cp -r "<KB_ROOT>/claude-project-template/." .`

**Do NOT copy** the lesson files (`tauri-desktop-oauth.md`, `tauri-ipc-serde.md`, `cloudflare-worker-setup.md`), `DECISIONS.md`, `references.md`, or this README. Those stay in the KB and are only pulled in on demand if relevant to the new project.

### Step 3 — Customize CLAUDE.md

Open `CLAUDE.md` in the new project and:

- Replace `<ProjectName>` with the actual project name everywhere it appears.
- Fill in the "Locked technical decisions" table with the user's answers from Step 1. Delete rows that don't apply (e.g. drop `Payments` for a CLI tool, drop `Frontend` for a backend-only project).
- **Trim stack-irrelevant work-style rules:**
  - **Not a UI project** (CLI, library, backend, infra) → delete the "Mock before you build" row from the Work-style table and remove that section from `docs/WORK_STYLE.md`.
  - **Not a multi-feature app** (single-purpose tool) → leave "Don't reinvent the wheel" alone but consider trimming the "Pause at natural test milestones" section to a one-liner.
- Update the one-line tagline at the top.

### Step 4 — Customize the rest

- Rename `.gitignore.template` → `.gitignore`. Append project-specific ignores under the marked line.
- If the project uses Cloudflare: rename `.mcp.json.template` → `.mcp.json` and follow the inline comments.
- Otherwise: delete `.mcp.json.template` (or leave it for later — it's inert until renamed).
- Prime `docs/CURRENT_STATE.md` with Day-0 placeholders (the file already has TODO markers).
- Leave `docs/HANDOFF_LOG.md` and `docs/CODEBASE_INDEX.md` as-is — they grow at `/end`.

### Step 5 — Verify hooks fire

Critical step. From inside Claude Code in the new project:

1. Ask the user to grant `Write` permission for a one-shot test.
2. Write a throwaway file: `tmp-hook-check.md` with content "delete me."
3. Read `.claude/pending-index-updates.txt`. It should contain `tmp-hook-check.md`.
4. If empty: see "Troubleshooting" in `claude-project-template/README.md`. Most common cause: `CLAUDE_PROJECT_DIR` not set (Python script silently exits).
5. Delete `tmp-hook-check.md` and clear the pending entry.

### Step 6 — Pulling in lessons (later, on demand only)

**Do not auto-load the KB lesson files into context** as part of bootstrap. They live one directory above the template and are deliberately separate.

When the user later starts work that maps to a lesson — e.g. designing OAuth in a Tauri project, setting up a Cloudflare Worker — read the relevant `.md` from the KB root *then*, not now. The lesson frontmatter (`stack:`, `kind:`) helps you decide what's relevant. Lessons are reference material, not auto-loaded context.

### Step 7 — Initial commit

If the new project doesn't have a git repo yet, ask before initializing. Once initialized, make one commit: `Bootstrap project from claude-project-template`. Do not push without explicit user authorization.

---

## Project template

- [claude-project-template/](./claude-project-template/) — Copy-in skeleton for new projects: auto-loaded `CLAUDE.md`, `PROTOCOL.md` session lifecycle, `/start` + `/end` slash commands, and a `PostToolUse` hook that enforces `CODEBASE_INDEX.md` updates. See its [README](./claude-project-template/README.md) for the apply-to-new-project steps.
- [claude-project-template/.gitignore.template](./claude-project-template/.gitignore.template) — Baseline `.gitignore` for new projects. Rename to `.gitignore` after copying the template in.

## Lessons

- [tauri-desktop-oauth.md](./tauri-desktop-oauth.md) — Google OAuth in Tauri 2 desktop apps (localhost callback + bearer tokens). The flow, code, gotchas, what NOT to do.
- [tauri-ipc-serde.md](./tauri-ipc-serde.md) — Always add `#[serde(rename_all = "camelCase")]` to Rust structs crossing the Tauri IPC boundary. Hidden `undefined`-field bug.
- [tauri-sqlite-direct-sqlx.md](./tauri-sqlite-direct-sqlx.md) — Opening your own sqlx pool alongside `tauri-plugin-sql`. Plus the migration-not-registered footgun that shipped a silent feature regression.
- [cloudflare-worker-setup.md](./cloudflare-worker-setup.md) — Deploying a Cloudflare Worker + D1 from zero. Exact command sequence, secrets, CORS for native apps.
- [local-first-sync-with-d1.md](./local-first-sync-with-d1.md) — 13 patterns for building local-first sync against Cloudflare D1: field-level outbox, UUID identity, user-scoped writes, Worker-side defense, chunking that doesn't split row identity, tombstones with matched retention. The ones that survived production.
- [webview2-react-render-traps.md](./webview2-react-render-traps.md) — Eight WebView2/Tauri render gotchas not present in Chrome dev: image lazy-load intervention, `key={id}` for fresh GPU layers, useLayoutEffect-mandatory for measurement, drag-region clearance, portal-to-body for modals, scrollbar gutter, image pre-decode for flight animations.
- [mobile-shell-decision.md](./mobile-shell-decision.md) — Decision record: webview wrapper (Capacitor) vs native (SwiftUI + Compose) for mobile when your desktop is React. The reversal we made, why, and the framework for picking next time.
- [cross-boundary-dev-events.md](./cross-boundary-dev-events.md) — Structured dev-event ring buffer that captures events from both sides of the Rust ↔ TS boundary. Catches silent failures (swallowed errors, missed setters, hidden 200-with-rejection responses) that `console.log` can't because it dies the moment F12 closes.
- [restartable-task-generation-counter.md](./restartable-task-generation-counter.md) — Atomic generation counter for safely restarting threads / async tasks / child processes without leaking the old instance. Survives React StrictMode double-mounts and stop/start races. Extracted from Checkpoint's process monitor; LLM Hub uses it for sidecar restart.

## Decisions & references

- [DECISIONS.md](./DECISIONS.md) — Append-only log of why this knowledge base is shaped the way it is. Read before adding a new lesson or restructuring.
- [references.md](./references.md) — Curated reading list: Diátaxis, awesome-claude-code, MCP servers, Tauri/Cloudflare-specific resources. Browse on demand.

## Freshness rule

Every lesson `.md` carries YAML frontmatter with `stack`, `kind`, and `last_verified` (date). When you reread a lesson and confirm it's still right, bump `last_verified` to today. When you change anything in the recipe, bump it as part of the same edit. Anything older than ~6 months is suspect — verify before relying on it. No tooling enforces this; it's a habit, not a hook.
