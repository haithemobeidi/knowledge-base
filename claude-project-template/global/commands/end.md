# /end — Session End Protocol

Wrap up the development session cleanly. **Execute every step in order. Do not skip.** Applies only to repos with `.claude/protocol.json` (or `docs/CURRENT_STATE.md`); otherwise say so and stop.

Read `.claude/protocol.json` once at the top: `check_command`, `secret_scan`, `push_policy`, `ledger` caps, `file_caps`, `tracks`, `shared_paths`. In a multi-track repo, you declared your track at start; every step below is scoped to it.

**No new work during `/end`.** A user message that arrives mid-wrap is a note or a question: answer briefly or fold it into the docs; do not build.

## Step 0a — Worktree guard (FAIL FAST)

```bash
pwd
git rev-parse --abbrev-ref HEAD
```

If the cwd contains `.claude/worktrees/` OR the branch starts with `claude/`, **STOP**. Do not `/end` from a worktree — it would pollute the handoff log with a `claude/<name>` branch merge. Tell the user to quit without ending (work on disk is preserved) and restart in the main checkout via the CLI. Do not silently fast-forward `main` from a worktree branch.

## Step 0b — Clear phantom-dirty files

```bash
git update-index --really-refresh > /dev/null 2>&1 || true
```

Stale mtimes (a pull, an editor touching files) make git flag unchanged files as modified. This drops only entries byte-identical to HEAD.

## Step 0c — Project check + secret scan (FAIL FAST)

Run the check command: in a multi-track repo, your track's own `check_command` from its `tracks` entry when it declares one (`""` means this track has no check — a marketing kit or docs track that never touches the build), otherwise the repo-wide `check_command`; if you touched `shared_paths`, run the repo-wide one as well (e.g. `pnpm check`: build freshness, contract drift, typecheck). **Non-zero exit → STOP.** Report the failure and fix it, or get an explicit override, before continuing. A tree that fails this guard has silent drift; do not commit and push it.

If `secret_scan` is true (default), run:

```bash
python .claude/scripts/scan-secrets.py
```

**Findings → STOP.** Do not commit. Move the value into an ignored file or a secret store, leave a `.example` sibling with the value blanked, rotate it if it was ever pushed, re-run until clean. `.gitignore` is a blocklist and only protects paths somebody remembered to list; this scan reads content. (Nested sub-repositories are invisible to it — run it inside them separately.)

## Step 0d — File caps + twins (the mechanical half of the size/DRY rule)

```bash
python .claude/scripts/check-file-caps.py
```

It reads the code files THIS session touched (commits since the last wrap + the working tree) against `file_caps` in `protocol.json`.

- **Over the hard cap (default 800) → STOP.** Split the file by a coherent concept now, or get an explicit override; never shave lines to pass.
- **Over the soft cap (default 500), or a new file that shares its name with an existing one → a `[ ]` ledger line per file, right now**, naming the split candidate or the twin (Step 1d will see it). The wrap RECORDS; the split happens at the next quiet point. Do not split during `/end`.
- **A twin the project repeats by design** (one `routes.js` per feature folder, one folder per post holding copies of the same templates) → not a ledger line: add its pattern to `file_caps.twin_exempt` in `protocol.json` and say so in the handoff, so no later wrap flags it again. A name repeated across clients (desktop's and mobile's own `format.ts`) is never "by design" — that is the twin.
- The judgement half — is anything duplicated, should anything split — runs once per feature close, not per session (global `PROTOCOL.md` → "Feature close"). The mechanical check is what holds the line between those sittings.

## Step 1 — Verify pending index updates

Read `.claude/pending-index-updates.txt`.

- Missing or empty → Step 1b.
- Non-empty → for each path, add a one-line entry to `docs/CODEBASE_INDEX.md` saying what the file does in plain language. Then overwrite the pending file to be empty. **Do not proceed until done.**

## Step 1b — Backstop: diff-based index check

