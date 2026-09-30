---
stack: [react, typescript, sync, local-first, any]
kind: gotcha
last_verified: 2026-09-24
---

# Check-then-act across an `await`: a sweep that can be entered twice must claim its work before the first `await`

**One-liner:** a boot-time "find the unclaimed rows, then upload each" sweep ran twice at once under React StrictMode. Both runs read the same unclaimed rows before either had stamped one (an `await` sat between the read and the stamp), both minted IDs and both uploaded, leaving 6 cloud rows for 3 local tips. Any guard written *inside* the async body is already too late. The claim has to happen synchronously at call time, before the first `await`. The same trick later fixed a client-side upload pacer that every caller read as "free" at once.

## Case 1: the StrictMode double sweep (Playmoir, 2026-08-01)

- **Symptom:** after shipping tips sync, Postgres held 6 rows for 3 tips, two per tip with different uuids. Only the last uuid was written back locally, so 3 cloud rows were orphans that would have synced down as duplicates. Every gate was green (typecheck, sync contract); it was found by comparing live data.
- **Mechanism:** the bootstrap effect called `void uploadPendingTips()`. StrictMode runs effects twice back to back in dev. The sweep was `SELECT … WHERE uuid IS NULL` → per row `randomUUID()` → upload → `UPDATE … SET uuid`. Both invocations finished the `SELECT` before either reached an `UPDATE`.
- **Fix:** a module-level flag flipped before the first `await`:

```ts
let sweepClaimed = false;
export async function uploadPendingTips() {
  if (sweepClaimed) return 0;   // the second caller arrives to a flag already true
  sweepClaimed = true;           // claimed at CALL time, synchronously
  const db = await getDb();      // first await: too late for any guard below it
  // ...stamp each row's uuid only AFTER its push succeeds, so a failed push
  //    leaves the row eligible for the next launch
}
```

The orphans were hard-deleted, not tombstoned: a tombstone would have synced down as a real deletion for rows that should never have existed.

## Case 2: a shared upload pace every caller read as free (2026-09-24)

A client pacer kept uploads under a server cap (120 presigns/min per account, so one every 600 ms). The naive version read "when is the next slot?" and then awaited, so concurrent callers all saw the same free slot and burst anyway. Reserving the slot synchronously makes them queue:

```ts
const UPLOAD_PACE_MS = 600;
let nextUploadSlot = 0;
async function takeUploadSlot() {
  const now = Date.now();
  const at = Math.max(now, nextUploadSlot);
  nextUploadSlot = at + UPLOAD_PACE_MS;      // reserved before any await
  if (at > now) await sleep(at - now);
}
```

(Why a pace was needed at all, and why its failures were invisible: `silent-refusals-make-clean-logs-meaningless.md`.)

## The rule

- **Anything shaped "read what's free, then take it" that can be entered twice** (StrictMode, a double event, a retry, two tabs, two features) must take its claim synchronously, before the first `await`: a module flag, an in-flight promise (`inflight ??= run()`), or a reserved slot.
- **Don't trust "effects run once in production".** StrictMode is only the dev symptom; real double entry comes from double clicks, reconnects and parallel callers.
- **If a duplicate can still slip through, make the ID deterministic** (derive it from the row's identity) so the second run can't mint a different one and orphan the first.
- **Caveat:** a never-reset flag means no retry within the same launch. That's fine for a boot sweep; for anything else, reset it in `finally` or use the in-flight promise.

## Related

- `restartable-task-generation-counter.md`: the long-running, restartable cousin (StrictMode double-starts a thread).
- `parallel-writers-minting-ids-collide.md`: the same read-then-write race, between agents on a shared file.
- `strict-schema-at-a-sync-boundary.md`: the other invisible sync bug found the same night.
