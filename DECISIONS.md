# Knowledge Base — Decisions

Append-only log of why this knowledge base is shaped the way it is. Newest entries at the bottom. Never rewrite past entries — supersede with a new one if a decision changes.

---

## 2026-04-20 — Extract `claude-project-template` from the source project

**Decision:** Snapshot the source project's `.claude/`, root `CLAUDE.md` / `PROTOCOL.md`, and `docs/` skeleton into `claude-project-template/` here.

**Why:** The source project (a Tauri 2 + Cloudflare Worker desktop app) had stabilized the session protocol (CURRENT_STATE overwrite, HANDOFF_LOG append, hook-enforced index, worktree guard, /start + /end). Re-deriving these for every new project was wasted ceremony. Canonical source of truth: this template; resync upstream when conventions meaningfully evolve.

**How to apply:** New projects start by copying this template wholesale, then customizing `<ProjectName>` / `<TODO>` markers. The template is *not* a generator — it's a paste-and-edit skeleton.

---

## 2026-04-13 — Canonize Tauri OAuth lesson

**Decision:** Promote the localhost-callback + bearer-token Tauri OAuth pattern into a standalone `tauri-desktop-oauth.md` lesson.

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

---

## 2026-05-03 — De-hardcode personal paths

**Decision:** Replace absolute Windows paths in `claude-project-template/README.md` and `tauri-desktop-oauth.md` with `$KB_TEMPLATE_DIR`-style env-var instructions and stack-relative descriptions.

**Why:** Hardcoded paths break silently when the KB moves or when someone other than the original author reads the lesson. The robocopy command in particular would `success` while copying nothing useful.

**How to apply:** Any future doc that needs to reference a path outside this repo gets an env var or a "the path is environment-specific" note. Never paste an absolute Windows path that someone else will execute.

---

## 2026-05-03 — YAML frontmatter on lessons + freshness rule

**Decision:** Each lesson `.md` carries `stack`, `kind` (howto/gotcha/recipe — borrowed from Diátaxis), and `last_verified` in frontmatter. Root README documents the rule.

**Why:** KBs rot when last-verified dates aren't tracked. Frontmatter is the cheap version of an index — readable by humans, future-MCPs, and `Grep`. Diátaxis split into subfolders is overkill for 3 files; revisit at ~10.

**How to apply:** New lesson? Add the frontmatter. Reread an old lesson and it's still right? Bump `last_verified`. Edit the recipe? Bump it in the same commit.

---

## 2026-05-03 — Ship `.mcp.json.template` with Cloudflare bundle

**Decision:** Add `.mcp.json.template` (opt-in, disabled-by-default) to the project template. Wires up Cloudflare's Workers Bindings, observability, and Browser Rendering MCP servers. Two additional servers (filesystem, sequentialthinking) included as commented-out examples.

**Why:** The Cloudflare MCP bundle is the single highest-ROI MCP for this stack — Claude can introspect live D1/R2/KV state and tail Worker logs without paste-paste-paste. Shipping disabled-by-default avoids surprising users with browser OAuth prompts on first launch.

**How to apply:** Each new project decides whether to enable. Rename to `.mcp.json`, comment out servers you don't want, restart Claude Code. First call to a CF server triggers OAuth.

---

## 2026-05-03 — Add Prerequisites + Troubleshooting to template README

**Decision:** Document `CLAUDE_PROJECT_DIR` as a harness contract that all four hook scripts depend on. Add a "hook didn't fire?" diagnostic ladder.

**Why:** Audit found that all four scripts silently no-op when `CLAUDE_PROJECT_DIR` is unset. Harness sets it, but if a wrapper / IDE plugin strips it, hooks vanish without output. Users won't know index tracking failed until they accumulate untracked files. Documenting the contract + giving a 5-step diagnostic is cheaper than refactoring the scripts to log loudly (which would compete with Claude Code's stdout).

**How to apply:** Future hook scripts that depend on env vars get the same treatment — document the dependency, add a one-liner diagnostic.

---

## 2026-05-03 — Add agent-readable bootstrap procedure to root README

**Decision:** Add an "Agent instructions — copying this into a new project" section at the top of the KB root README. Lists trigger phrases, a 7-step bootstrap procedure, and explicit "do not copy lessons / do not auto-load lessons" rules.

**Why:** The right workflow is "open Claude Code in a new project, point it at the KB, say 'copy the KB over.'" That requires Claude to read a procedure on arrival. Without one, each project's bootstrap drifts based on the prompt the user remembers to type. Putting it in the README means every time Claude lands in the KB it sees exactly what to do — no guessing, no token-waste on lessons that don't apply.

**How to apply:** When bootstrapping a new project, the user only needs to say "copy the KB over" (or any of the listed trigger phrases). Claude reads the README, runs the procedure, asks one stack question, customizes accordingly. Lessons stay parked unless explicitly pulled in.
