# Why the protocol is shaped this way

**Read this when you want to know *why*, not *what*.** The rules in force are in `global/PROTOCOL.md` (short, auto-loaded every session). This file holds the design reasoning, the measurements that forced each decision, and the external evidence — it is never auto-loaded and an agent should not read it during normal work.

Written 2026-09-20, from an audit of the v1 protocol running live on a three-track project with 153 sessions of history.

---

## The purpose, in one sentence

**Make session N+1 start exactly where session N stopped, using the least reading that makes that true.**

Every rule either serves that or it is ceremony. When a rule is in question, this sentence settles it.

Two corollaries that do a lot of work:

- **The codebase answers "how does this work?"** The protocol answers "where are we and what is next." A protocol document that starts explaining the app has taken on the codebase's job and will go stale doing it.
- **A document's cost is what it costs *at every session start*, not what it costs to write.** A 60KB file that is never auto-loaded is free. A 6KB file that is injected every session is not.

---

## What went wrong in v1

v1 was correct in architecture and failed in exactly one predictable way. The audit measured it rather than guessing.

### The measurement

The `SessionStart` hook on the live project injected **163,478 characters — roughly 41,000 tokens — before the user typed anything**:

```
 92,368   docs/CURRENT_STATE.md
 60,494   docs/SESSION_LEDGER.md   (88 open items, truncated at injection)
  4,382   ROADMAP.md spine
  3,522   last handoff line per track
  2,219   last 5 handoff lines
```

For scale: Anthropic's own illustrative worked example of everything auto-loaded at a Claude Code session start — system prompt, memory index, environment, MCP tool names, skill descriptions, both CLAUDE.md files — totals about **7,850 tokens**. v1 was running at five times a normal full startup payload, in project state documents alone.

### The pattern

Sorting every v1 rule by how it was enforced produces a clean split:

| Enforcement | Rules | Outcome |
|---|---|---|
| A script | worktree guard, sync guard, index queue, clean-tree check, secret scan, file caps, injection truncation | **All holding** |
| Discipline at `/end` | ledger open count ≤ 30, prune closed after 7 days, route items older than 45 days, handoff summary ≤ 300 chars, "overwrite, do not append" | **All failed** |

Concretely: 88 open ledger items against a soft max of 30; 88 closed lines unpruned against a 7-day rule; 17 items past the 45-day line, listed every session and never actioned; **402 of 442 handoff lines over the 300-character cap** (mean 754, max 5,166); and `CURRENT_STATE.md` grown to 30 sessions of accumulated narrative.

This is v1's own documented lesson #1 — *"a protocol step with a discretionary skip clause is not a step"* — firing against v1's own bookkeeping.

### The mechanism nobody caught

v1's ledger caps worked. The ledger came down from 397KB to 259KB and stayed down. But **the mass moved to the one adjacent document with no cap.** On the day of the v1 audit, `CURRENT_STATE.md` was 5,968 characters. Twelve days later it was 92,900.

```
2026-09-08    CURRENT_STATE  5,968    ← v1 audit day
2026-09-12    CURRENT_STATE 23,202
2026-09-20    CURRENT_STATE 92,900
```

Three reasons it was missed, all structural rather than careless:

1. **The audit measured the suspect document, not the payload.** It counted the ledger because the ledger was the problem. Nobody summed what the hook emits. A per-document cap relocates mass; only the aggregate shows where it went.
2. **A template cannot exhibit a growth bug.** This repo's `project/docs/CURRENT_STATE.md` is 48 lines of placeholders and always will be. Auditing the template tells you whether the rules cohere, never whether they survive a year of use.
3. **The v1 fix created the surface.** Multi-track landed 2026-09-08 and brought three NEXT ACTION sections plus a Shared block. The 92KB lives almost entirely in structures that audit introduced — which were empty, and therefore looked fine, on the day they shipped.

**Standing consequence:** a structural change is the moment to schedule the next measurement, and the measurement is of the assembled payload.

---

## What the evidence says

The v2 shape is not invented. Where an established answer exists, v2 uses it.

### Manifest plus fetch-on-demand is the reference implementation

Claude Code's own auto-memory system is exactly this pattern: `MEMORY.md` is an index auto-loaded every session, **hard-capped at the first 200 lines or 25KB, whichever comes first**, with content past the cap silently not loaded; the topic files it points at are **not** loaded at startup and are read on demand. Claude Code's Skills do the same — a catalog entry capped at **1,536 characters**, the full body loaded only on trigger, and a further tier that keeps a skill out of the catalog entirely until called by name.

