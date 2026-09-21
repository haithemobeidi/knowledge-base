---
stack: [process, android, compose, testing, ledger]
kind: process
last_verified: 2026-09-21
---

# When the test build changes, re-check every open item that was reported by eye under the old build before carrying it forward

**One-liner:** a perception report ("the animation is jagged", "it lags", "it flashes") is a report about a build, not about the code; when the build under test changes in a way that touches rendering (debug → release/R8, a profiler on or off, a cache or decode change), every open eye-reported item gets one deliberate re-look before the next wrap carries it, or the ledger fills with items whose symptom is already gone and a session gets planned around a fix for nothing.

## Symptom

- An animation was reported as "a cut, not a flight" under the debug build and logged with a hypothesis (fixed tempo, too little travel) and a planned fix. Two sessions later the test build switched to release code because a *different* surface measured laggy on debug and smooth on release. Three wraps carried the animation item forward verbatim. When the fix finally came up, the user opened the surface and said "it works, how'd that not get recorded?" Nothing had been built; the debug build's overhead was the symptom.
- The tell: the item's text describes a *feel* and names a build state ("the Fold runs the debug build") in the same session's handoff line.

## Cause

The ledger's discipline is "an item stays open until someone dispositions it", which is right for facts. Perception items are facts *about a build*. The wrap protocol has no step that asks "did the thing this item was seen on change?", so a build switch, which is itself logged as a win, silently invalidates a class of open items without anyone re-reading them.

## Fix

1. When a wrap records a test-build change (debug → release, a perf build becoming the test build, a decode/cache change on the surface under test, a profiler removed), **list the open items that were reported by eye** (feel, lag, jank, flash, jag, shimmer) and re-check each with one deliberate look on the new build before the next wrap. Close the ones that are gone as "not reproducible on <build>, nothing built", with the hypothesis marked unproven, not confirmed.
2. When minting an eye-reported item, **name the build it was seen on** in the line ("seen on the debug build"), so the re-check can be found by grep later.
3. A closed-as-not-reproducible item names the surface AND the build in its closing line, so a recurrence is a fresh line with both, not a reopen with neither.

## Related

- `instrument-before-patching.md` — measure before building the fix; this is its calendar-shaped cousin.
- `negative-control-before-trusting-a-probe.md` — the same instinct for probes.
