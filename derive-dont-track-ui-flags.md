---
stack: [react, frontend, state-management, data-modelling]
kind: pattern
last_verified: 2026-07-27
---

# State with N reset paths WILL get stuck — derive it instead

*(Written first about UI flags; the same shape shows up in the database, see "The same shape in your data model" below.)*

**One-liner:** if a boolean UI flag has to be explicitly cleared on more than a couple of exit paths (back button, Escape, outside-click, nav-away, a cancel button, a race with another action...), it will eventually get stuck true on whichever path someone forgets to wire up. The fix isn't "find and patch the missing path" — it's eliminating the reset action entirely by **deriving** the flag from state that's already correctly maintained elsewhere.

## The failure shape

A flag like `modalObscuringBackground` or `detailViewBlockingLibrary` starts as its own `useState`, set `true` on open and expected to be set `false` on close. Fine, until close turns out to have more than one door:

- Back button
- Escape key
- Clicking outside
- A sidebar navigation that jumps away without going through the normal close handler
- Browser/router `popstate`
- A "quit" or "cancel" ritual with its own code path
- A race: the user triggers a new open while an old close is still mid-animation

Every one of these needs to remember to clear the flag. Miss any single one and the UI gets stuck in the blocked/obscured/locked state — usually intermittently, usually only on the path nobody tested last, and usually patched 3-5 times across separate sessions because each fix addresses the ONE path that was just discovered broken, not the shape of the bug.

## The fix: derive, don't track

Ask: is there already OTHER state in the component that's true exactly when this flag should be true, and false exactly when it shouldn't? If yes, delete the flag and compute it:

```ts
// BEFORE — an independent boolean every exit path must remember to clear
const [obscured, setObscured] = useState(false);
// ...open path: setObscured(true)
// ...close path A: setObscured(false)
// ...close path B: (forgot!) — obscured stays stuck true forever

// AFTER — derived from state that's already correctly set/cleared elsewhere
const obscured = selectedItemId !== null && !isClosing;
```

`selectedItemId` and `isClosing` both already have to be correct for the rest of the feature to work (the detail view can't render without `selectedItemId`; the close animation can't run without `isClosing`). Riding on state that already has to be right means there's no THIRD piece of state that can independently drift out of sync — the "forgot to clear it on path N" bug class is structurally impossible, because there's no clear-action left to forget.

## The same shape in your data model: derive invalidation, don't handle it

The principle isn't about React, or booleans, or even UI. It's about **any stored fact that N different code paths are each responsible for clearing.** The database version is the same bug with a longer memory: a stale flag in a component dies on refresh, a stale flag in a row is wrong forever.

The canonical shape: a feature that promises "remind me about this in two weeks — unless I come back on my own first." The obvious implementation stores `remind_at` and then has to *notice* the coming-back:

- a listener on the app's own "user did the thing" path
- another on the background/OS watcher that detects it happening outside the app
- another on a manual entry the user creates by hand
- another on the sync path, because it might have happened on their other device
- a scheduled job to clean up reminders that are no longer relevant
- and a race to reason about, between "they came back" and "the reminder fired"

Six things to get right, and every one you miss produces the exact failure the feature exists to avoid: nagging someone who already came back.

**The derived version stores one more timestamp and deletes all six.** Alongside *when it fires*, store *when the promise was made*:

```sql
-- reminder_at      when the nudge should surface
-- reminder_set_at  when the user asked for it

-- "is this reminder still valid?" — no listener, no job, no race
WHERE reminder_at IS NOT NULL
  AND (last_played_at IS NULL OR last_played_at <= reminder_set_at)
```

`last_played_at` was already maintained, for other reasons, by machinery that already had to be correct. Coming back moves it past `reminder_set_at`, and the reminder stops being valid **by construction** — not because anything observed the return and reacted to it.

What this buys, beyond fewer lines:

- **No missed events.** There is no subscriber to forget to register on the seventh path that means "came back."
- **No cleanup job.** Invalid rows aren't garbage to collect; they're just rows the predicate stops matching.
- **No race.** "Came back" and "fired" can't interleave wrongly, because firing is a read of current state rather than a scheduled action queued in the past.
- **Retroactively correct.** Rows written *before* the feature existed evaluate correctly the moment the column lands — an event-driven design can only ever know about events that happened after you started listening.
- **Free across devices.** Two timestamps replicate through whatever sync you already have. An event-driven version needs the *event* to reach the other device, which is a much harder thing to guarantee than a value.

### The recipe

When you're about to write "on X, clear Y," stop and ask two questions:

1. **Is X already recorded somewhere durable?** Usually yes, and usually as a timestamp you already keep — `last_seen_at`, `updated_at`, `last_login_at`, a status column, a monotonically increasing counter.
2. **Can Y be re-expressed as a comparison against it?** If so, store whatever anchor makes the comparison possible (typically "when this rule was established") and delete the clearing logic entirely.

The cost is usually one extra column. The saving is every future path that would otherwise have had to remember to clear it.

### When it doesn't apply

- **The invalidating event leaves no durable trace.** If nothing records that X happened, there's nothing to compare against, and you genuinely need to observe it. (Consider recording it — a timestamp column is cheaper than a subscriber network.)
- **You need "exactly once" semantics.** Derived validity is a predicate, so it's naturally idempotent and stateless; if the thing must fire exactly once and never again, you still need to record the firing.
- **The comparison gets expensive at scale.** A predicate over an unindexed column on millions of rows is worse than a maintained flag. Index it, or accept the flag with its N paths — but make that a measured decision, not the default.

## When this applies

- The flag is a pure function of state you already track for other reasons (existence of a selection, an in-progress-transition marker, a count being zero/non-zero).
- You've already found yourself patching "flag stuck true" bugs more than once for the same flag — that's the signal the tracked-boolean approach has structurally too many exit paths, not that you haven't found the last one yet.

## When it doesn't apply

- The flag genuinely carries information no other state has — e.g. "the user explicitly dismissed this warning" isn't derivable from anything else; it has to be its own tracked fact (and in that case, the number of paths that can SET it is usually small and well-defined, unlike close/exit paths which tend to multiply over a project's life).
- Deriving from multiple fast-changing pieces of state can occasionally introduce a one-render flicker if they don't update atomically — verify the derived value is correct across a render, not just eventually-consistent.

## How to spot candidates in an existing codebase

Grep for `useState` booleans whose setter appears in more than 2-3 distinct call sites/handlers within the same feature. That fan-out is the tell — a flag set/cleared from many places is a flag one of those places will eventually mis-handle. Check whether the same true/false shape already exists as a computable expression over other state before adding yet another explicit clear call to the newest exit path.

---
*Generalized from a real recurring bug (5+ patches across sessions before the structural fix) — the tracked flag was a "library view is obscured/blurred behind an open detail panel" boolean with 8 separate paths that could close the detail. Replaced with `selectedId !== null && !closing`.*