Anthropic's stated recommendation is a **hybrid**, not pure just-in-time: load some data up front for speed and predictability, let the agent fetch the rest, because runtime exploration is slower.

> Sources: Claude Code docs, *How Claude remembers your project* and *Skills* / *Explore the context window* (fetched 2026-09-20); Anthropic, *Effective context engineering for AI agents* (2025-09-29).

### One level of routing, never two

A July 2026 controlled study of progressive disclosure found that one level of routing beats reading raw documents once a corpus is too large to browse, but **a second, deeper routing level "never helps and sometimes breaks accuracy outright."**

v1 had a three-hop chain: `CURRENT_STATE` cites a ledger ID → the item is capped at 600 characters → the item points at `docs/notes/<ID>.md` for the analysis. v2 flattens it to **manifest line → whole item**.

This is also what removes the data-loss risk from capping. The 600-character cap and the notes-file indirection existed only to protect the injection. Once the injection is a manifest, they have no job, and the item can stay whole where it was written.

> Source: *Is Progressive Disclosure All You Need for Long-Context Agents?*, arXiv:2607.17598 (2026-07-20).

### Derived context cannot go stale

Aider's repo map is the only surveyed tool structurally incapable of staleness, because it is **computed per request** rather than maintained: tree-sitter extracts symbols, a PageRank-style graph ranks them, and a binary search fits the result to a token budget (default 1k), **dropping** the lowest-ranked entries rather than summarizing them.

v2 takes two things from this. **Derive what can be derived** — build status from the last check run, version from git, what-changed from the commits since the last wrap; a derived line cannot drift. And **fit a budget by ranking**, with one adaptation: Aider drops what does not fit, but a ledger item that vanishes is an absence, and absences produce no signal. So v2 ranks for **depth, not presence** — the manifest is always complete, ranking only decides which items also get full text.

> Sources: aider docs, *Repository map*; `aider/repomap.py` (read directly, 2026-09).

### The same architecture fails the same way for everyone

Cline's "Memory Bank" is the community pattern closest to v1: six markdown files read **in full, every task**, with no size, staleness, or archiving rule anywhere in its documentation. A user report on the project's own discussion board describes reaching *"around 300,000 tokens"* after roughly five iterations. The ecosystem's answer was a third-party MCP server bolted on to add a 28-day TTL and re-verify entries against current code.

This matters for morale as much as design: the accumulation is what the architecture does, not a personal discipline failure.

> Source: cline/cline GitHub Discussion #2979 (community report, no maintainer reply — treat as unresolved complaint, not acknowledged behaviour).

### The handoff has a validated structure; use it

**I-PASS** is the strongest evidence base in the handover literature: across 10,740 admissions at 9 hospitals, a **23% reduction in medical errors** (24.5 → 18.8 per 100 admissions, p<0.001) and a **30% reduction in preventable adverse events** (4.7 → 3.3, p<0.001), **with no significant change in handoff duration**. Structure did not cost time.

Its five elements were chosen because pilot observers found these were the ones most often *missing*: illness severity, contingency planning, and receiver read-back.

| I-PASS | v2 handoff |
|---|---|
| **I**llness severity | Build status — one word, first, not buried |
| **P**atient summary | What changed — **delta only** |
| **A**ction list | Owned items with done-conditions — the ledger, cited by ID, never restated |
| **S**ituation awareness + contingency | **"If X, then Y"** — new in v2 |
| **S**ynthesis by receiver | Read-back — new in v2 |

Aviation and nuclear converge on the same shape and add one element: an **explicit acceptance act**. FAA position-relief briefing and a docketed nuclear shift-turnover procedure both require self-brief from persisted state → brief scoped to the delta and anomalies → explicit acceptance ("position responsibility has been assumed"; initialing the log after read-back) → a post-handoff verification pass. Both treat completeness as **shared between outgoing and incoming**, not the outgoing party's job alone.

> Sources: Starmer et al., *Changes in Medical Errors after Implementation of a Handoff Program*, NEJM 2014;371(19):1803–1812; Starmer et al., *I-PASS, a Mnemonic to Standardize Verbal Handoffs*, Pediatrics 2012;129(2):201–204; FAA Order JO 7110.65 App. A; NRC-docketed Diablo Canyon turnover procedure.

### Long narrative causes omissions

A 2026 systematic review and meta-analysis of nursing handovers (6 studies, 1,590 cases) found errors in roughly **88% of observed handoffs**, with **information omission the most prevalent category**, and named *"excessive non-essential information"* and lengthy duration among the leading contributing factors.

