---
stack: [sync, local-first, crdt, sqlite]
kind: gotcha
last_verified: 2026-09-18
---

# A field only ever written locally still needs a monotonic guard

**One-liner:** the reasoning that skips the guard is *"only this device ever writes this field, so there is no conflict to resolve."* That is true about **writers** and irrelevant to the actual risk, which is **ordering**. The same user on the same account with two devices, or one device replaying an older snapshot after a restore, will hand you your own past. A guard that asks *"did this change?"* accepts it. The guard has to ask *"is this newer?"*

## Why "single writer" is the wrong frame

Single-writer removes *contention*. It does not remove:

- **a second device of the same user**, holding a state from before your last write and syncing it up
- **a restore, reinstall or cache rebuild**, which replays a stale snapshot as if it were current
- **out-of-order delivery**, where a retried older write lands after a newer one
- **a clock that moved**, on any device involved

Every one of those delivers a *legitimate* write carrying an *older* value. A change-detection guard sees a difference and applies it, and the field walks backwards — a "last played" that rewinds a week, a progress marker that un-advances, a counter that drops. It self-corrects on the next local write, which is exactly why it survives: it looks like a glitch, not a bug.

## The fix

Compare, don't just detect:

```ts
// WRONG: any difference wins, including a difference that is older.
if (incoming.lastPlayed !== local.lastPlayed) local.lastPlayed = incoming.lastPlayed;

// RIGHT: only forward.
if (incoming.lastPlayed > local.lastPlayed) local.lastPlayed = incoming.lastPlayed;
```

**When the value itself is a timestamp, `max()` is the whole algorithm.** That is not a shortcut, it is a Max-Register CRDT: `max` is commutative, associative and idempotent, so any delivery order converges to the same result. You need no Lamport clock, no vector clock, no node tiebreaker, and no "last write wins by wall clock" heuristic — because the value *is* the ordering. Two devices replaying each other's history in any sequence land on the same answer.

For a non-timestamp value, you need something to order by, and then you are back to the general pattern in [local-first-sync-with-d1.md](./local-first-sync-with-d1.md) (Pattern 1): carry a per-field `updated_at`, accept if strictly newer, reject silently otherwise.

## The alternative that looks cleaner and is worse

**Keep the column off the wire entirely.** If only this device writes it, do not sync it; then it cannot move backwards. This is genuinely supported and genuinely tempting — and it trades a transient flicker for **permanent per-device divergence**. Device A's value and device B's value are now independent forever, and the user's second device shows a different answer to the same question with no path to reconciliation. A field that visibly rewinds for one second is a smaller problem than a field that is quietly wrong on one device for its lifetime.

Take the exclusion only when the field is genuinely device-local in *meaning* (a window position, a local cache path), not merely device-local in *authorship*.

## How to confirm it in 30 seconds

Sync device A. On device B, sign in and let it pull, then put B offline, make a change on A, bring B back. Or cheaper, with one device: take a backup, advance the field, restore the backup, and watch whether the restored older value overwrites the newer one after a sync pass. If it does, the guard is change-detection.

## The general rule

**"Who writes it" tells you about conflict. "When was it written" tells you about correctness.** Any field that crosses a sync boundary needs an ordering answer even when it has exactly one author, because delivery order is not authorship. Ask of every synced field: *if I received the value I held yesterday, right now, would I take it?* If yes, the field can rewind.

And when the answer is monotonic by nature — timestamps, high-water marks, counters that only increase, "furthest progress reached" — reach for `max()` and stop designing. The value orders itself.

## What NOT to do

- Don't reach for a Lamport clock or vector clock for a value that is already a timestamp. You would be adding an ordering mechanism on top of an ordering.
- Don't resolve with "whichever arrived last." Arrival order is the thing that is unreliable; it cannot also be the referee.
- Don't use `>=` where `>` will do. Equal values are already converged; accepting them buys nothing and costs a write.
- Don't assume the guard is unnecessary because you tested on one device. One device is the configuration in which this bug is undetectable.

## Related

- [local-first-sync-with-d1.md](./local-first-sync-with-d1.md) — Pattern 1 (per-field timestamp comparison) and Pattern 14 (pull vs outbox ordering); this lesson is the narrower corollary that the guard is still required with a single writer.
- [tombstone-vs-hide-for-mirrored-data.md](./tombstone-vs-hide-for-mirrored-data.md) — the same "is it newer, not did it change" rule applied to clearing tombstones.
- [local-fixture-reverts-under-authoritative-sync.md](./local-fixture-reverts-under-authoritative-sync.md) — the neighbouring failure where an authoritative pull overwrites a legitimate local value.
