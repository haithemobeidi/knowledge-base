# Claude Code Project Template

A session protocol for Claude Code that lets each new session pick up a project as if the same person had never left: one rolling state doc, an append-only handoff log, a moment-of-event ledger, a hook-enforced codebase index, and rules for two sessions working on two versions of the same app at once. Extracted from a desktop + mobile product after ~120 sessions and ported to six repos; every rule traces to a measured failure.

## Two layers

```
Knowledge Base repo (this folder)                 Each project repo
─────────────────────────────────────             ─────────────────────────────────────
global/WORK_STYLE.md        ──@import──▶  ~/.claude/CLAUDE.md   (every session, every project)
global/WORK_STYLE_DETAIL.md   (read on demand)
global/PROTOCOL.md          ──@import──▶  ~/.claude/CLAUDE.md
global/commands/start.md    ──copy────▶  ~/.claude/commands/   (project copies win if present)
global/commands/end.md
install-global.py             ← run once per machine, rerun after each KB pull

project/CLAUDE.md           ──copy────▶  <repo>/CLAUDE.md      what is DIFFERENT about this app
project/.claude/protocol.json ─copy───▶  <repo>/.claude/       the scripts' settings (edited per project)
project/.claude/scripts/    ──copy────▶  <repo>/.claude/       byte-identical; drift-checked against here
project/.claude/settings.json, agents/
project/docs/*.md, DECISIONS.md, .gitignore.template, .mcp.json.template
```

- **Global** = how the user works (any app) + the session lifecycle. Lives here, imported live, so a `git pull` of the Knowledge Base updates every project on the machine.
- **Project** = identity, stack, layout, project rules, explicit overrides, and one settings file. Copied in once.
- **Enforcement** (hooks and scripts) stays inside each repo so a fresh clone is protected on day one, but is never hand-edited: everything that differs per project is in `protocol.json`, and `check-template-drift.py` reports when a repo falls behind this template.

## Install the global layer (once per machine)

From the Knowledge Base clone (any folder name, any machine — the script finds its own location):

```bash
git pull --ff-only
python claude-project-template/install-global.py            # install / refresh
python claude-project-template/install-global.py --check    # is it current?  (prints OK)
python claude-project-template/install-global.py --uninstall
```

New machine from zero: clone the KB repo (`github.com/haithemobeidi/knowledge-base`), `cd` into it, run the two commands above. That is the entire setup.

It writes a managed block into `~/.claude/CLAUDE.md` (two `@import` lines pointing at this folder, plus the KB path) and copies `start.md` / `end.md` into `~/.claude/commands/`. Anything else in `~/.claude/CLAUDE.md` is left alone. Restart open sessions afterwards. **After each `git pull` of the Knowledge Base, rerun it** — the imports are already live, but the command copies are not.

If a project session starts without the global layer, the start hook says so loudly before anything else.

## Bootstrap a new project (agent procedure)

> **If you are an AI agent** and the user says "copy the KB over", "set this project up with the template", "bootstrap from the Knowledge Base", or anything equivalent: follow this exactly.

1. **Global layer first.** Run `install-global.py --check`; if not current, run the installer and tell the user to restart the session after bootstrap.
2. **Copy `project/` only** — never the whole template folder, never the lesson files.
   - PowerShell: `robocopy "<KB>\claude-project-template\project" . /E /XD .git`
   - Bash/macOS/Linux: `cp -r "<KB>/claude-project-template/project/." .`
