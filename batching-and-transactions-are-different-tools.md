---
stack: [sqlite, sql, sync, performance]
kind: gotcha
last_verified: 2026-09-18
---

# Batching and transactions are different tools, and code that confuses them fails in both directions

**One-liner:** batching is about **how many round trips**; a transaction is about **what is allowed to be half-done**. They look interchangeable because both turn "many operations" into "one operation," so codebases reach for whichever they learned first and inherit the other one's failure mode — either a chunked write that tears a logical record in half, or a transaction reached for as a performance tool that a pooled connection layer then refuses outright.

## The two directions

**Direction 1 — batching used where atomicity was needed.** You chunk a large write to respect a request limit, and the chunk boundary falls inside a logical unit. Worked example in [local-first-sync-with-d1.md](./local-first-sync-with-d1.md) (Pattern 9): a 595-row backfill produced 479 orphan rows because ~50 records had one field land in chunk N+1 while the rest landed in chunk N. Every chunk succeeded. The data is wrong anyway, because the unit of *success* was never the unit of *meaning*.

**Direction 2 — a transaction reached for as a speed fix, on a layer that will not give you one.** You have 600 inserts and they are slow, so you wrap them in `BEGIN` / loop / `COMMIT`. On a **pooled** connection layer this can fail outright — the statements are not guaranteed to land on the same physical connection, and you get `SQLITE_BUSY` (or a silently useless transaction that spans nothing) while a single multi-row `INSERT` of the same 600 rows sails straight through. Measured here at roughly **700ms per launch**, spent because the code reasoned about transactions when the problem was round trips.

The second direction is the one that hides, because the comment in the file is usually *correct about transactions* and simply about the wrong subject.

## Ask which problem you actually have

| Symptom | You want | Shape |
|---|---|---|
| This is slow; each row is a round trip | **batching** | one multi-row statement, or one request carrying N ops |
| A partial result would be corrupt or unreadable | **a transaction** | `BEGIN` … `COMMIT`, all-or-nothing |
| Both | **both**, deliberately nested | batch for the round trips, transaction around a logical unit |
| A request/payload limit forces me to split | batching — and now **the split must respect the unit** | chunk on record boundaries, never on row count alone |

The fourth row is the one that bites. Once an external limit forces chunking, you have introduced a failure boundary, and it is your job to place it somewhere harmless. Chunk by *logical record*, not by flat row count, so a torn chunk is impossible by construction.

## Fixes

**For speed, collapse round trips, don't wrap them.** One statement with many value tuples, or the driver's batch API:

```ts
// 600 inserts as one statement — no transaction needed, no pool assumptions.
const rows = items.map(() => '(?, ?, ?)').join(',');
await db.execute(`INSERT INTO unlocks (game_id, name, at) VALUES ${rows}`, flatParams);
```

**For atomicity, use a transaction and make sure you really have one.** On a pooled layer that means an API that hands you a connection to hold (`db.transaction(cb)`, a reserved connection), not bare `BEGIN` statements fired at a pool. If the layer cannot promise you one connection, it cannot give you a transaction, whatever the SQL says.

**When an external limit forces a split, make the chunk the unit of meaning.** Group by record first, then pack groups into chunks until the limit; never slice a flat array of fields.

## How to confirm it in 30 seconds

Fire your `BEGIN`, then from the same code path run a query that would be invisible inside the transaction (or check the driver's "in transaction" flag if it exposes one). If you are not actually in a transaction, you will find out immediately rather than during the first partial failure in production. For the performance direction: time one multi-row statement against your `BEGIN`/loop/`COMMIT` on real row counts — if the single statement wins, you never wanted the transaction.

## The general rule

**Name the property you need before naming the mechanism.** "Fewer round trips" and "no half-states" are different requirements with different solutions, and a design that says "wrap it in a transaction for speed" or "chunk it, it'll be fine" has skipped the naming step. The tell in a codebase is a comment that reasons carefully about *one* of the two properties next to code that needed the other.

## What NOT to do

- Don't assume a transaction makes things faster. Sometimes it does (fewer fsyncs), often it does not, and on a pooled layer it may not exist at all.
- Don't chunk by row count when rows belong to records. Pick the boundary deliberately or the boundary picks itself, badly.
- Don't swallow `SQLITE_BUSY` with a retry and move on. Busy here is usually the layer telling you the transaction you think you have is not the transaction you have.
- Don't nest a transaction per chunk and call the whole backfill atomic. N atomic chunks are not one atomic operation, and the orphan-row failure above is exactly what that misreading produces.

## Related

- [local-first-sync-with-d1.md](./local-first-sync-with-d1.md) — Pattern 9 is direction 1 fully worked, with the orphan-row count.
- [sqlite-upsert-against-a-partial-index.md](./sqlite-upsert-against-a-partial-index.md) — the other place SQLite's specifics defeat a correct-looking write.
- [sql-migration-runner-auto-baseline.md](./sql-migration-runner-auto-baseline.md) — where one-transaction-per-unit genuinely is the right call.
