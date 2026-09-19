---
stack: [sync, zod, validation, api, local-first]
kind: gotcha
last_verified: 2026-09-18
---

# A strict schema at a sync boundary turns one missing column into a total outage

**One-liner:** strict validation (`.strict()`, `additionalProperties: false`) is correct and is what you want — but on a **sync boundary** it composes with two other ordinary facts, batched writes and an ordered queue, into something much worse than a rejected field. One unknown column rejects the whole batch; the batch never drains; everything queued behind it is stuck forever. The user does not report "my new feature doesn't sync." They report **"nothing syncs any more"**, which sends you hunting a transport bug that does not exist.

## The composition

Three individually-correct decisions:

1. **The server validates strictly.** An unexpected key is an error, not something to ignore. Right — silently dropping unknown fields is how data quietly disappears.
2. **Writes upload in batches.** One request per transaction, not per row. Right — it is the only way to keep a write queue efficient.
3. **The queue drains in order.** A failed batch retries rather than being skipped. Right — skipping would reorder writes and corrupt causality.

Now add one column to a client table and forget it in the server's accept-list. The client writes it. The server rejects the *whole payload* for one unknown key. The batch never completes, so the queue never advances, so **every table stops syncing** — including tables that have nothing to do with the change. A one-column omission takes down the sync layer.

## Why the symptom misleads

The blast radius is inverted relative to the cause. The cause is maximally narrow (one column, one table, one commit). The symptom is maximally broad ("sync is down"), and it arrives on surfaces the change never touched. So the instinct is to look where the symptom is — transport, auth, tokens, the sync service's health — and the actual defect is a single missing string in a registry, in a diff you already reviewed and approved.

Worse, the failure is **silent on the client** by design: a retrying queue is a normal state, not an error state. There is nothing to catch. The queue is behaving exactly as specified.

## Fixes, in the order worth trying

**1. Assert the client's write shape against the server's accept-list, mechanically.** This is the only fix that prevents rather than mitigates. Whatever your contract checker compares, it must include the direction "a column the client WRITES that the server will NOT ACCEPT". See the caveat in [n-copies-of-truth-drift-guard.md](./n-copies-of-truth-drift-guard.md) — a checker that validates one layer as a permitted *superset* of another is structurally unable to express this, and will stay green through the entire outage.

**2. Make the boundary's rejection loud and specific.** A strict rejection should name the offending key and the table, and that message must reach somewhere a developer looks. "Validation failed" in a retry log is indistinguishable from noise.

**3. Consider whether the queue should quarantine rather than block.** A poison batch that blocks all progress trades one broken feature for a broken product. Parking the failing transaction after N attempts and continuing keeps the blast radius equal to the cause — at the cost of an out-of-order write you must then reconcile. This is a real trade, not a free win; take it only where the ordering guarantee is weaker than the availability one.

**Not a fix: relax the schema.** Dropping `.strict()` converts a loud total failure into a silent partial one — the column is accepted, stripped, and never stored, and you find out weeks later when someone asks where their data went. That is the mirror-image failure documented in [monorepo-stale-dist-zod-strip.md](./monorepo-stale-dist-zod-strip.md). Strict-and-blocked is genuinely better than lax-and-lying; the goal is to catch it before deploy, not to make the boundary permissive.

## How to confirm it in 30 seconds

Add a junk key to one outgoing row from the client and watch. If the whole batch fails and the queue stops advancing for *unrelated* tables, you have this shape. If only that row is rejected and other tables keep flowing, your queue quarantines and you are exposed to a much smaller version of this problem.

## The general rule

**Validation strictness, write batching and ordered delivery are each safe alone and dangerous multiplied.** Any boundary with all three turns "a field I forgot" into "the pipe is closed." Before adding strictness to a boundary, ask what the *unit of failure* is: if rejecting one row fails a batch, and a failed batch halts a queue, then your unit of failure is not the row — it is the entire queue, forever.

This generalises past Zod and past sync: a message broker with an ordered partition and a strict deserializer, a migration runner that stops on first error, an ETL step that rejects a malformed record — all the same shape. Ask "what is stuck behind this?" before "what failed?"

## What NOT to do

- Don't debug the transport first. The transport is fine. It is faithfully retrying a request that will never succeed.
- Don't add the missing column and move on. The column was the trigger; the absent mechanical check is the defect, and it will fire again on the next table anyone adds.
- Don't infer from a green contract check that the layers agree. It may be checking a relationship that cannot see this class of mismatch at all.

## Related

- [n-copies-of-truth-drift-guard.md](./n-copies-of-truth-drift-guard.md) — the drift-guard playbook this outage belongs to, including why the guard was green and what a repo-only checker structurally cannot see.
- [monorepo-stale-dist-zod-strip.md](./monorepo-stale-dist-zod-strip.md) — the opposite failure: a non-strict schema silently stripping the new column instead of rejecting it.
- [local-first-sync-with-d1.md](./local-first-sync-with-d1.md) — the outbox/ordering patterns that supply the "everything behind it is stuck" half.
