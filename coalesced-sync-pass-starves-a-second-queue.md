---
stack: [sync, local-first, mobile, concurrency]
kind: gotcha
last_verified: 2026-08-15
---

# A "work already done" skip on a serialized work loop must check EVERY queue the loop drains

**One-liner:** If a mutex-serialized sync pass collapses redundant callers with "someone else's pass just ran and the queue is empty, so my work is done," that emptiness check silently becomes a lie the day the loop grows a *second* queue — the collapsed pass was the only one that would have drained it, and the starved queue presents as "feature X randomly never syncs" with every component's logs reading clean.

## The symptom

Phone-recorded voice memos synced their metadata row instantly but their audio bytes never reached object storage — **for notes, every time; for sessions, never**. Both entry types ran byte-identical attachment code. The upload queue on-device held the file intact, marked ready. No error was logged anywhere: not by the uploader (never ran), not by the outbox (drained fine), not by the server (applied everything it was sent).

The flow-specific shape is what made it expensive: "notes are broken, sessions work" points hard at the notes code path, and the notes code path was innocent.

## The mechanism

The sync pass was serialized behind a mutex with a ticket-collapse optimization, verbatim pattern:

```kotlin
val ticket = syncPasses
syncLock.withLock {
    // "a call that waited through someone else's complete pass, with
    //  nothing new queued since, has had its work done"
    if (syncPasses > ticket && outbox.count() == 0) return lastReport
    return syncPass().also { syncPasses += 1 }
}
```

A save fires two passes back-to-back: pass A (from the row write) and pass B (from the attachment staging). Pass A takes the lock first, pushes the rows, and empties the **outbox**. Pass B — the only pass that knows the WAV is waiting — then wakes, sees a completed pass and an empty outbox, and skips itself as redundant. The bytes sit in the **pending-uploads queue**, which the guard never looked at, until some unrelated future pass drains them.

The killer detail: the guard was *correct when written*. The pending-uploads queue was added months later by a different feature, and nothing forced the guard to learn about it.

**Why sessions "worked":** saving a session also triggered an AI-summary round-trip whose result queued a row write ~5–60 seconds later — a real pass with a non-empty outbox, which drained the byte queue as a side effect. Notes had no follow-up trigger. The masking wasn't design; it was luck, and it made a global bug look flow-specific.

## The diagnosis pattern (transferable on its own)

- **Cloud row with `created_at == updated_at`** where a post-upload stamp should have touched it → the stamp op was never applied.
- **The server's applied-batch log is ground truth for arrival order.** One `console.log("applied N op(s): PUT xxxx, PATCH yyyy")` per batch let the healthy flow (+62s stamp in a follow-up batch) be distinguished from the starved one (no stamp batch, ever) in seconds.
- **Client queues all empty + no error logs + server never saw the op** = the op was *skipped*, not failed. Look for a dedup/coalesce/debounce guard, not an error path.

## The fix and the rule

The guard's emptiness check must enumerate every queue the pass drains:

```kotlin
if (syncPasses > ticket && outbox.count() == 0 && pendingUploads.count() == 0) return lastReport
```

**The rule:** any "skip, the work's been done" fast path on a shared work loop encodes a list of what "the work" is. That list WILL drift as the loop grows responsibilities, and the failure is silent by construction (skipping is the success path — nothing logs). When adding a queue to an existing loop, grep for every early-return/coalesce guard on that loop and teach each one about the new queue — or better, have the guard ask the loop for a single `hasPendingWork()` that owns the list in one place.

## Related

- [[sqlite-upsert-against-a-partial-index]] — the sibling silent-sync-failure: an error *swallowed*; this one is an op *never attempted*. Between them: when sync "sent nothing," check both the catch blocks and the skip paths.
- [[tombstone-vs-hide-for-mirrored-data]] — the third family member: an op that arrives but no-ops against a row that doesn't exist yet.
