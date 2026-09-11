# Migrating an existing project to the layered protocol

For a repo that already runs an older copy of this protocol (its own `PROTOCOL.md`, `docs/WORK_STYLE.md`, `.claude/commands/`, hand-edited scripts), or an older generation (`start-session`/`end-session` commands, a `handoff/` folder). One session, one repo, done in order. **This is a one-time migration that must not run while another session is open in the same checkout** — it renumbers nothing, but it rewrites state docs and the ledger header, and two writers would collide.

## 0 — Preconditions

- The user has confirmed no other session is running in this checkout.
- `git status --porcelain` is empty, or every dirty path has been categorised with the user (commit / stash / leave-as-other-track's).
- The Knowledge Base clone on this machine is pulled: `git pull --ff-only`.
- The global layer is installed: `python "<KB>/claude-project-template/install-global.py" --check` says OK. If not, run it without `--check` and restart the session.

## 1 — Drop in the new machinery

Copy from `<KB>/claude-project-template/project/`:

- `.claude/scripts/*` → overwrite the project's scripts (they are now generic; anything project-specific they used to carry moves to `protocol.json` in the next step).
- `.claude/settings.json` → overwrite, unless the project added hooks of its own; then merge and keep them.
- `.claude/agents/*` → add or overwrite.
- `.claude/protocol.json` → add, then **fill it from what the old files carried**:

| Key | Where it used to live |
|---|---|
| `check_command` | old `end.md` Step 0c (e.g. `pnpm check`) |
| `audit_command` | old `start.md` audit step (e.g. `pnpm audit --prod`) |
| `push_policy` | old `PROTOCOL.md` Step 4 / `DECISIONS.md` standing-push entry → `standing`; else `ask` |
| `index_skip_prefixes` | old `track-new-file.py` SKIP_PREFIXES additions + old `end.md` Step 1b ignore list |
| `protected_branches` / `upstream_ref` | a fork's old start hook: the branch it refused (`main`) and the second remote it fetched (`upstream/main`) |
| `spine_heading` | the string the old `session-start-context.py` matched (default `status at a glance` matches "📊 v1 status at a glance" too) |
| `ledger.*` | defaults, unless the user wants different caps |
| `tracks` / `shared_paths` | from the repo layout — confirm with the user: which top-level paths each version of the app owns, and which are shared (core packages, server, docs). Give each track the `aliases` your existing handoff lines and ledger items use for it (e.g. `"mobile"` with aliases `["android", "phone"]`), so the start hook can match legacy lines by text from day one. |

## 2 — Remove the project copies of what is now global

Before deleting, skim each for **project-specific** content and move it: rules → `CLAUDE.md` "Project rules"; settings → `protocol.json`; incidents worth keeping → `DECISIONS.md`.

```bash
git rm PROTOCOL.md docs/WORK_STYLE.md .claude/commands/start.md .claude/commands/end.md
```

(Older generation: also `docs/SESSION_PROTOCOLS.md`, `.claude/commands/start-session.md`, `end-session.md`, `work-session.md`. Leave a `handoff/` folder as frozen history; nothing reads it.)

The global `/start` and `/end` take over the moment the project copies are gone (project-level commands win while they exist).

## 3 — Rewrite `CLAUDE.md` to the outline

Use `project/CLAUDE.md` as the shape. Keep: identity, locked stack, layout, how to run. **Move out** every work-style section (pause-points, mock-first, don't-reinvent, grounded pushback, kbdoc) — they are global now; keep only the project-specific line each one carried (where the prototype lives, which device to test on, the reference repos). Put explicit deviations in the Overrides table with a date and a reason. Target under 150 lines.

## 4 — Ledger

- Replace the header block of `docs/SESSION_LEDGER.md` with the template's (worthiness test, size cap, ID scheme). Items below the header are untouched.
- **Multi-track:** from now on mint with the track prefixes and independent counters (`D-1`, `M-1`). Legacy `L-` IDs stay forever. Add a one-line note under the header: "Items before <date> use the shared `L-` counter; see the ID rule above."
- **Multi-track — tag every open legacy item once (this is what makes the old items per-track).** The start hook groups items by ID prefix or by a `→track` tag; untagged `L-` items land in "unassigned" for BOTH sessions. So, for each open `[ ]` line, insert `→desktop`, `→mobile`, or `→all` **right after the ID** (`- [ ] L-423 →mobile (2026-08-29, …)`), touching nothing else on the line. Propose the tag from the item's own text (mentions of the mobile platform, "phone", the store, "/Android" → `→mobile`; the desktop app, its release numbers, "/desktop" → `→desktop`; "both clients", "parity", "cross-client", server or shared-schema changes → `→all`), then show the user ONE table (ID · first 80 chars · proposed tag) and let them correct it before writing. Ambiguous → `→all`, never guess a single track. Closed lines are not tagged. Nothing else about the item changes, so every open loop keeps its place.
- **One-time triage** (the part the caps make necessary): for each open item over `item_max_chars`, move its analysis to the bug doc, the backlog, `docs/notes/<ID>.md`, or a DECISIONS entry, and cut the ledger line down to the loop + a pointer. Then, with the user in one sitting, route or close every item older than `stale_after_days` and everything that fails the worthiness test. A plain-language review lens (one table per "needs your decision / needs your hands / I can just do it") works well; delete it when done.

## 5 — State docs

- `docs/CURRENT_STATE.md`: multi-track → one NEXT ACTION section per track plus a Shared block (deploy state, migration numbers). Single-track → unchanged.
- `docs/HANDOFF_LOG.md`: from now on the track is the second field in multi-track repos. Do not rewrite old lines. Older generation: seed CURRENT_STATE from the newest handoff file, then leave the folder alone.
- `ROADMAP.md` spine: add `⬅ CURRENT (<track>)` markers if the tracks are at different points; move any cell over ~1,500 characters into an archived history section below the table (the hook warns on bloated cells).
- `docs/CODEBASE_INDEX.md`: older generation only — convert to the `| \`path\` | purpose |` table the validator parses; add rows for the new `.claude/` files.

## 6 — Verify before trusting it

```bash
# hooks, manually
CLAUDE_PROJECT_DIR="$(pwd)" python .claude/scripts/session-start-context.py | head -c 3000
echo '{"tool_name":"Write","tool_input":{"file_path":"'"$(pwd)"'/tmp-hook-check.md"}}' | CLAUDE_PROJECT_DIR="$(pwd)" python .claude/scripts/track-new-file.py && cat .claude/pending-index-updates.txt
python .claude/scripts/check-template-drift.py        # must say up to date
python .claude/scripts/scan-secrets.py --history      # once, on migration
```

Remove `tmp-hook-check.md` and its pending line. Then start a fresh session and confirm the injected context shows the tracks (if any), the track gate, and the grouped ledger.

## 7 — Commit

Single track: `Session: protocol migrated to the global layer`. Multi-track: `Session (<track>): …`. Push per `push_policy`. Record the migration in `DECISIONS.md` (one entry: what moved where, the caps chosen, the tracks declared).