3. **Ask one question if the stack is unknown:** "What stack is this project (and does it have more than one version, e.g. desktop + mobile)?"
4. **Fill `CLAUDE.md`** — replace every `<TODO>`: identity, locked stack, layout, how to run, project rules. Delete the Tracks section for a single-version app. Leave Overrides empty unless the user names one.
5. **Fill `.claude/protocol.json`** — `check_command`, `audit_command`, `push_policy` (ask unless the user pre-authorises and you record it in `DECISIONS.md`), `index_skip_prefixes` (generated dirs), and `tracks` + `shared_paths` for a multi-version app.
6. Rename `.gitignore.template` → `.gitignore` and append project ignores. If the project uses Cloudflare, rename `.mcp.json.template` → `.mcp.json` and follow its comments; otherwise delete it.
7. `docs/CURRENT_STATE.md`: fill the NEXT ACTION line. Leave the other docs as shipped — they grow at `/end`.
8. **Verify the hooks fire** (do not assume): Write a throwaway `tmp-hook-check.md`, read `.claude/pending-index-updates.txt` — it must list the file. Delete both. Run `python .claude/scripts/check-template-drift.py` — it must say up to date. If either fails, see Troubleshooting.
9. Initial commit: `Bootstrap project from claude-project-template`. Push only if asked.

Lessons in the Knowledge Base root are **not** loaded at bootstrap. Pull one in when the work maps to it (the `kb` agent does this), not before.

## The project file (`CLAUDE.md`)

The outline in `project/CLAUDE.md` has eight optional sections: what this is · locked stack · where the code is · tracks · how to run · project rules · overrides · where things live. Every line in it must pass three tests:

1. **Contradicts a global rule?** → it belongs in *Overrides*, naming the rule, the replacement, the reason, and the date. Nowhere else.
2. **Actionable?** → a trigger and an action. "Make it feel premium" is not a rule; "when editing user-facing copy, no em-dashes" is.
3. **Specific to this app?** → if it would be true in another app it goes in the global work style or the Knowledge Base.

Keep it under ~150 lines. It is the only prose file edited per project.

## `.claude/protocol.json`

| Key | Default | Meaning |
|---|---|---|
| `spine_heading` | `status at a glance` | Heading (substring, case-insensitive) that opens the ROADMAP status table |
| `check_command` | `""` | Run at `/end` Step 0c; non-zero stops the wrap |
| `audit_command` | `""` | Run at start; mentioned only on findings |
| `push_policy` | `ask` | `standing` pre-authorises session-end pushes (record it in DECISIONS.md) |
| `protected_branches` | `[]` | Branches the start hook refuses to work on, e.g. `["main"]` in a fork whose `main` mirrors upstream |
| `upstream_ref` | `""` | Fork only: a ref like `upstream/main`; the start hook fetches it and reports the drift count (never acts on it); the statusline shows `upstream +N` |
| `secret_scan` | `true` | Content-based secret scan at `/end` |
| `index_skip_prefixes` | `[]` | Extra paths the index hook ignores (generated code) |
| `ledger.item_max_chars` | `600` | Hard cap per ledger item; the start hook truncates over it |
| `ledger.open_soft_max` | `30` | `/end` reports when exceeded and offers triage |
| `ledger.stale_after_days` | `45` | Older open items listed at `/end` as route-or-close |
| `ledger.prune_closed_after_days` | `7` | Struck lines older than this are pruned |
| `tracks` | `[]` | Parallel tracks: `{name, prefix, owns[], aliases[]}` each (aliases = words your old docs use for it, e.g. `android` for `mobile`) |
| `shared_paths` | `[]` | Paths every track may edit, with an announcement |

## Parallel tracks — desktop and mobile side by side

Two sessions, one checkout, one branch, on purpose: they see each other's work instantly and the mobile build tests against the server the desktop track deploys. The rules that make it safe (full text in `global/PROTOCOL.md`):

- Each session **declares its track** before touching anything; the start hook gates on it.
- **IDs are prefixed per track with independent counters** (`D-12`, `M-3`), so two writers never collide. A tag `→mobile` / `→all` right after the ID says who acts on an item; legacy items are tagged once at migration.
- Each track **edits only its owned paths plus shared paths**; shared changes are announced with a tagged ledger line; deploy state lives in CURRENT_STATE's Shared block.
- The other session's uncommitted files are **left alone and reported**; the stop hook tolerates them only inside that track's owned paths; `git add -A` is forbidden.
- **A push publishes the whole branch** — commits that are not yours are named in the report.
- CURRENT_STATE has one NEXT ACTION per track; handoff lines carry the track; the cross-check uses your track's last line.

