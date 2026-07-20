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
- [powersync-steam-backend-architecture.md](./powersync-steam-backend-architecture.md) — The *successor* backend: off-the-shelf sync (PowerSync) + Steam OpenID login + Supabase Postgres + Cloudflare R2 on a Fly server. The full auth flow (two-token system, stateless JWT, presigned URLs), the security model (server-stamped ownership), and the build-vs-buy / self-hosting-economics / vendor-lock-in reasoning explained for a non-engineer.
- [webview2-react-render-traps.md](./webview2-react-render-traps.md) — Eight WebView2/Tauri render gotchas not present in Chrome dev: image lazy-load intervention, `key={id}` for fresh GPU layers, useLayoutEffect-mandatory for measurement, drag-region clearance, portal-to-body for modals, scrollbar gutter, image pre-decode for flight animations.
- [mobile-shell-decision.md](./mobile-shell-decision.md) — Decision record: webview wrapper (Capacitor) vs native (SwiftUI + Compose) for mobile when your desktop is React. The reversal we made, why, and the framework for picking next time.
- [cross-boundary-dev-events.md](./cross-boundary-dev-events.md) — Structured dev-event ring buffer that captures events from both sides of the Rust ↔ TS boundary. Catches silent failures (swallowed errors, missed setters, hidden 200-with-rejection responses) that `console.log` can't because it dies the moment F12 closes.
- [restartable-task-generation-counter.md](./restartable-task-generation-counter.md) — Atomic generation counter for safely restarting threads / async tasks / child processes without leaking the old instance. Survives React StrictMode double-mounts and stop/start races. Extracted from Checkpoint's process monitor; LLM Hub uses it for sidecar restart. Plus a related but distinct pattern: an N-consecutive-miss counter for debouncing a flickering process-liveness signal (launcher-to-game handoff gaps misread as "stopped").
- [supabase-rls-with-own-backend.md](./supabase-rls-with-own-backend.md) — When your own server + a sync layer (PowerSync/Electric) front Postgres, RLS isn't your auth model — but you must still enable deny-all RLS to lock Supabase's auto-on PostgREST/anon API. Why it's free (owner + replication bypass), the FORCE foot-gun, and a fresh-project checklist.
- [purge-secret-from-git-history.md](./purge-secret-from-git-history.md) — Removing a committed secret/credential/DB-dump from git history with `git-filter-repo` (+ re-add origin, `--force-with-lease`). The "remote is your backup until force-push" rule and why you must rotate the credential anyway.
- [tauri-desktop-security-hardening.md](./tauri-desktop-security-hardening.md) — Pre-launch hardening checklist for Tauri 2: asset-scope traversal, least-privilege `opener`, `#[cfg(debug_assertions)]` to drop debug commands from release, path-containment for file commands, the XSS lynchpin that makes the rest live-or-dormant.
- [sql-migration-runner-auto-baseline.md](./sql-migration-runner-auto-baseline.md) — A one-command migration runner that won't wipe data: auto-baselines an already-hand-migrated DB (records files as applied, runs none) so early `drop table` migrations can't re-run. Dry-run, per-migration transactions, multi-statement handling.
- [pre-launch-security-audit-playbook.md](./pre-launch-security-audit-playbook.md) — Repeatable pre-launch security review: fan out read-only auditors by trust-boundary domain (backend authz / data+input / client / frontend+secrets), prompt rules for signal-not-noise, triage, and the recurring lessons ("no CRITICALs ≠ done"; infra-config is the blind spot).
- [monorepo-stale-dist-zod-strip.md](./monorepo-stale-dist-zod-strip.md) — Workspace package consumed via `dist/` + Zod's default key-stripping = a new DB column that vanishes between SQLite and React with zero errors; git-clean says current, runtime runs week-old code. Plus the stacked-bug post-mortem method (verify pipeline STAGES: protocol-level stream capture, control-machine comparison) and the two-machine remote-agent runbook pattern (read-only rules, self-classifying diagnostic script).
- [n-copies-of-truth-drift-guard.md](./n-copies-of-truth-drift-guard.md) — Any app where one "thing" is described in 2+ independent schema copies (DB, sync rules, client schema, shared validators, server write-allowlist, build artifacts) will drift silently. The fix is an automated script that diffs the copies and fails the build — not a checklist.
- [shared-schema-multiple-projections-drift.md](./shared-schema-multiple-projections-drift.md) — A same-repo, same-commit drift flavor: multiple SQL/query call sites feed ONE shared parse schema, and a centralized column-list helper doesn't stop a second call site from writing its own inline SELECT. Recurred twice in the same codebase; the mitigation menu from cheapest to strongest.
- [motion-design-token-system.md](./motion-design-token-system.md) — A named easing/duration/preset module (mirrored as CSS vars) so JS and CSS animations can't drift apart, plus a real reduced-motion system: a 4-state preference, bridging into your JS animation library's OWN config (not just CSS), and a universal `!important` kill-switch for hardcoded utility-class durations that bypass the tokens.
- [material-tier-glassmorphism-tokens.md](./material-tier-glassmorphism-tokens.md) — A 3-tier (thin/regular/thick) translucent-surface token system organized by interaction ROLE, not visual weight. The non-obvious fix for "my modal doesn't look like glass": a luminosity bump on the top tier independent of blur/opacity.
- [clip-path-shared-element-morph.md](./clip-path-shared-element-morph.md) — A FLIP-transition variant using a union-bbox + `clip-path` instead of scale-transform (no blurry rescaling), plus a non-obvious gotcha: mixing your animation library's JS interpolator with WAAPI/CSS-transitioned properties in one coupled transition causes visible drift — keep every property on the same thread.
- [runtime-animation-profiler-hud.md](./runtime-animation-profiler-hud.md) — A dependency-free dev-only HUD that measures real frame timing (refresh-rate-agnostic jank detection) and fingerprints DOM/GPU-layer leaks by tagName/className histogram diffing — turns "it feels janky" into an exact element and class string to grep.
- [steam-library-integration.md](./steam-library-integration.md) — Steam's librarycache has three coexisting cover-art layouts across client versions; VDF text parsing vs. binary `appinfo.vdf` (use a validated crate); an authoritative-scan-diff pattern for install-state with a hard failure-vs-empty rule; and the Steam Web API 100k-calls/day ToS cap that forces a local-scan + OpenID + BYO-key three-tier architecture.
- [derive-dont-track-ui-flags.md](./derive-dont-track-ui-flags.md) — A boolean UI flag with more than a couple of reset paths (back button, Escape, nav-away, races...) will eventually get stuck true on the path someone forgot. Fix: derive it from state that's already correctly maintained, eliminating the reset action entirely.
- [tombstone-vs-hide-for-mirrored-data.md](./tombstone-vs-hide-for-mirrored-data.md) — A soft-delete tombstone claims "this shouldn't exist anywhere" — false for rows mirrored from an external authority (Steam library, calendar sync) that the server deliberately keeps live. Use a local-only, non-syncing hidden flag instead; soft-deleting re-derivable data is an unwinnable fight against a correctly-functioning sync engine. Plus two guard rules for genuine deletes: write-throughs must never re-insert a tombstoned row, and tombstone GC must be replication-confirmed, not a bare wall-clock timer.
- [dry-modularity-audit-playbook.md](./dry-modularity-audit-playbook.md) — Sibling to the security audit playbook: fan out read-only sweeps by code AREA (not trust domain), tier findings by drift-risk (already-bit-us / worthwhile / opportunistic) instead of line count, keep file-split candidates as a separate list, execute tier-by-tier as traceable separate commits.
- [byo-api-key-client-direct-tier.md](./byo-api-key-client-direct-tier.md) — Let users paste their own API key and call a metered third-party API directly instead of through your server, for a genuine free tier. The client-direct call must run from native code (key custody + CORS), one low branch point forks the network call only, one predicate per capability (never widen a shared "isPremium"), and a free key's real rate limit needs its own concurrency/retry tuning, not the paid path's.
- [local-sqlite-app-wide-change-signal.md](./local-sqlite-app-wide-change-signal.md) — A local DB with no live-query layer needs ONE coalesced "data changed" signal with every write choke point as a producer, or writers outside the original ad hoc poke inventory (a second window, a background sync engine) go stale with zero errors. Includes a debugging trap: verify data actually reached the layer before assuming the missing piece is the signal itself.

## Decisions & references

- [DECISIONS.md](./DECISIONS.md) — Append-only log of why this knowledge base is shaped the way it is. Read before adding a new lesson or restructuring.
- [references.md](./references.md) — Curated reading list: Diátaxis, awesome-claude-code, MCP servers, Tauri/Cloudflare-specific resources. Browse on demand.

## Freshness rule

Every lesson `.md` carries YAML frontmatter with `stack`, `kind`, and `last_verified` (date). When you reread a lesson and confirm it's still right, bump `last_verified` to today. When you change anything in the recipe, bump it as part of the same edit. Anything older than ~6 months is suspect — verify before relying on it. No tooling enforces this; it's a habit, not a hook.