Accumulated narrative is not merely expensive. It causes the thing the handoff exists to prevent.

### Copy-forward staleness is a measured hazard class

This is the evidence for the problem that started the audit — a line in `CURRENT_STATE` still saying two items were pending when both had been struck in the ledger eight days earlier.

Medicine has studied this for two decades. 66–90% of clinicians copy/paste routinely. In VA charts, copied exam findings persisted a **median of 56 days** past the original note. Among cases where copying had occurred, copy/paste mistakes **contributed to 35.7% of the diagnostic errors** identified. Documented case reports include a cardiac diagnosis carried forward across 12 visits over two years, ending in the patient's death.

There is a companion finding on why stale content survives review: diagnosis momentum, anchoring, and premature closure mean that **once something is written into a handoff it tends to be inherited and reinforced rather than re-verified**.

On the live project, 146 ledger IDs were cited in `CURRENT_STATE.md` and **65 of them were already struck** — 45% of every ID reference in the file. Copy-through-by-default is the default, and it is a hazard class.

> Sources: ECRI Institute, *Copy/Paste: Prevalence, Problems, and Best Practices* (2015, systematic review of 51 studies); Thielke et al. 2006; Singh et al. 2013; Frye et al., *Cognitive Errors and Risks Associated with Provider Handoffs*, Cureus 2018.

### A template alone changes nothing

A randomized trial gave nurses a structured SBAR form for after-hours physician calls. It **did not improve** the content communicated, and trended toward *fewer* background details.

This is the most important caution in the whole evidence set, and it is why v2 is not a document redesign. **Every element below has a script behind it or it does not ship.** Structure without enforcement is inert — which is the same conclusion the v1 measurements reached independently.

> Source: Joffe et al., *Evaluation of a Problem-Specific SBAR Tool*, Jt Comm J Qual Patient Saf 2013;39(11):495–501.

---

## The v2 design

### The injection contract

The `SessionStart` hook emits a **budgeted payload** with a stated target and a printed actual:

| Part | Budget | Content |
|---|---|---|
| App state | ~2.5KB | `CURRENT_STATE.md` in full — it is small by construction |
| Ledger manifest | ~10KB | One line per open item, all of them, grouped by track |
| Gating items | ~3KB | Full text of the items that gate a NEXT ACTION |
| Spine | ~4.5KB | `ROADMAP.md` status table |
| Handoff | ~2KB | **Your track's last entry only** |
| Directive | ~3KB | Track gate, cross-check, acceptance |
| **Total target** | **≤ 25KB** | matching Claude Code's own `MEMORY.md` ceiling |

The total is **measured and printed at every session start.** That number is the guard; the per-part budgets are hints. If the total is over, the hook says so and names the largest contributor.

### The four documents

Same four as v1. Each does exactly one job.

**`docs/CURRENT_STATE.md` — the state of the app.** Not the state of the session.

> If we are on 1.0.1, what does that entail?

- Version and what is shipped where (per track)
- Build status: working / broken / not yet tested, what was verified, on what, when
- Deploy state of shared services — server version, migration number
- **NEXT ACTION**, one line per track
- Active blockers

No session narrative. No "what the last session did." No "things to watch." No restating a ledger item's status — cite the ID. Derived fields are generated at `/end`, not typed.

**`docs/SESSION_LEDGER.md` — open loops.** Unchanged in content rules, with three changes:

- **No character cap on an item.** Items stay whole. The 600-char cap and the `docs/notes/<ID>.md` indirection are gone.
- **The first line is a self-contained title.** The manifest is built from it, so it has to stand alone. Everything after is body.
- **Closed lines move, they never delete.** Pruning appends to a closed-items file. An ID that escaped into a commit subject or a handoff entry must stay resolvable forever.

**`docs/HANDOFF_LOG.md` — the handoff, in I-PASS shape.** One entry per session, append-only, and **only the last entry per track is ever injected** — which is what lets it be as long as it needs to be. No 300-character cap.

```
## YYYY-MM-DD HH:MM | <track> | <area>
**Status:** green | yellow | red — <what was verified, on what>
**Changed:** <delta only — not a re-summary of the project>
**Next:** <the first move, with enough context to make it>
**If it fails:** <the contingency — what to try, or what it means>
**Confirm:** <the one thing the next session must restate before starting>
```

The last two lines are new, and they are the two elements the handover literature says are most often missing.

**`docs/CODEBASE_INDEX.md` — unchanged.** Never injected, read on demand. It already works the way v2 wants everything to work.

