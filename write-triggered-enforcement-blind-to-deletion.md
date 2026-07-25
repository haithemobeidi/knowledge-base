---
stack: [any, docs, tooling, hooks, claude-code]
kind: pattern
last_verified: 2026-07-25
---

# Write-triggered enforcement is blind to deletion

**One-liner:** a hook that fires on "file written" can guarantee every *new* thing gets documented, and still let documentation silently disappear — because deleting a row in a catalog is not a write to the thing that row describes. Enforce the **invariant** ("every source file has a row"), not the **event** ("every write produces a row"). The invariant check is a one-second script; the event hook is half a guard that reads like a whole one.

## Symptom

A 643-line file — the single most important component on the app's main screen — had **no row in the repo's file index** for about three and a half weeks.

Nothing failed. No test, no build step, no linter, no CI job. `git status` was clean the whole time. The index's own enforcement hook was working correctly and firing on schedule.

It was found by accident, while doing unrelated work in that file.

## The setup (why this felt airtight)

The project enforces "one index row per source file" with a `PostToolUse` hook: every time an agent writes a file, the path is appended to a pending list, and the session-end protocol refuses to complete until each pending path has a row in `docs/CODEBASE_INDEX.md`.

That is a real guard, and it works. Every file *created* since the hook landed has a row. The discipline problem it was built to solve — "remember to document new files" — is genuinely solved.

## What actually happened

Weeks earlier, a docs-reconciliation commit set out to do legitimate housekeeping: **remove index rows pointing at files that no longer existed** (renames, splits, deletions leave these behind). The commit message said so plainly:

```
CODEBASE_INDEX.md: remove 4 verified-phantom rows.
```

The diff removed **10** rows and re-added **3** (those three were merely reordered). Net: **7** rows removed, against **4** intended.

Checking each of the 7 against the filesystem afterwards:

| Row removed | Reality |
|---|---|
| 4 of them | genuinely deleted files ✅ — exactly the 4 claimed |
| 3 of them | **live files, still on disk** ❌ |

The author verified four phantoms, found four phantoms, and was right about all four. The edit then removed a **contiguous block** that happened to contain three correct neighbours. The commit message accurately reports the *intent*, which is the number that was verified — not the number that was removed.

Then the self-healing kicked in and hid the damage: **9 of the 10 removed rows came back** over the following weeks, re-added naturally as later work touched those files and the hook fired. The one that never came back was a **stable** file — nobody had needed to modify it, so nothing re-triggered the hook.

That selection effect is the nastiest part. **The files that stay missing are exactly the stable, load-bearing ones** — the files most worth having documented, and the least likely to heal by accident.

## Why nothing caught it — three independent reasons

1. **The hook keys on the wrong event.** It fires when a file is *written*. Deleting that file's row in a catalog is a write to the *catalog*, not to the file. The two events are unrelated, so a create/update hook cannot see it by construction.

2. **The artifact has no runtime consumer.** A missing index row does not throw, warn, fail a test, or degrade at runtime. It is an *absence*, and absences produce no signal. Compare a missing DB column — something eventually reads it and breaks. Nothing ever "reads" a docs row except a human or an agent looking something up, and both fail *silently* by concluding the thing doesn't exist.

3. **Partial self-healing hides the rate.** Because most rows return by accident, the failure looks rarer than it is. You never see "7 rows lost," you see "one weird gap," long after the commit that caused it.

## The near-miss while fixing it

The first verification scan reported **0 missing** and was wrong. It extracted every `` | `path` `` occurrence *anywhere in the file* — so a path mentioned inside **another row's prose description** counted as "indexed."

Rows in this format describe their neighbours constantly ("extracted from `Foo.tsx`", "same pattern as `bar.ts`"), so the false-negative rate is high and biased toward exactly the well-connected files you care about.

```python
# WRONG — a path mentioned in any row's description counts as indexed
listed = set(re.findall(r'\| `([^`]+)`', index_text))

# RIGHT — anchor to the first column of a table row
listed = set(re.findall(r'(?m)^\|\s*`([^`]+)`\s*\|', index_text))
```

Anchored, the same scan found 2 real gaps it had just declared clean. **A verification script that can return a false "all clear" is worse than no script**, because it converts an open question into unearned confidence.

## The fix

Stop enforcing the event. Check the invariant directly — it costs about a second:

```python
import re
from pathlib import Path

index  = open('docs/CODEBASE_INDEX.md', encoding='utf-8').read()
listed = set(re.findall(r'(?m)^\|\s*`([^`]+)`\s*\|', index))   # first column ONLY

roots = ['packages/frontend/src', 'apps/server/src']            # your source roots
skip  = {'node_modules', 'dist', 'target', '.turbo', 'vendor'}
found = [p.as_posix() for r in roots for p in Path(r).rglob('*')
         if p.suffix in ('.ts', '.tsx', '.rs') and not set(p.parts) & skip]

missing = sorted(set(found) - listed)
print(f'MISSING: {len(missing)}')
for m in missing:
    print('  ', m)
```

Run it at wrap/commit time. Two properties matter more than the code:

- **It is stateless.** It doesn't care how a row went missing — deletion, bad merge, block edit, hook outage, a file arriving via `git mv`. It compares reality to the catalog and reports the delta.
- **It cannot false-clear.** Anchoring to the first column is the whole difference between a guard and a comfort blanket.

Keep the write-hook too. The two catch different things: the hook is *proactive* (documents at creation, while context is fresh), the scan is *reactive* (catches everything else). Neither subsumes the other.

## Where this generalizes

The pattern is **any catalog with no runtime consumer, guarded by a create/update hook**:

- File/module indexes, ADR lists, API doc pages, runbook links
- Environment-variable documentation, feature-flag registries
- `CODEOWNERS`, permission allowlists, monitoring alert inventories
- Dependency/license manifests maintained alongside a lockfile

The diagnostic question, worth asking of every hook you write:

> **"What happens when someone *deletes*?"**

If the answer is "nothing," the enforcement covers one direction of a two-directional problem, and the gap will be invisible for as long as it takes someone to trip over it.

## Two rules worth stealing

1. **Enforce invariants, not events.** "Every source file has a row" is checkable in one second, from scratch, with no memory of how the tree got this way. "Every write produces a row" is an event subscription with blind spots you inherit forever.

2. **Block edits take neighbours.** When a cleanup removes a contiguous range, verify the **whole range you touched**, not the items you set out to remove. Your commit message will report the count you verified — which is exactly why the extra removals never make it into the message, the review, or your memory of what you did.

## Related

- [n-copies-of-truth-drift-guard.md](./n-copies-of-truth-drift-guard.md) — the same parent thesis ("build the guard, don't rely on discipline") applied to *runtime schema* copies. Different mechanism: there the copies drift by omission at deploy time and the symptom is missing data; here a catalog loses rows and the symptom is nothing at all. Both fail silently, both are fixed by a script that fails loudly.

## Cost of the fix

One script, about a second per run, nothing to maintain. Weighed against a core file being undiscoverable for 3.5 weeks — and the file that stays missing always being a stable, important one — this is not a close call.
