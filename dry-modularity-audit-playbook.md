---
stack: [any, refactoring, codebase-audit]
kind: playbook
last_verified: 2026-07-20
---

# DRY / modularity audit playbook

A repeatable way to find and fix real duplication in a codebase that's grown fast — sibling to `pre-launch-security-audit-playbook.md`, but for duplication/file-size instead of security. Same fan-out → synthesize → triage shape, different split axis and a different tiering criterion.

## Shape: fan out read-only sweeps by CODE AREA, synthesize into ONE tiered report
Split by code area, not by trust-boundary domain: e.g. frontend data/sync, frontend UI + styles, native/Rust commands, server + shared core. Contrast with the security playbook's domain split (auth / data / client / frontend) — that split exists because security findings cluster at trust boundaries; DRY findings instead cluster inside a layer or language, so an area split surfaces more real duplication per agent. Report only — **no code changes in the audit pass itself.** The user reviews and prioritizes the tier list before any refactor lands.

## The tiering axis is DRIFT RISK, not line count
- **Tier 1 — already bit us, or actively drifting.** The copies have either already caused a real bug, or have visibly diverged from each other (proof the "keep N copies in sync by hand" discipline is already failing). This is correctness debt, not style debt — do it first.
- **Tier 2 — worthwhile consolidations, not yet bitten.** Real duplication per the project's own DRY bar, where the extraction creates a genuinely reusable module/interface. Judge by the interface created and the blast-radius removed, **not raw line savings** — a "plug-n-play modularity" lens, not a diff-size lens.
- **Tier 3 — small/opportunistic.** Dedupe only when you're already touching the file for another reason.
- **File-split candidates are a SEPARATE list, not a tier.** "Which files are too big" and "what's duplicated" are different questions with different remedies — splitting a file changes nothing about duplication, and collapsing a duplication doesn't necessarily shrink any one file below a size cap. Keep them as two lists so a giant-but-non-duplicated file doesn't get miscategorized as a DRY finding (or vice versa).

## Auditor rubric (signal, not noise)
- Read-only; report only. Each Tier 1/2 finding needs exact file:line pairs for every duplicate site, a % identical estimate, and — for Tier 1 specifically — the concrete bug or observed drift that proves the risk is real, not hypothetical.
- **Quote the project's own DRY bar in the prompt** (e.g. "3+ identical uses = extract; 2 uses only when the shape is certain AND drift risk is real") so every agent applies the same threshold instead of each inventing its own aggressiveness.
- **State an explicit, non-arbitrary goal lens up front.** Without one, a DRY sweep degenerates into "everything remotely similar is a finding" — the opposite of signal. ("Judged by the module/interface it creates and the blast-radius it removes... don't be overly aggressive/arbitrary — it should be valuable/worthwhile" is a real instruction that worked.)
- **Include a "Verified non-findings" section** — duplication that looks like a finding but should stay: a security-motivated non-collapse (don't let a client address arbitrary secret keys over IPC just to save 3 lines of shell command), a compile-time-guarded intentional redundancy, a deliberate cross-language duplication with no shared-source mechanism available. Mirrors the security playbook's "Verified OK" section: record what you checked and decided not to touch, so it isn't re-litigated next audit.

## Sequencing: don't ship it all in one PR
- Recommend an explicit sequence, not just a flat list — including what to **defer** and why. A finding that physically overlaps files another feature slice has mid-edit (uncommitted WIP) should be deferred past that slice landing, not raced into a merge conflict.
- Execute tier-by-tier as **separate commits**, one logical consolidation per commit, each stating which report item(s) it closes (e.g. "audit Tier1 1.1+1.6"). Traceable back to the line item, independently revertible/bisectable.
- Each execution commit should state what was verified (build green, live probe, specific repro) in the body — not just "refactored X."

## What a real Tier-1 fix looks like (concrete)
- **Duplicated per-table delete list.** Two account-deletion routes hand-maintained the same multi-table `DELETE` list; one copy had already silently missed a table, causing a real production bug (an orphaned row synced back down as stale data). Fix: one `wipeUserData(client, id, options)` function; both routes call it. Bonus: an automated assert that the delete list covers every table in the app's write-allowlist, closing the gap for good — this is a fresh instance of `n-copies-of-truth-drift-guard.md`'s pattern, found via a DRY audit rather than a sync-schema audit.
- **~85%-identical pipeline duplicated 3x.** A download-materialize / upload / sweep-pending / mirror-to-cloud skeleton (~55-100 lines) was copy-pasted per attachment kind (screenshots, audio, a lighter third variant), including a subtle bug-fix branch that had to be kept byte-identical by hand across copies. Fix: one parameterized module owning the four shared flows; kind-specific residue (column names, content-type derivation) stays as small config objects at each original call site. Net line count barely moved (+59 raw lines) — **log this "honest accounting" explicitly in the commit message.** A DRY refactor that doesn't shrink line count can still be the right call: the win is N independently-editable copies becoming 1, not bytes removed.

## Lessons that recur
- **The real yield is often "how many places a future bug-fix must be applied by hand," not line count.** Report savings honestly, including near-zero or negative — the value is the copy count, not the byte count.
- **The audit will also surface your best existing work as "verified non-findings."** Treat a confirmed-correct consolidation as equally valuable output: it tells you that area doesn't need a second look, and it gives new findings a cited precedent to follow.
- **Tier-1 findings are frequently fresh instances of a drift-guard problem** (hand-maintained lists/copies that must stay in lockstep) — pair the refactor with an automated assert wherever the finding was "these N things must match," not just a shared function.
- **Sequence around in-flight work explicitly.** A DRY audit reads the whole tree including uncommitted WIP; findings that overlap another slice's mid-edit files get deferred, not raced.

## Related
- [`pre-launch-security-audit-playbook.md`](./pre-launch-security-audit-playbook.md) — sibling playbook, same fan-out/synthesize/triage shape, split by trust-boundary domain instead of code area, severity instead of tier.
- [`n-copies-of-truth-drift-guard.md`](./n-copies-of-truth-drift-guard.md) — Tier-1 findings that are "N hand-maintained things that must match" are instances of this pattern; pair the fix with an automated assert, not just a shared function.

---
*Captured from the Playmoir DRY/modularity audit, 2026-07-17 (4-agent sweep, ~600-800 line dedup opportunity found across Tier 1-3, Tier 1 executed as 6 separate commits over 2026-07-18).*