### Session start gains an acceptance step

v1's cross-check compares documents against each other. Stale documents agree with each other perfectly, so that check cannot detect staleness — it can only detect disagreement.

v2 adds the receiver's half: **restate the NEXT ACTION in your own words, and name what would make it wrong.** That is the read-back, and it converts the start report from a summary into an acceptance. Completeness becomes shared: if the handoff cannot support a restatement, `/start` says the handoff was insufficient, and that is a recorded signal rather than a silent shrug.

### Scripts

| Script | Status | Job |
|---|---|---|
| `session-start-context.py` | modified | Render the manifest; inject one handoff entry; **measure and print the payload** |
| `check-payload-budget.py` | **new** | The aggregate guard. Reads the files, reports per-part and total, exits non-zero over budget |
| `check-ledger-refs.py` | **new** | The copy-forward guard. Every ledger ID cited in `CURRENT_STATE.md` / `ROADMAP.md` classified open / struck / not-in-ledger |
| `end-derive.py` | **new** | The facts git can prove: commits since the last wrap, files touched grouped by track ownership. Does NOT derive build status — that is Step 0c's result, and inferring it would be unearned confidence |
| `ledger-archive.py` | **new** | Moves closed lines to `SESSION_LEDGER_CLOSED.md`. Dry run by default; refuses a dirty ledger; balances its line count before writing |
| `migrate-docs-v2.py` | **new** | One-time content migration, writes `.new` files beside the originals |
| everything else | unchanged | |

**`check-ledger-refs.py` design constraints**, all earned:

- Match **only declared ID prefixes** from `protocol.json` → `tracks`, plus legacy `L`. Verified against the live file: a generic pattern also catches `BUG-79` and `AVX-512`.
- **Three-way classification.** Open / struck / absent. On the live project 51 of 72 spine IDs are absent because they were pruned, and almost all are legitimate history. Only *struck* is actionable.
- **Report, never block.** A closed ID cited as history is correct.
- **Multi-track scoping.** A stale ID in another track's section cannot be edited by this session — it gets a ledger line tagged for the owner.
- **Anchor the match.** v1's `track-new-file.py` decides "already indexed" with a bare substring test, so 68 paths mentioned only inside other rows' descriptions would never be queued. Its sibling `validate-index.py` anchors correctly. Same lesson, one script over, never applied.

### Configuration

New keys in `.claude/protocol.json`:

```jsonc
"protocol_version": 2,          // which doc shape this project is on
"payload": {
  "target_chars": 25000,        // total injection budget
  "warn_over": 1.0,             // report when the total exceeds target × this
  "manifest_title_chars": 110   // manifest line length
}
```

Removed: `ledger.item_max_chars`, `ledger.prune_closed_after_days` (becomes `ledger.move_closed_after_days`).

---

## Validating this without fooling ourselves

The KB's own lesson: *"a probe only carries information if it can come back RED,"* and every assertion of the form "no element of S violates P" passes vacuously when S is empty.

**Every new check is validated against the live project's real files, never against `project/` in this template.** The template's state docs are 48, 56 and 11 lines of placeholders — any growth or staleness check validated there goes green forever by construction. Each check is made to fail on purpose once before it is trusted.

The companion trap: a check that can return a false all-clear is worse than no check, because it converts an open question into unearned confidence.

---

## Deliberately rejected

- **A new harness.** Every script-backed rule in v1 held. The layering is what makes v2 deployable at all.
- **Dropping low-ranked ledger items from the manifest** (Aider's approach). An item that vanishes is an absence, and absences produce no signal. Rank for depth, not presence.
- **Summarizing anything during migration.** Every v2 migration verb is *append* or *move*. Nothing is deleted or rewritten.
- **A second routing level** (`docs/notes/<ID>.md`). Measured to hurt.
- **Keeping the 300-character handoff cap.** It existed because five lines were injected; one entry is injected now, so the cap has no job and it was being violated 91% of the time regardless.
- **Fixing the soft caps by making them louder.** A cap exceeded 3x for months is not a cap. The answer is a rate, not a level: route or close the two oldest stale items per wrap, which is cheap enough that nobody wants to override it.

---

## Migration

`protocol_version` tells the scripts which shape a project is on, so v1 and v2 projects coexist and the start hook names the difference. Machinery syncs with `check-template-drift.py --sync`; document content is migrated by `migrate-docs-v2.py`, which writes `.new` files for review and never replaces anything on its own. Full procedure in `MIGRATION.md`.
