# <ProjectName> — Project file

> <TODO: one-line tagline.>

**This file augments the global rules** (work style + session protocol, auto-loaded from the Knowledge Base on every machine). It holds ONLY what is different about this app. Keep it under ~150 lines. Before adding a line, apply the three tests:

1. **Does it contradict a global rule?** Then it goes in *Overrides*, naming the rule and the reason — nowhere else.
2. **Is it actionable?** A trigger and an action ("when X, do Y"). "Make it feel premium" is not a rule.
3. **Is it specific to this app?** A rule that would be true in another app belongs in the global work style or the Knowledge Base, not here.

Everything the scripts need (check command, push policy, skip paths, ledger caps, tracks) lives in `.claude/protocol.json`, not here.

---

## What this is

<TODO: 2–4 sentences. What is the app, who is it for, what problem does it solve. Link `ROADMAP.md` for the plan and `DECISIONS.md` for why each technical choice was made.>

## Locked stack

<TODO: the choices you've committed to. Delete rows that don't apply. A row here is a decision, not a status — never read "what is built" from this table.>

| Area | Choice |
|---|---|
| Frontend | <e.g. React 19 + TypeScript strict> |
| Shell / runtime | <e.g. Tauri 2, Next.js, CLI, Kotlin + Compose> |
| Local data | <e.g. SQLite + Drizzle> |
| Backend | <e.g. Fly.io + Postgres, Cloudflare Workers + D1> |
| Auth | <…> |
| Styling | <…> |
| State | <…> |
| Validation | <e.g. Zod at every boundary> |
| Repo shape | <e.g. pnpm workspaces + Turborepo, or single package> |

**Stack-specific quality rules** (the global ones — 500/800 caps, DRY at 3, no `utils/`, comments explain why — always apply):
- <TODO: e.g. TypeScript strict, no `any` without a comment; Kotlin: no `!!` without a comment>
- <TODO: e.g. Zod at every boundary: disk, network, user input, IPC>

## Where the code is

<TODO: the layout, and "know which codebase you're in" if the repo holds more than one. Name generated directories so nobody edits them.>

| Path | What it is | Status |
|---|---|---|
| `<apps/desktop/>` | <…> | active |
| `<packages/core/>` | <shared schemas + API contract, consumed by every client> | active |
| `<…/gen/>` | generated — never hand-edit | — |

## Tracks

<TODO: delete this section in a single-track project. Tracks are DECLARED in `.claude/protocol.json` (name, ID prefix, owned paths, shared paths) — that is the source of truth the scripts read. Here, one line per track on how to build, run, and test it, and anything a session on that track must know.>

- **desktop** — <how to run it; who launches the dev server; where releases go>
- **mobile** — <device/emulator; how to install a build; test account>

## How to run and test

<TODO: canonical commands. Who launches what (default: the user launches the app, Claude reads logs).>

```
<dev command>
<check / typecheck command — also set as check_command in protocol.json>
<test command>
```

## Project rules

<TODO: additive rules specific to this app, each as trigger → action. Examples of the right shape:>

- **When editing user-facing copy** → no em-dashes; keep the product's voice: <…>.
- **When adding a table or column** → update the sync rules file and the client schema in the same commit; run the drift guard.
- **When a screen is new** → mock it in `docs/design/prototype/<screen>.html` first (global mock-first rule; this line only names where the prototype lives).
- **When testing on device** → <device name>, <account>, <install method>.

## Overrides of global rules

<TODO: empty is the normal state. Each entry names the global rule, what replaces it here, why, and the date. Anything not listed here cannot override a global rule.>

| Global rule | Override here | Why | Since |
|---|---|---|---|
| <e.g. "Push per policy = ask"> | <e.g. session-end push pre-authorised (`push_policy: standing`)> | <continue work from the laptop without ceremony; recorded in DECISIONS.md> | <YYYY-MM-DD> |

## Where things live

<TODO: pointers, one line each. Delete what doesn't exist.>

| Thing | Where |
|---|---|
| Open bugs | `docs/BUGS_AND_FIXES.md` (each entry has an **Affects:** line) |
| Deferred features / ideas | `docs/FEATURE_BACKLOG.md` |
| Design prototype | `docs/design/prototype/` (one HTML per screen; see its README) |
| Architecture flows | `ARCHITECTURE.md` (read when work spans folders) |
| Glossary / naming map | `docs/GLOSSARY.md` |
| Reference repos (prior art, same author) | `<path>` |
| Deployed services | <server host + how to see version/logs> |

## Navigation docs — read on demand, never auto-load

| Doc | Read when |
|---|---|
| `docs/CODEBASE_INDEX.md` — one line per file | Locating something. "Does X exist?" → index first, then grep. |
| `ARCHITECTURE.md` — flow diagrams | Work spans 2+ folders, or tracing an unfamiliar flow. Fix it when a flow changes. |
| Per-folder `README.md` — sibling maps | Glance if already in the folder and it might have gotchas. Staleness is expected; fix only when actively misleading. Never duplicate the index or the bug list into a README. |

## Subagents — read-only by design

`.claude/agents/` ships `planner` (plan with pause-points before non-trivial work), `reviewer` (independent diff review before committing), `explorer` (adjacent "how does X work / does Y exist" questions without derailing). All read-only; the main session makes every edit.
