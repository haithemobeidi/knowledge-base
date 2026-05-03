# <ProjectName> — Project Context for Claude

> <TODO: one-line purpose/tagline for the project.>

This file is auto-loaded into every Claude session. Read it first.

## What is <ProjectName>?

<TODO: 2–4 sentence description. What is this project? Who is it for? What problem does it solve?>

For the full plan see [`ROADMAP.md`](./ROADMAP.md). For why each technical choice was made, see [`DECISIONS.md`](./DECISIONS.md).

---

## Locked technical decisions

<TODO: Fill this table with the choices you've committed to. Delete rows that don't apply.>

| Area | Choice |
|---|---|
| Frontend | <e.g. React + TypeScript (strict mode)> |
| Backend / shell | <e.g. Tauri 2, Next.js, CLI, etc.> |
| Local DB | <e.g. SQLite + Drizzle ORM> |
| Cloud backend | <e.g. Cloudflare D1 + R2 + Workers> |
| Auth | <e.g. better-auth, Clerk, Lucia, custom> |
| Payments | <e.g. Lemon Squeezy, Stripe, N/A> |
| Styling | <e.g. Tailwind v4 + shadcn/ui> |
| State | <e.g. Zustand, Redux Toolkit, none> |
| Validation | <e.g. Zod at every boundary> |
| Monorepo | <e.g. pnpm workspaces + Turborepo, or single-repo> |

---

## Code quality rules (non-negotiable)

1. **Files do ONE thing.** Soft cap **500 lines**, hard cap **800**. If a file passes 500, propose a split before adding more.
2. **No DRY violations.** Default: 3+ identical uses = extract. Judgment override: extract at 2 uses when the shape is *certain* (trivial utility, identical verbatim SQL) AND the duplication creates real drift risk (already caused a bug, or lives on a schema that changes often). Don't extract at 2 uses when the abstraction might be wrong — duplication is cheaper than the wrong abstraction.
3. **No "utils" or "helpers" dumping grounds.** Group by feature (e.g., `features/screenshot/`), not by type.
4. **TypeScript strict mode.** No `any` without a comment justifying it.
5. **Zod at every boundary** — anything from disk, network, user input, or IPC.
6. **Comments explain WHY, not WHAT.** Code explains what.
7. **No premature abstractions.** Used once = leave inline.
8. **Per-file documentation lives in [`docs/CODEBASE_INDEX.md`](./docs/CODEBASE_INDEX.md)** — not in file headers. The index is enforced by a `PostToolUse` hook (see [`PROTOCOL.md`](./PROTOCOL.md)).
9. **Folder-level docs live in per-folder `README.md` files + `ARCHITECTURE.md`** at the repo root — see the "Navigation docs" section below for when to read and write them.

---

## Navigation docs: READMEs + ARCHITECTURE.md — read on demand, never auto-load

The repo ships three layers of documentation. Each has a specific purpose and a specific usage protocol, designed so future agents/devs get the context they need without context-bloating every session.

