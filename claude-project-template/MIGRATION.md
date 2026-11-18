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
echo x > tmp-hook-shell.md && echo '{"tool_name":"Bash","tool_input":{"command":"echo"}}' | CLAUDE_PROJECT_DIR="$(pwd)" python .claude/scripts/track-new-file.py && cat .claude/pending-index-updates.txt   # the shell half: an untracked file queued
python .claude/scripts/check-template-drift.py        # must say up to date
python .claude/scripts/scan-secrets.py --history      # once, on migration
```

Remove `tmp-hook-check.md` and its pending line. Then start a fresh session and confirm the injected context shows the tracks (if any), the track gate, and the grouped ledger.

## 6b — v1 document shapes → v2 (the budgeted shape)

Separate from the layering migration above, and safe to do later. A project on `protocol_version: 1` keeps working indefinitely; v2 is opt-in per project.

**Do not run this while another session is open in the same checkout.** Use `--out <dir>` outside the repo if one is.

```bash
python .claude/scripts/check-template-drift.py --sync     # get the v2 scripts first
python .claude/scripts/migrate-docs-v2.py --report        # triage table only, writes nothing
python .claude/scripts/migrate-docs-v2.py                 # writes docs/*.new.md
```

The script does the mechanical half and refuses the rest:

- **Session narrative → handoff entries**, joined on the session ordinal ("153rd"). A block with no matching handoff line is reported and left in place, never guessed at and never summarized.
- **Closed ledger lines → `SESSION_LEDGER_CLOSED.md`**, moved, not deleted.
- **Everything awaiting a ruling** (the Shared block, "things to watch", loose ends) is parked **verbatim** in the archive under "Parked pending a ruling". It prints a numbered table; each bullet is (K) a standing fact that goes back into CURRENT_STATE, (L) a live loop that becomes a ledger item, or (A) history that stays parked. Take it to the user as one table, the same way the legacy `→track` tags were done in §4.
- It prints a **conservation check** — characters that left CURRENT_STATE versus characters that arrived in the archive. A large positive delta means something was dropped rather than moved; do not use that output.

Then, by hand: apply the rulings, fill CURRENT_STATE's new **Shipped** section (it has no v1 source), replace the originals with the `.new.md` files, and **only then** set `protocol_version: 2`. The script never flips it, because rendering unmigrated documents in the v2 shape just renders them differently.

Finally: `python .claude/scripts/check-payload-budget.py`. Over budget after migrating usually means the ledger's open count, not the documents — shrink the contributor, never the budget.

## 6c — Delivery in parts (template 2026-10-20)

For any project already on the template, v1 or v2. Claude Code caps one hook string at 10,000 characters, so a settings.json that wires the start hook once delivers a 2,000-character preview of anything larger. The fix is in the template-managed files; nothing in the documents changes.

```bash
python .claude/scripts/check-template-drift.py          # expect settings.json + the scripts to differ
python .claude/scripts/check-template-drift.py --sync   # after the user agrees
python .claude/scripts/check-payload-budget.py          # now prints a Delivery block: parts, entries wired, ceiling
```

Then in `.claude/protocol.json` (project-owned, not synced):

- `payload.max_gating_items` is now **per NEXT ACTION section**. A five-track project at the old value of 5 expands up to 25 items; 3 is a sane start there. `payload.gating_item_max_chars` (1,200) caps each expansion.
- v2 projects may delete `ledger.item_max_chars`; `ledger.prune_closed_after_days` is `move_closed_after_days`.
- A track whose work never touches the build (a marketing kit, a docs track) gets `"check_command": ""` in its `tracks` entry; a track with its own build gets its own command. Absent = the repo-wide one.
- `index_skip_suffixes` if the repo carries file types beyond the built-in binaries and media that must never become index rows.

Verify in a fresh session: the context arrives as "part n of m" strings, part 1 carries the directive and a `Payload: N chars in M part(s)` line, and `/compact` is followed by the slim rules reminder.

## 6d — Load by track, the budget gate, the lessons queue (template 2026-11-12)

For any project already on the template. **Nothing in the project's documents has to change**, there is no version to flip, and the sync does the adoption itself. Run it in the project, in its own session, with no other session open in the checkout:

```bash
git -C "<KB>" pull --ff-only && python "<KB>/claude-project-template/install-global.py"   # /start and /end
python .claude/scripts/check-template-drift.py --sync      # after the user agrees
python .claude/scripts/check-template-drift.py --adopt     # this ONE time only: the copy that did the sync predates adoption
```

`--adopt` (which later syncs run by themselves) adds `docs/LESSONS_QUEUE.md` if the project has none, and — once per project — records the budget gate in `protocol.json`: a payload already over the budget gets a ceiling at today's size, a project inside it gets an empty `payload.ceiling_chars`. It prints anything left for a person as the exact command. Usually that is one line:

```bash
python .claude/scripts/ledger-archive.py --lessons           # dry run: the open `kbdoc:` items
python .claude/scripts/ledger-archive.py --lessons --apply   # whole text → the queue; a struck stub keeps each ID
```

Then commit `.claude/`, `docs/LESSONS_QUEUE.md` and (if lessons moved) `docs/SESSION_LEDGER.md`.

What changes, by project shape:

| Project | After the sync |
|---|---|
| Single track, v1 or v2 | The start payload is byte-for-byte what it was. `/end` Step 3b is now a gate; a project inside the budget never notices. |
| Two or more tracks, v2 | The hook injects one small part (sync result, track list, directive). Each session runs `session-start-context.py --track <name>` and loads its own track. `settings.json` goes back to the template's 8 `--part` entries — a project that raised it by hand no longer needs to. |
| Two or more tracks, v1 | Unchanged until it migrates to v2 (§6b). |

Verify in a fresh session on a multi-track project: the hook context says "This repo loads by track", the session runs the `--track` command after the track is named, and the first line of that output states the payload against the budget. `python .claude/scripts/check-payload-budget.py` prints one line per track.

**What a correct run looks like** (from the first real one, a five-track project at 307% of budget, 2026-11-12): `--sync` printed six `synced …` lines; `--adopt` printed `added docs/LESSONS_QUEUE.md`, one `Ceiling: <track>: ceiling set at N (payload M)` line per track with each ceiling 500 to 1,000 above its payload, and under "Left for you" the lessons command with eleven IDs; `settings.json` went from 10 `--part` entries back to 8; per-track payloads came out at 34,000 to 43,000 against 76,800 before. Still being over the 25,000 budget after adoption is expected and is not a failure — see the last paragraph.

**In the first fresh session afterwards, check three things:** (1) the hook's notes say "This repo loads by track" and carry no track's state; (2) once the track is named, the session runs `session-start-context.py --track <name>` **before** any other read or edit — this step depends on the model following the directive, and is the one thing a rehearsal on copied documents cannot prove; (3) its report gives a payload line and, when there are `DECIDE:` items, lists them as "Your calls". If a session skips (2), that is a finding about the directive's wording in `session-start-context.py`: record it and fix it in the template, not in the project.

**If something is wrong:** every step is a file change in the project's working tree, so `git diff` shows it and `git checkout -- .claude/` undoes an uncommitted sync. `--adopt` and `--sync` are safe to rerun (adoption happens once: it is recorded by the `payload.ceiling_chars` key in `protocol.json`, even when empty). `--init-ceiling` does nothing after adoption, by design. A ceiling that needs raising is the user's decision: edit the number by hand and record why in DECISIONS.md.

**This is per project, not per machine.** Run it once, from any machine, commit and push; the other machine pulls the project. Each machine separately needs the KB pull + `install-global.py` (the first line of the block above), once. The table in `README.md` → "Rolling out a template change" has the whole split.

**Rollout as of 2026-11-12** (check `grep -c init-ceiling .claude/scripts/check-payload-budget.py` in a project: 0 = not yet synced): Checkpoint synced and adopted. BuddySystem (three tracks) is the only other project whose session start changes. The single-track projects (Cove, Cove-ACS-Expert, Zendesk-Copilot, armada-astra2, armada-odin3, final-fantasy-resonance-ultrawide, Interview-Prep, Nuveen-Reporting, Stash, Tagsmith, Texsmith) can sync at any quiet point: their session start is byte-for-byte unchanged and they gain only the `/end` gate and the lessons queue.

**Getting an over-budget project under the budget is a separate sitting, and it is the user's.** The ceiling stops growth; it does not shrink anything. `check-payload-budget.py --all` shows what each track loads. The usual three, largest first: (1) what sits in CURRENT_STATE outside the NEXT ACTION sections is paid for by every track — move standing reference facts to a doc that is read on demand; (2) items tagged `→all` are in every track's payload — retag for the tracks that act; (3) items that are really ideas, facts or pending rulings — route them, or retitle `DECIDE:` and take the list to the user as one table. Since 2026-11-18 the template has a tool for each of the first two and parking for items that wait on an event — §6e.

## 6e — Shared state with an exit, one owner per item, parked items (template 2026-11-18)

Answers Checkpoint's D-106 second round ("fixed for good", user, relayed 2026-11-18): the 2026-11-12 ceilings held every track still and nothing shrank. Three changes, all enforced by the `/end` gate (PROTOCOL.md "Why this exists" #11):

1. **CURRENT_STATE outside the NEXT ACTION sections** — a bullet that is one track's state starts `- →<track>` and only that track loads it; the untagged bullets of the accumulating sections (Shared services and the like) are capped at `state.shared_max_chars` (5,000), and `/end` Step 2 runs `state-archive.py`, which moves the oldest to `docs/CURRENT_STATE_ARCHIVE.md` (never loaded). Blocker sections and Shipped / Build status are never counted or moved.
2. **One owner per item** — `protocol.json` → `shared_owner` names who owns problems on shared paths; new items are not tagged `→all` (the gate stops it from the wrapping track; `--track <name>` on the gate says which track that is).
3. **Parked items** — `[~]` + `→ PARKED <date> until <event>`, counted by event at session start instead of listed; `ledger-archive.py --park / --unpark / --parked`.

**What changes, by project shape.** Single track, or v1: the start payload is byte-for-byte what it was (verified on Cove, Zendesk-Copilot, armada-astra2, Tagsmith, Interview-Prep); the only new rule is that a parked item must name its event (and on v1 a parked item stays listed, marked — v1 has no manifest heading to count it in). Multi-track v2 (Checkpoint, BuddySystem): on documents that use none of the new syntax the `--track` output is also byte-identical (verified on all five Checkpoint tracks and all three BuddySystem tracks) — but the gate now stops a wrap whose shared block is over its cap, so the first sync is followed by a cleanup.

**The sync** — the §6d commands (KB pull + `install-global.py` on the machine; `check-template-drift.py --sync` in the project). One `--sync` is enough: the project's old copy syncs the files it knows, hands over to the new copy, and that one prints `added .claude/scripts/state-archive.py (new in the template)` and, when the shared block is over its cap, the state step under "Left for you". (Rehearsed on a copy of Checkpoint, 2026-11-18. A sync whose output has no `added … state-archive.py` line was run by a copy older than 2026-11-12: run `--sync` once more.)

**The cleanup, once, in the project's own session, in this order** (every step has a dry run; read it before `--apply`):

1. **Tag the per-track bullets** outside the NEXT ACTION sections: `- →<track> **…**`. Build status and Shipped rows are usually all one track's each (the script never moves them; tagging is what stops every track paying for them). A bullet several tracks act on names them (`- →desktop/android`).
2. `python .claude/scripts/state-archive.py` — read the list: anything in it that is one track's state goes back to step 1; a standing ruling is fine to move (it is in DECISIONS.md); a hazard warning ("never rotate X") moves to the project `CLAUDE.md`'s rules, which every session loads. Then `--apply`.
3. **`shared_owner`** in `protocol.json` — which track owns problems on the shared paths (one name, or per path). **The user's call.**
4. **Retag the `→all` items:** a problem on a shared path → its owner; work several tracks must each do → those tracks by name; an announcement nobody must act on → close it and keep the fact, stamped, in Shared services. Dispositions of another track's items are the user's to rule — bring them as one table.
5. **Park** what waits on a named event: `python .claude/scripts/ledger-archive.py --park <IDs> --until "<event>" --apply` (works with uncommitted ledger edits; the note goes right under each ID line). `--parked` shows the result grouped by event.
6. `python .claude/scripts/check-payload-budget.py --strict --ratchet --track <yours>` exits 0; `--ratchet` lowers every track's ceiling to its new size and removes the ceilings of tracks now inside the budget. Commit `.claude/protocol.json`, `docs/CURRENT_STATE.md`, `docs/CURRENT_STATE_ARCHIVE.md` and `docs/SESSION_LEDGER.md` together.

**What to expect** — a rehearsal on a copy of Checkpoint's documents of 2026-11-18 (origin/main `94cc92ef`), with *simulated* dispositions (the real ones are the user's): the 10 per-track Build status / Shipped rows tagged, `state-archive.py --apply` (15 Shared services bullets moved, 9,035 → 4,828), 38 `→all` items retagged to their writer's track, 31 desktop/Android items not cited by a NEXT ACTION parked "until the iOS prototype works" (open 122 → 91 + 31 parked). Per-track payload before → after: desktop 43,340 → 32,667 · android 41,835 → 30,396 · ios 34,975 → 22,629 · steamos 35,734 → 23,693 · social 40,944 → 28,275; `--ratchet` lowered three ceilings and removed ios's and steamos's. Steps 1–2 alone: 37,103 / 35,742 / 27,867 / 28,758 / 33,365. What is left over budget on desktop, android and social is mostly their own NEXT ACTION sections and their own open items — the ordinary work of closing what is done.

**In the first fresh session afterwards, check:** (1) the `--track` output says how many bullets for other tracks it left out and points at `docs/CURRENT_STATE_ARCHIVE.md`; (2) the ledger heading counts parked items by event; (3) the wrap runs `state-archive.py` at Step 2 and the gate with `--track`. A machine that has not rerun `install-global.py` has the old `/end`: it skips `state-archive.py`, and the new gate stops the wrap with a message naming that command — follow it, then rerun `install-global.py` on that machine.

**If something is wrong:** every step is a file change; `git diff` shows it. A bullet moved by mistake is copied back from the archive (append-only — leave the archive copy). `--unpark` reverses `--park`. Raising `state.shared_max_chars` is raising what every session pays: the user's decision, a DECISIONS.md entry.

## 7 — Commit

Single track: `Session: protocol migrated to the global layer`. Multi-track: `Session (<track>): …`. Push per `push_policy`. Record the migration in `DECISIONS.md` (one entry: what moved where, the caps chosen, the tracks declared).
