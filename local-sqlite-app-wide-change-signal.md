---
stack: [local-first, sqlite, tauri, react, sync]
kind: pattern
last_verified: 2026-07-20
---

# A local DB with no live-query layer needs ONE explicit "data changed" signal — or writers outside the original poke inventory go stale silently

**One-liner:** if your UI reads a plain local database (not a watchable/reactive store), no screen can subscribe to changes — every screen only re-queries when something explicitly tells it to. Building that "something pokes it" wiring feature-by-feature, ad hoc, guarantees you'll eventually add a writer (a second window, a background sync engine, an external event) that nobody's poke inventory covers, and it goes stale with no error anywhere.

## The shape of the trap
Two data layers can coexist in one app with very different change-notification guarantees: a sync engine's own local replica is often watchable/reactive by design, while the app's actual query surface (a separate local SQLite file the sync layer mirrors *into*) frequently isn't. If your screens query the second layer, "the sync engine mirrored the row" and "the currently-mounted screen knows to re-render" are two completely separate facts — mirroring correctly is necessary but not sufficient.

The failure compounds because poke wiring gets built per-feature: screen A gets a refresh bump wired for the actions its author was thinking about (mount, an explicit sync button, window focus). Every writer outside that mental model — a **second window** in a multi-window desktop app, the sync engine's own background arrivals, another screen's write this screen's author didn't anticipate — reaches zero consumers. Multiple independent-looking bugs (a stale grid order, a stale detail screen, a stale list after a background save from another window) are frequently **one root cause wearing different clothes**. If you're finding "yet another place that doesn't refresh" more than once in a session, stop patching sightings individually and look for the systemic gap.

## The fix: one coalesced signal, N producers, ONE consumer that already exists
- **One event/signal** ("data changed"), tagged with a source for debugging — not a bespoke custom event per writer.
- **Every write choke point is a producer**, including ones outside the obvious in-process call graph: bridge writes across windows with a native app-level event (don't assume "same app" means "same JS heap" in a multi-window desktop shell), and make the sync engine's own write-through/mirror step announce when it *actually changed rows*, not just when it ran.
- **One consumer**: wire the new signal into the top-level "refresh key" / query-invalidation mechanism most apps already have for their explicit refresh button, coalesced (leading-edge instant + a short trailing debounce to fold a burst of arrivals into one re-render). You're not converting every screen to a live query — you're making sure the ONE lever that already re-queries everything gets pulled by everything that should pull it.
- **Retire only the genuinely redundant ad hoc pokes it replaces.** Audit each existing custom event/counter individually; fold it in, or leave it with a comment stating why it's semantically distinct (see below).

## The debugging trap this pattern's own postmortem surfaced: don't assume the wiring is what's missing
When this was implemented for real, the flagship symptom (a stale grid after a cross-device sync) turned out NOT to be "no signal existed" — a refresh-bump wire had existed for a long time, and the consumer WAS listening. The actual bug was one layer deeper: the mirror step had a re-entrancy guard that silently **dropped** an incoming change notification arriving while an earlier batch was still being mirrored (a large first batch on cold boot creates exactly this window) — so the data never even reached local storage, and no amount of "re-query on signal" fixes a re-query that reads a row that was never written. Lesson: when "add the missing signal" is the theorized fix, verify the data actually reaches the layer a re-query would read from *before* assuming the signal itself is the gap. A debug trace at the mirror boundary (log every fire, every drop, every batch edge) is what caught this — not code review.

## Least-privilege signal semantics: don't let a new generic signal steal an existing event's specific meaning
Before adding a broad "data changed" event, audit what your existing per-purpose events actually mean. Some are deliberately narrow for reasons unrelated to refreshing — one real example: an event whose entire job was suppressing a *different*, unrelated end-of-session behavior, not triggering a UI refresh. Folding it into the generic signal would silently break that other behavior. Keep purpose-built events purpose-built; add the generic signal alongside them, not as a blanket replacement for anything you haven't individually verified is redundant.

## Related
- [`derive-dont-track-ui-flags.md`](./derive-dont-track-ui-flags.md) — adjacent family: both are about UI state (a boolean flag; a "should I re-query" moment) hand-maintained via scattered reset/poke call sites instead of derived/centralized, and both bug classes are "a path someone forgot."
- [`n-copies-of-truth-drift-guard.md`](./n-copies-of-truth-drift-guard.md) — a different failure mode (schema shape, not change-notification) from the same "local-first sync has non-obvious invisible failure classes" family.

---
*Captured from Playmoir's BUG-51 reactivity pass, 2026-07-18 — filed as a narrow "library grid order stale" bug, widened same-day to a systemic fix after 3 independent sightings, shipped as one bounded block (4 pause-points, 7 commits), each fix live-verified on real 2-device hardware.*
