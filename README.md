# Knowledge Base

Reusable patterns and lessons learned from vibe coding projects. Reference these when starting new projects to avoid re-learning the same things.

## Project template

- [claude-project-template/](./claude-project-template/) — Copy-in skeleton for new projects: auto-loaded `CLAUDE.md`, `PROTOCOL.md` session lifecycle, `/start` + `/end` slash commands, and a `PostToolUse` hook that enforces `CODEBASE_INDEX.md` updates. See its [README](./claude-project-template/README.md) for the apply-to-new-project steps.
- [claude-project-template/.gitignore.template](./claude-project-template/.gitignore.template) — Baseline `.gitignore` for new projects. Rename to `.gitignore` after copying the template in.

## Lessons

- [tauri-desktop-oauth.md](./tauri-desktop-oauth.md) — Google OAuth in Tauri 2 desktop apps (localhost callback + bearer tokens). The flow, code, gotchas, what NOT to do.
- [tauri-ipc-serde.md](./tauri-ipc-serde.md) — Always add `#[serde(rename_all = "camelCase")]` to Rust structs crossing the Tauri IPC boundary. Hidden `undefined`-field bug.
- [cloudflare-worker-setup.md](./cloudflare-worker-setup.md) — Deploying a Cloudflare Worker + D1 from zero. Exact command sequence, secrets, CORS for native apps.

## Decisions & references

- [DECISIONS.md](./DECISIONS.md) — Append-only log of why this knowledge base is shaped the way it is. Read before adding a new lesson or restructuring.
- [references.md](./references.md) — Curated reading list: Diátaxis, awesome-claude-code, MCP servers, Tauri/Cloudflare-specific resources. Browse on demand.

## Freshness rule

Every lesson `.md` carries YAML frontmatter with `stack`, `kind`, and `last_verified` (date). When you reread a lesson and confirm it's still right, bump `last_verified` to today. When you change anything in the recipe, bump it as part of the same edit. Anything older than ~6 months is suspect — verify before relying on it. No tooling enforces this; it's a habit, not a hook.
