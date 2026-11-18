# /start — Session Start Protocol

Begin a development session. **Applies only to repos with `.claude/protocol.json`** (or `docs/CURRENT_STATE.md`); otherwise say "this repo has no session protocol" and stop.

> **Normally you do not need to type this.** The `SessionStart` hook runs Steps 0–6 automatically and injects the state docs. Use `/start` when the hook did not fire (python missing, hook disabled, global rules not installed) or to redo the check mid-session.

> **Workflow note:** sessions run **directly in the main checkout** on the `main` branch. Worktrees are forbidden: they shift file paths and strand gitignored env files, which breaks builds in confusing ways. Claude Code **Desktop** force-creates a worktree per session and offers no setting to disable it ([anthropics/claude-code#21236](https://github.com/anthropics/claude-code/issues/21236)); the CLI flag `tengu_worktree_mode` is CLI-only. Two fixes: (1) **use the CLI** — `cd` into the project root in a terminal and run `claude`; or (2) **desktop workaround** — Settings → Claude Code → Desktop: Worktree location → Custom folder = `C:\Program Files` (an admin-only path makes creation fail and desktop falls back to the main checkout).

## Step 0 — Worktree guard (FAIL FAST, before anything else)

```bash
pwd
git rev-parse --abbrev-ref HEAD
```

If the cwd contains `.claude/worktrees/` OR the branch starts with `claude/` OR the branch is listed in `.claude/protocol.json` → `protected_branches` (a fork's read-only `main`), **STOP IMMEDIATELY**. Do not run the later steps, read files, or edit. Report the path, the branch, and the two fixes above, and wait.

## Step 0.3 — Global rules installed?

`~/.claude/CLAUDE.md` must import `claude-project-template/global/PROTOCOL.md`. If it does not (the hook will have said so), the session has no work-style rules and no protocol: locate the Knowledge Base clone on this machine, run `python "<KB>/claude-project-template/install-global.py"`, and restart. Tell the user first.

## Step 0.5 — Sync guard (BEFORE reading a single doc)

```bash
git fetch origin --prune
git status -sb
```

**`git status` reporting "up to date with 'origin/main'" is NOT a live check** — it compares HEAD against the local remote-tracking ref, which only moves on fetch/pull/push.

| State | Action |
|---|---|
| Up to date | Proceed. |
| `[behind N]`, tree clean | `git pull --ff-only`, then proceed. Report the pull in Step 7. |
| `[behind N]`, tree dirty | **STOP.** Surface both. Do not stash, do not merge. (Multi-track: the dirty files may be the other session's — say so; still the user's call.) |
| `[ahead N, behind M]` (diverged) | **STOP.** Surface it. Never auto-merge or rebase at session start. |
| Fetch failed (offline) | Proceed, but report currency as **unverified** in Step 7. |

If `protocol.json` sets `upstream_ref` (a fork): `git fetch <its remote> --prune` and `git rev-list --count HEAD..<ref>`. Report the count in Step 7. **Never merge or rebase at session start** — that is a session decision at a quiet point, per the project's DECISIONS.md.

Every file the later steps read is a tracked repo file. Reading them from a checkout that is behind origin loads a snapshot of the past, and the cross-check cannot catch it: it only tests whether the docs agree with each other, and stale docs agree perfectly. A stale checkout does not look broken; it looks complete. **Any protocol step that reads a git-backed source of truth must pull first** — this includes sibling repos a session reads (the Knowledge Base, shared config).

## Step 0.7 — Track gate (multi-track repos only)

If `.claude/protocol.json` declares two or more `tracks`: establish which track this session is on **before reading or editing anything**. Take it from the user's first message if stated; otherwise ask with the **AskUserQuestion picker** (one option per declared track, so the user clicks instead of typing; never a plain-text question) and wait. Everything below is scoped to your track — its NEXT ACTION section, its ID prefix, its last handoff line, its owned paths.

## Step 0.8 — Load your track (multi-track v2 repos: one command replaces Steps 1–4)

A v2 repo with two or more tracks **loads by track**: the start hook injects only the sync result, the track list and the directive, and the session loads its own track once it knows which one it is:

```bash
python .claude/scripts/session-start-context.py --track <name>
```

It prints your track's NEXT ACTION, the shared state (bullets tagged for other tracks left out), the open ledger items your track acts on (tagged for it, tagged `→all`, or unassigned — the ones waiting on the user's ruling first; parked items only as a count per event they wait on), the status spine and the handoff entry you are accepting. If the output ends with a **PAGE** line, run the command it names too. That output IS Steps 1–4; do not also read the state docs whole — every track's state in every session is the 77,000-character payload this replaced. Then go to Step 5.

(Only when the project's scripts carry it: `grep -c -- '--track' .claude/scripts/session-start-context.py` prints 0 on a project not yet synced to the template — there, the hook still injects everything and Steps 1–4 apply as written. Single-track and v1 repos: the hook injects the documents and this step does not apply; if the hook did not fire, the same command with any name prints them.)

## Steps 1–7

1. Read `docs/CURRENT_STATE.md` — the **📍 NEXT ACTION** line(s) above all (your track's, in multi-track repos) and the Shared block.
2. **v2 (`protocol_version: 2`):** the hook injects a **manifest** — every open item's first line, plus the full text of the items the NEXT ACTION cites. Each manifest line is a TITLE, not the item. Do not read any other item now; grep its ID when you work on it. Items under **YOUR CALLS** (title starts `DECIDE:`) wait on the user's ruling, not on work — name them in the report. **v1:** read the open `[ ]` lines only (grep `- [ ]`; closed lines are history).
3. Read your track's **newest handoff entry** — that is the handoff you are accepting. Do not read further back unless something in it does not parse.
4. Read the **status spine in `ROADMAP.md`** (heading per `spine_heading`) — the single source of truth for which phase/block is CURRENT (per track, if marked).
5. **Working-tree check** (Step 0.5 handled the remote). Run `git update-index --really-refresh > /dev/null 2>&1 || true` to clear phantom-dirty entries, then `git status` and `git log --oneline -5`. Changes surviving the refresh are real: surface them, since they mean the previous `/end` did not reach a clean tree — unless (multi-track) they sit in the other track's owned paths, in which case name them as theirs.
6. If `protocol.json` sets `audit_command`, run it. Silent on green; mention only findings.
7. **CROSS-CHECK (mandatory — the step that prevents drift).** Does the NEXT ACTION agree with (a) the spine's CURRENT marker (for your track), (b) the last HANDOFF line's "Next:" (your track's), (c) recent commits, and (d) no open ledger gate? **If any contradict, STOP and surface it — do not pick one and proceed.** A stale CURRENT_STATE leading with a minor loose end while the spine and handoff point at the real next work is exactly what this catches.

8. **ACCEPT (mandatory).** Step 7 compares documents against each other — and documents that have all copied the same stale claim agree perfectly, so it can find disagreement but never staleness. Close that gap from the receiving side: **restate the NEXT ACTION in your own words, and name what would make it wrong** (the assumption it rests on, the thing you would check first). If the handoff entry cannot support a restatement, say so plainly — "the handoff was insufficient: it does not say X" is a recorded signal and the next wrap should fix it. Completeness belongs to both sessions, not just the one that wrote the handoff.

Then report, 4 lines plus a sync line (5 plus track in multi-track repos):

- **Track:** <name> *(multi-track only)*
- Where we are (phase/block **name + number** from the spine)
- What last session accomplished (your track's)
- The single **NEXT ACTION**, **as you restate it** (Step 8) — or the flagged contradiction
- **Payload:** the session-start size against budget, when the hook (or the `--track` output) reported one
- Open ledger items: N (call out gates; multi-track: yours + `→all` + unassigned)
- **Your calls:** the `DECIDE:` items, one line each *(only when there are any)*
- **Sync:** `synced to origin @ <short-sha>`, plus `(pulled N)` or `(⚠️ fetch failed — currency unverified)`; forks add `upstream: +N` or `current`

**Trust, but verify.** CURRENT_STATE is hand-written and CAN be wrong. The spine wins any status disagreement, and CURRENT_STATE gets fixed — never silently work around either. Numbers are frozen. **Do not** read every handoff or every doc.

Full rules: the global `PROTOCOL.md` (already in context).