```bash
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

Ignore protocol bookkeeping (`.claude/`, `CODEBASE_INDEX.md`, `CURRENT_STATE.md`, `HANDOFF_LOG.md`, `SESSION_LEDGER.md`), build output, lockfiles, and the `index_skip_prefixes` from `protocol.json`. In a multi-track repo also ignore paths inside the OTHER track's owned paths (they are that session's to index). For each remaining path, check it appears verbatim in `docs/CODEBASE_INDEX.md`. If any are missing: report them (the hook may have failed), add the entries, and note in CURRENT_STATE's watch section that the hook missed N files.

## Step 1c — Phantom-row check

```bash
python .claude/scripts/validate-index.py
```

Remove any reported rows (index entries pointing at files no longer on disk).

## Step 1d — Reconcile `docs/SESSION_LEDGER.md`

Do this **before** writing CURRENT_STATE, so the wrap is written against the ledger rather than end-of-session recall (recall provably loses early-session facts to context compaction).

1. Read the ledger **from disk** (a concurrent session may have edited it).
2. Disposition every `[ ]` item this session touched: `[x]` + `→ DONE <date>: <one line>`, or `[-]` + reason. Untouched items stay `[ ]`. **Never strike an item you merely don't recognise.** Multi-track: only your prefix's lines, plus lines tagged for you or `→all` that you resolved (note "closed by <track>").
3. Append `[ ]` lines for anything this session queued or deferred that isn't captured — scan for "next session", "before release", "check later", riders, gates. Apply the worthiness test (open loop with a done-condition / not tracked elsewhere / can't be done in 10 minutes / one ID per loop), and **route what fails it instead of minting an ID**: an idea → the backlog; a lesson → `docs/LESSONS_QUEUE.md`; a standing fact or a ruling already made → `DECISIONS.md` or CURRENT_STATE; a bug → the bug doc. An item that waits on **the user's ruling** rather than on work starts its title with `DECIDE:` — session start lists those first, as the user's calls. **The first line must be a self-contained TITLE** — it is the only part a future session sees in the manifest, so lead with the headline and put the detail on continuation lines. **There is no length cap**: keep the item whole, here. Multi-track: mint with your prefix; put `→<other track>` right after the ID (`D-9 →mobile (2026-09-09) …`). **One owner, never `→all`:** a problem on a shared path goes to `shared_owner` (protocol.json) or the track that will fix it; work several tracks must each do names them (`→desktop/ios`); a shared change nobody must act on is a stamped Shared fact in CURRENT_STATE, not an item. Step 3b stops a wrap that adds an `→all` item from your track. An item no session can act on until a named event (a lock lifting, a release) is **parked**, not left open: `python .claude/scripts/ledger-archive.py --park <IDs> --until "<event>" --apply`.
4. **MOVE** closed lines to `docs/SESSION_LEDGER_CLOSED.md` — run the script, do not do it by hand:

   ```bash
   python .claude/scripts/ledger-archive.py            # dry run: what would move
   python .claude/scripts/ledger-archive.py --apply
   ```

   **Never delete them.** That file is never injected and may grow forever; an ID cited in a commit subject, a handoff entry or a spine cell has to stay resolvable. (v1 specified this move as prose and it never once ran — 88 closed lines sat in a ledger with a 7-day rule. That is why it is a script.)
5. Count the open items (parked ones do not count). Over `open_soft_max` → **route, park or close the two oldest stale items now** (items past `stale_after_days`), proposing a disposition for each and letting the user rule. If the session start listed parked items whose event has happened, unpark them (`--parked` lists them; `--unpark <IDs> --because "…" --apply`). An item that belongs to another track is handed over with `--retag <IDs> --to <track> --apply` — once the user has ruled, when it was another track's. Two items, not a triage sitting: a level-based cap that has been exceeded for months is not a cap, and a rate you would not bother skipping is.

## Step 1e — `check-ledger-refs.py` (the copy-forward guard)

```bash
python .claude/scripts/check-ledger-refs.py
```

Every ledger ID cited in `CURRENT_STATE.md` and the spine, classified open / struck / absent. Read each **struck** line and decide: does it still describe the item as pending (fix it in Step 2), or as history (correct as written, leave it)? *Absent* means the line has moved to the closed file — informational, not a finding.

This exists because copy-forward is the default editing action: every wrap re-reads the file and rewrites the parts it was thinking about, so a line nobody was thinking about survives untouched. One real project's CURRENT_STATE cited 146 IDs and 65 were already struck. The `/start` cross-check cannot catch it — the documents agree with each other perfectly.

**Multi-track:** a stale line in another track's section is not yours to edit. Put it on the ledger tagged for that track.

## Step 1f — KB sweep (name the lessons, or say none)

Answer in the report, every wrap: **did this session produce a lesson that would still be true in a different app?** Look for a root cause that took more than one attempt, a platform or tool trap, a dead end worth warning about, or a technique the user approved. List each as `*kbdoc` + one line, or write `KB: none`. Each one not written this session becomes a `- [ ] (<date>, <track>) <one-liner>` entry in **`docs/LESSONS_QUEUE.md`** (create it from the template's copy if the project has none), so it can't vanish with the chat. **Not a ledger line, and no ledger ID.** Also count the open entries in that file and name any older than 7 days; the user decides when they get written.

This step exists because the rule lived only as prose ("flag it in chat"): 17 sessions in a row produced no tag and the KB went 9 days without a lesson (2026-09-21 → 09-30). It then sent every unwritten lesson to the ledger, where on one project 11 of 124 open items were write-up reminders riding in every session's start payload — so the queue is its own file, which is never loaded at start. A step with a written answer cannot be silently skipped.

## Step 2 — Reconcile the spine, then overwrite `docs/CURRENT_STATE.md`

**First, the source of truth.** If this session completed or started a phase/block or changed scope, update the status spine in `ROADMAP.md` (and the matching section header). **Never renumber** — a cut item stays a labeled gap. **Spine cells stay at-a-glance short:** a status marker, the gate holding it open, at most a pointer. Do not append session narrative into a cell — that history lives in `HANDOFF_LOG.md`; when a session materially advances an item, REPLACE the cell's summary.

**Then re-read `docs/CURRENT_STATE.md` from disk** before overwriting (`git log --oneline -2 -- docs/CURRENT_STATE.md`, or compare against the session-start copy). Concurrent sessions share the checkout; if another session wrapped mid-flight, fold its facts in rather than clobbering.

**Then** replace it. Single track — the whole file; multi-track — **only your track's sections and the Shared facts you changed** (the other track's sections are copied through verbatim).

**v2: this file is the state of the APP, not the state of the session.** The test for every line is *if we are on 1.0.1, what does that entail?* Required shape:

- **📍 NEXT ACTION** (one per track) — ONE unambiguous line matching the spine's CURRENT marker, **citing the ledger IDs it depends on** (those are the items the next session gets in full).
- **Shipped** — version per track, and where it is (released / in review / internal).
- **Build status** — working / broken / not yet tested, what was verified, on what, when.
- **Shared services** (multi-track or client+server) — deploy state both sides consume, stamped `(by <track>, <date>)`.
- **Active blockers**, and **Open loops** as a pointer to ledger IDs only.

**Not here:** session narrative (that is the handoff entry) · any ledger item's *status* (cite the ID) · a copy of the phase/block list (that is the spine) · a "things to watch" pile. On one project those turned this file into 92,000 characters, 63% of it a 30-session narrative, injected whole at every session start. Overwrite, do not append.

**Multi-track — the shared block has a cap, and a script keeps it.** Everything outside the NEXT ACTION sections is loaded by every track's session. So:

- A bullet that is **one track's state** — its build status, its shipped version — starts with its tag, `- →<track> **…**`, and only that track loads it. Untagged means every track needs it.
- Then run, every wrap that touched CURRENT_STATE:

  ```bash
  python .claude/scripts/state-archive.py            # what would move
  python .claude/scripts/state-archive.py --apply
  ```

  When the untagged bullets are over `state.shared_max_chars` it moves the oldest (by the newest date in each; undated counts as oldest) to `docs/CURRENT_STATE_ARCHIVE.md`, which is never loaded. It never touches blocker sections or Shipped / Build status (each track's status of record — tag those rows instead). Read the dry-run list first: a bullet in it that is one track's state should be tagged instead; a standing ruling belongs in DECISIONS.md (and in the NEXT ACTION of the tracks it constrains). A moved fact that every track still needs goes back with today's stamp, shorter — that is the only way back. No track prunes another track's lines by hand; this script is the exit. Step 3b stops a wrap that leaves the block over its cap. (No `.claude/scripts/state-archive.py` in the project: it predates this step, which arrives with its template sync, `MIGRATION.md` §6e — skip it, never sync mid-wrap.)

## Step 3 — Append one entry to `docs/HANDOFF_LOG.md`

First, get the facts from git rather than from memory:

```bash
python .claude/scripts/end-derive.py
```

It prints the commits since the last wrap and the files touched, grouped by track ownership, and flags a shared-path change that needs an announcing ledger line. It deliberately does not derive build status — that is Step 0c's result, and inferring it would be exactly the unearned confidence this protocol keeps finding. **Those are the facts; you write the judgement.**

Get the time with `date '+%Y-%m-%d %H:%M'`. Append at the bottom, in **I-PASS shape**:

```
## YYYY-MM-DD HH:MM | <track> | <Phase/Block or area>
**Status:** green | yellow | red — <what was verified, on what, when>
**Changed:** <the delta this session — NOT a re-summary of the project>
**Next:** <the first move, with enough context to make it>
**If it fails:** <the contingency — what to try, or what it would mean>
**Confirm:** <the one thing the next session must restate before starting>
```

Single-track repos drop the `<track>` field.

**No length cap** — only this entry is injected next session, so it can be as long as the next session needs. But keep it to the **delta**: the reader has CURRENT_STATE, and a meta-analysis of 1,590 handovers found *excessive non-essential information* among the leading causes of the omissions handovers exist to prevent.

**If it fails** and **Confirm** are not optional. They are the two elements the handover literature finds missing most often, and they are what turn a summary into something the next session can act on when the happy path does not happen. If you cannot write **Confirm**, the entry is not finished.

A post-`/end` mini-wrap appends an entry covering ONLY the delta since the previous one.

## Step 3b — Payload budget (a GATE: non-zero exit → STOP)

```bash
python .claude/scripts/check-payload-budget.py --strict --ratchet                  # single track
python .claude/scripts/check-payload-budget.py --strict --ratchet --track <yours>  # multi-track
```

Measures what the next session will load — per track in a multi-track repo (the start hook plus that track's `--track` load) — against its **limit**: `payload.target_chars`, or the ceiling recorded for it in `protocol.json` → `payload.ceiling_chars` when the project was already over the budget when this gate arrived. **Non-zero exit → STOP. Do not commit the wrap** until it passes; the output names the payload, how far over it is and its largest contributor.

- **OVER ITS LIMIT** — this session left a payload bigger than it is allowed to be. Shrink what this session added: close ledger items that are done; route the ones that fail the worthiness test (idea → backlog, lesson → `docs/LESSONS_QUEUE.md`, standing fact → DECISIONS.md); cut narrative out of CURRENT_STATE (it belongs in the handoff entry, which costs nothing here). Move text, never delete it, and never strike an open loop to make room. In a multi-track repo an item tagged `→all` lands in every track's payload — if that is what tipped another track over, retag it for the tracks that actually act on it.
- **UNDELIVERABLE** — the next session would not receive everything (a hook part over the cap, more parts than `settings.json` wires, a handoff entry not loaded whole, an open item no track's session loads). Fix that first.
- **GROWTH** — one of the three ways the payload regrew under its ceiling: CURRENT_STATE's shared block over its cap (run `state-archive.py --apply`, Step 2); an item tagged for every track added by your track since the last wrap (give it its one owner, or name the tracks that act); a parked item that names no event (add one, or unpark it). Another track's new `→all` item is printed as a note, not a stop — tell that session.
- **Over budget, inside its ceiling** — passes. `--ratchet` lowers the ceiling to the new size whenever the payload ends a wrap smaller, and removes it once the payload is inside the budget; commit `.claude/protocol.json` with the wrap when it changed.

**A project whose scripts predate the gate** (`grep -c init-ceiling .claude/scripts/check-payload-budget.py` prints 0 — the start hook will have reported template drift) runs this step without `--strict --ratchet`, reports the size, and says in the report that the gate arrives with the template sync (`MIGRATION.md` §6d). Do not sync mid-wrap.

**Never raise `target_chars` or a ceiling, and never run `--init-ceiling` to get past this step** (it works once, on the day a project adopts the gate, and does nothing after). Raising either is the user's decision, in so many words, recorded in DECISIONS.md. This step reported for seven weeks before it was a gate, and the payload on the live project went from 53,000 to 77,000 characters while every wrap printed "over budget": a check that cannot fail is a notice.

## Step 4 — Commit and push

`git status` to confirm what changed. Stage **explicit paths** — never `git add -A` / `git add .`:

- `docs/CURRENT_STATE.md`, `docs/HANDOFF_LOG.md`, `docs/SESSION_LEDGER.md`, `docs/SESSION_LEDGER_CLOSED.md`, `docs/LESSONS_QUEUE.md` and `docs/CURRENT_STATE_ARCHIVE.md` (if they changed — the archive always together with CURRENT_STATE, or the moved facts are in neither commit), `docs/CODEBASE_INDEX.md` (if updated), `ROADMAP.md` (if the spine changed), `.claude/protocol.json` (if Step 3b lowered a ceiling)
- Any other files the user confirmed should be committed — in a multi-track repo, only files inside your owned paths or the shared paths.

Commit message: `Session: <one-line summary>` — multi-track: `Session (<track>): <summary>`.

Push per `push_policy`: `standing` → push now (the authorisation is recorded in DECISIONS.md); `ask` → ask first. **Force pushes always need explicit per-instance confirmation.** If a push is rejected, report it and let the user decide; never retry destructively.

**Multi-track:** before pushing, run `git log origin/main..HEAD` and name in the report any commit that is not yours — a push publishes the whole branch. If the user has said the other track's commits are not ready, do not push.

### Step 4a — Clean-tree guarantee (non-negotiable)

After the commit, `git status --porcelain`. For each remaining entry:

1. **Real in-scope work this session touched** → second commit `Session followup: <summary>` (with `(<track>)`), push again per policy.
2. **The other track's files** (multi-track; inside its owned paths, or in shared paths where the user has said they belong to that session) → leave them, and say so explicitly in the report.
3. **Out-of-scope work the user hasn't reviewed** → STOP and ask: commit, stash, or discard?
4. **Unknown** → treat as 3. Ask.

The only acceptable exit state: every remaining dirty path is accounted for in the report. The Stop hook enforces this.

### Step 4b — Confirm the mainline is published

```bash
git fetch origin main
git rev-parse HEAD
git rev-parse origin/main
```

If a push was made, both must match; if they differ, the push didn't land — report it, do not force. If policy was `ask` and the user declined, note that the remote is behind.

## Step 5 — Report

1. What was accomplished this session (track named)
2. What's next
3. Anything to watch for next session (incl. the other track's files left in the tree, and any commits of theirs your push carried)
4. Open ledger items: N (IDs that gate the next action; count vs soft max; stale items listed; the `DECIDE:` items as **Your calls**)
5. KB: this session's `*kbdoc` lessons (or "none"), plus the open count in `docs/LESSONS_QUEUE.md` (Step 1f)
6. Payload: the size against its limit from Step 3b, and any ceiling it lowered

## After `/end` — the mini-wrap rule

Work regularly continues after a completed `/end`. It must close with a **mini-wrap**: disposition/append ledger lines → ONE delta-only handoff line → CURRENT_STATE only if NEXT ACTION or build status changed (multi-track: then `state-archive.py --apply`) → `Session followup:` commit, push per policy, clean tree. Never a second full re-summary — that is how work gets recorded twice.
