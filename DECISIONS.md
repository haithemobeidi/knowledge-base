# Knowledge Base — Decisions

Append-only log of why this knowledge base is shaped the way it is. Newest entries at the bottom. Never rewrite past entries — supersede with a new one if a decision changes.

---

## 2026-04-20 — Extract `claude-project-template` from Checkpoint

**Decision:** Snapshot Checkpoint's `.claude/`, root `CLAUDE.md` / `PROTOCOL.md`, and `docs/` skeleton into `claude-project-template/` here.

**Why:** Checkpoint had stabilized the session protocol (CURRENT_STATE overwrite, HANDOFF_LOG append, hook-enforced index, worktree guard, /start + /end). Re-deriving these for every new project was wasted ceremony. Canonical source of truth: this template; resync from Checkpoint when its protocol meaningfully evolves.

**How to apply:** New projects start by copying this template wholesale, then customizing `<ProjectName>` / `<TODO>` markers. The template is *not* a generator — it's a paste-and-edit skeleton.

---

## 2026-04-13 — Canonize Tauri OAuth lesson

**Decision:** Promote the localhost-callback + bearer-token Tauri OAuth pattern from Checkpoint into a standalone `tauri-desktop-oauth.md` lesson.

**Why:** Cookie-based desktop OAuth (custom URL schemes, `@daveyplate/better-auth-tauri`) was unreliable on Windows specifically. Wasted ~2 days debugging. The pattern that worked is identical to what VS Code / GitHub CLI / JetBrains do, so it generalizes beyond Tauri.

**How to apply:** Read before any new desktop project that needs Google/GitHub/etc. OAuth. Don't rebuild from scratch.

---

## 2026-04-13 — Canonize Tauri IPC serde lesson

**Decision:** Save the `#[serde(rename_all = "camelCase")]` rule as a standalone lesson.

**Why:** Lost an hour debugging `undefined` JS-side fields because Rust serializes `snake_case` and Tauri IPC pipes JSON through verbatim. Single-line fix; high embarrassment-cost if you re-discover it.

**How to apply:** Every Rust struct that crosses the `#[tauri::command]` boundary gets the attribute, no exceptions.

---

## 2026-04-13 — Canonize Cloudflare Worker + D1 setup

**Decision:** Save the zero-to-deployed command sequence as a standalone lesson.

**Why:** Setup spans 5+ tools (wrangler login, d1 create, schema, migrations, secrets, CORS) and the Cloudflare docs route through 4 different pages. Having the whole sequence in one file shaves 30+ minutes off any new Worker project.

**How to apply:** Read before bootstrapping any new Cloudflare Worker that talks to a native client.

---

## 2026-05-03 — Initialize as a git repo

**Decision:** `git init` the Knowledge Base. Add a top-level `.gitignore` covering `*.7z`, OS cruft, and per-machine Claude state.

**Why:** A knowledge base whose purpose is "lessons that should outlive any single project" needs version history. Without it, an accidental overwrite is unrecoverable. The `.7z` archive of the template was tracked-but-unexplained; gitignore it so future zips don't pollute the diff.

**How to apply:** Commit lesson edits as you make them. No formal session protocol here — this is a reference repo, not a project.

---

## 2026-05-03 — Surface the template in the root README

**Decision:** Restructure root `README.md` into "Project template" + "Lessons" sections. Mention `.gitignore.template` explicitly.

**Why:** The template was the biggest asset in the repo and invisible from the front door — README only listed the three lesson `.md` files. New users (and future-me) shouldn't have to `ls` to find it.

**How to apply:** When adding a new lesson or template artifact, update the root README's relevant section. If a third category emerges (e.g. shell snippets, prompt fragments), give it its own section rather than overloading "Lessons."