| Doc | Purpose | When to read |
|---|---|---|
| `CLAUDE.md` (this file) | Non-negotiable rules + work style | **Auto-loaded every session.** |
| `docs/CODEBASE_INDEX.md` | One-line description per file in the repo | **Read on demand** when you need to locate something. Don't load into context proactively. |
| `ARCHITECTURE.md` (repo root) | ASCII flow diagrams for core end-to-end flows. | **Read when work spans multiple folders** OR when tracing a flow you haven't seen before. Write this once the project has 3+ distinct features talking to each other. |
| `<feature>/README.md` (per-folder) | "Sibling map" — folder purpose, main entry, file roles, key flows, connected folders, gotchas. | **Read the folder's README before making non-trivial changes in that folder.** Skip for typo-level edits or single-line touches in a file you already understand. |
| `docs/WORK_STYLE.md` | Long-form work-style rules (mock-before-build, don't-reinvent, pause-at-milestones). | **Read on demand when the rule's trigger applies** (starting a UI feature, designing a non-trivial component, starting a sub-phase). Not auto-loaded. |

### How to use during a task

1. **Starting a task in a specific file** — read that file's folder README first. It tells you the sibling files you might touch, the helpers that already exist, and the gotchas. Takes ~30 seconds, saves you from reinventing something that already lives next door.
2. **Starting a task that spans 2+ folders** — read `ARCHITECTURE.md` for the relevant flow. The flow diagram shows you where control hands off between folders so you know which READMEs to read next.
3. **Looking for "does X already exist?"** — `CODEBASE_INDEX.md` first (flat catalog, one line per file). If the index doesn't have it, grep.
4. **Skip the docs when** — the task is trivial, scoped to one file you already know, or a bug fix that doesn't touch architecture.

### How to maintain

- **READMEs and ARCHITECTURE.md are NOT enforced by a hook.** The `CODEBASE_INDEX.md` hook catches new files; there's no equivalent nag for README staleness. So: when you do a substantial refactor (file move, feature extraction, flow change), update the affected README(s) as part of the same commit. If an ARCHITECTURE.md flow diagram no longer reflects how the code actually works, fix it.
- **Keep each README under ~100 lines.** If it sprawls, you're probably restating `CODEBASE_INDEX.md` — step back.
- **READMEs are sibling maps, not file catalogs.** One line per file is plenty. The purpose is "here's the feature + here's what each sibling contributes + here's the 2-3 flows that pass through." Not "here's every prop and export."

### Anti-patterns

- ❌ Auto-loading all READMEs at session start. Context bloat for marginal benefit.
- ❌ Copying CODEBASE_INDEX content into a README. The index already does flat file coverage; the README does sibling/flow orientation.
- ❌ Treating READMEs as "should be documented" — they're navigation, not reference docs. Brevity > completeness.

---

## Work style — long-form rules live in `docs/WORK_STYLE.md`

To keep this file lean, three dense work-style rules now live in [`docs/WORK_STYLE.md`](./docs/WORK_STYLE.md). Read that file on demand when the trigger applies; it is **not** auto-loaded.

| Rule | Read it when |
|---|---|
| **Mock before you build** (UI projects only) | Before designing any new screen or layout change. |
| **Don't reinvent the wheel** | Before designing any non-trivial component — search OSS / reference repos for prior art first. |
| **Pause at natural test milestones** | Before starting any sub-phase. Declare 2–4 pause-points up front; stop at each one for live testing. |

Quick summary of each so the trigger lands even without reading the full file:

- **Mock first** — new UI lands in the HTML prototype before real code; user signs off on the prototype, then you build.
- **Search first** — for any "this must have been solved before" problem, spend up to 10 minutes finding prior art before designing from scratch.
- **Pause first** — declare pause-points before writing code; stop at each milestone (form renders, IPC roundtrips, error surfaces) for live test before continuing. Hard safety net: stop after 4+ new files or 300+ lines without hitting one.

---

## Subagents — read-only by design

This project ships three custom subagents in `.claude/agents/`. They are **all read-only** — they research, plan, and review, but never write or edit code. Only the main Claude session makes changes. This is deliberate: parallel writers fragment a project; parallel readers compound focus.

| Agent | When to launch |
|---|---|
| `planner` | Before starting any non-trivial implementation. Returns a step-by-step plan with declared pause-points and tradeoffs. |
| `reviewer` | After the main session has made a substantive change but before committing. Returns must-fix items grounded in CLAUDE.md rules. |
| `explorer` | Mid-task, when you (or the user) become curious about an adjacent feature or "does this already exist?" question and don't want to derail the current change. Returns a focused report with `file:line` citations. |

**How the user expects them to be used:**

- **Use them freely for the current task** (planning the function you're about to write, reviewing the diff you just produced).
- **Use them freely for adjacent read-only questions** (the "I'm building Y, but how does X work?" case). Launch in parallel with current work — explorer reports back, current work continues.
- **Do NOT spawn writer/editor subagents.** Even if the platform's general-purpose agent could edit files, do not delegate code changes to it. The main session is the single source of changes.

## Session protocol

**See [`PROTOCOL.md`](./PROTOCOL.md) for the full session lifecycle (start / during / end), the automation hook, and slash commands.** That is the single source of truth — do not duplicate session rules in this file.

---

## Coordination

<TODO: If you have a global agent-coordination doc (e.g. `~/documents/CLAUDE_AGENT_COORDINATION.md`), link to it here. Otherwise delete this section.>