## What the ledger is and isn't

The ledger holds open loops a future session must act on — queued tests, gates, riders, deferred decisions — written **at the moment** they arise. It is not for bugs, feature ideas, or status (those have their own homes), and not for analysis: an item is capped at 600 characters, the analysis goes to a linked doc. The start hook injects only open items, truncated at the cap, grouped by track, and lists what is stale. Before this cap one project's ledger reached 99 open items averaging 2,500 characters and injected ~250KB at every session start.

## Troubleshooting

**Hooks don't fire** (writing a file leaves `pending-index-updates.txt` empty): (1) `python --version` inside Claude Code's shell — the hook commands invoke `python` literally; (2) `python -c "import os; print(os.environ.get('CLAUDE_PROJECT_DIR'))"` — empty means the harness didn't set it (launched outside the project root, or a wrapper stripped it), and every script silently no-ops; (3) run a hook by hand with a synthetic event (see MIGRATION.md §6); (4) confirm the matcher in `.claude/settings.json` is `Write|Edit`.

**"Global rules not installed"** at session start: run the installer for this machine (the path is in the message), restart.

**Template drift reported**: `python .claude/scripts/check-template-drift.py` lists the files; `--sync` copies the template's versions in (after the user agrees). If the project's version is a genuine improvement, upstream it here instead.

**Worktree guard trips every session**: Claude Code Desktop force-creates worktrees; use the CLI from the project root, or the desktop workaround in `/start`.

**`/end` finds unindexed paths the hook should have caught**: Step 1b is the backstop doing its job; add the rows and note the miss in CURRENT_STATE.

## Migrating an existing project

See [`MIGRATION.md`](./MIGRATION.md). One session, not concurrent with another session in the same checkout.

## What's opinionated vs generic

| Layer | Opinionated? | Notes |
|---|---|---|
| Work style (pause-points, mock-first, grounded both ways, user-clickable tests) | Yes | The user's way of working; edit `global/WORK_STYLE.md` to taste |
| Code quality caps (500/800, DRY at 3, no `utils/`) | Yes | Standing preferences |
| Session lifecycle, ledger, index hook, clean-tree guard | Mostly generic | The shape works for any solo long-horizon project |
| Spine as single source of truth + cross-check + frozen numbers | Generic | Costs nothing until a roadmap exists |
| Parallel tracks | Generic | Inert until `tracks` has two entries |
| Worktree guard | Situational | Only if Claude Code Desktop keeps spawning worktrees |

## Where to remember things

| Place | Auto-loaded | Use for |
|---|---|---|
| Global work style + protocol (here) | Every session | How we work, in any app |
| Project `CLAUDE.md` | Every session in that repo | What is different about this app |
| Project `DECISIONS.md` | On demand | Why each technical choice was made; standing authorisations |
| Harness memory (`~/.claude/projects/<slug>/memory/`) | Index every turn | Corrections and validated approaches for this user on this project — never app status |
| Knowledge Base lessons (repo root) | On demand via the `kb` agent | Transferable lessons, `*kbdoc`-tagged and written after `/end` |

## Provenance

Extracted 2026-04-20 from a Tauri 2 + Cloudflare desktop app; resynced 2026-07-24 (ledger, drift-audit fixes). **Restructured 2026-09-08** into the global/project layers: work style and protocol moved out of the per-project copies into imports; scripts made generic behind `protocol.json`; parallel-track rules, ledger caps, content-based secret scan, template-drift check, and the installer added. The source projects' later evolutions (build guard at `/end`, spine-cell brevity, secret scan) were folded in at the same time. **2026-09-11** (from the first fork-with-a-device migration): `protected_branches` + `upstream_ref` for forks; the index queue is written LF-only on Windows; the ledger reader skips HTML comment blocks (the header's example items used to be counted as open).
