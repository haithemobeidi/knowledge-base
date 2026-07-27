---
stack: [any]
kind: playbook
last_verified: 2026-07-26
---

# Instrument before patching — the rule for invisible-failure surfaces

**One-liner:** when a fix on some surface fails *invisibly* — the patch is plausibly correct, ships, and the symptom persists with no error anywhere — do not write the next patch. Wire the surface's own decisions into something dumpable first. Measured result from the sessions this was extracted from: **three consecutive correct-looking patches failed silently over two days; the first capture with decision-logging in place named the real bug in one shot** (an effect-cancellation race that no amount of staring at the patch sites could reveal, because every patch was downstream of the cancellation).

## The failure shape

Some pipeline makes internal decisions you can't see from the outcome: an image-resolution chain picking URLs, an animation state machine choosing exits, a sync layer reconciling rows. It misbehaves intermittently. Each fix attempt:

1. reads the code, forms a plausible theory,
2. patches the theorized spot — the patch is often *correct in isolation*,
3. tests by outcome ("is the symptom gone?"), sees it's not (or worse, it flakes), goto 1.

The loop burns rounds because outcome-testing can't distinguish "patch wrong" from "patch right but never reached" from "patch reached but its effect cancelled by something upstream." All three look identical: symptom persists.

## The rule

**Before fix attempt N+1 on any surface that has already eaten one invisible failure, the surface logs its own decisions.** Not `console.log` scattered during debugging and deleted after — a small permanent trail: which branch ran, which candidate won, what got cancelled, with enough context to replay the decision. Then reproduce once and read what it *says it did*. The bug names itself; deltas between "what the code should do" and "what the trail shows" are exactly the diagnosis.

## The tripwire pattern (for "app looks frozen/wedged" bugs)

When the failure mode is *the UI itself wedging*, the instrument must survive the patient:

- **Framework-free by design.** If React is wedged, an instrument that renders through React dies with it. Vanilla listeners + imperative DOM only.
- **Armed pre-mount, always on** (dev builds), not attached when debugging starts — intermittent bugs don't schedule appointments.
- **A capture-phase input ring buffer** (last N pointer-downs, each with its `elementsFromPoint` hit-test stack) — shows what actually ate the clicks made *while frozen*.
- **A global hotkey that snapshots the DOM facts open theories disagree about** — full-viewport fixed/absolute layers with computed pointer-events/opacity/visibility, `document.getAnimations()`, portal roots, a hit-test grid — and **persists to disk via the backend**, with a localStorage fallback if IPC is also down. The dump must survive the kill-and-restart that follows a freeze.
- **Stamp the relevant state machine onto the DOM** (`data-*` attributes on `<html>` + a bounded in-memory transition log included in the dump), so the dump names the wedged variable directly instead of leaving it to inference.

Cost: ~250 lines, one evening. It converted "recurring unexplainable freeze, three failed theories" into a mechanism-level diagnosis from a single user-captured dump — twice, for two different bugs.

## When it's overkill

First failure on a surface, with a visible error or a deterministic repro — just fix it. The rule triggers on the *second* attempt at the same symptom, or the first attempt on a surface whose failures are known to be silent (fire-and-forget async, `catch {}` blocks, best-effort fallback chains). Corollary worth auditing for: every `catch(() => {})` in a dismiss/cleanup path is a future invisible failure — at minimum, log it to the trail.
