---
stack: [sqlite, local-first, sync]
kind: gotcha
last_verified: 2026-08-13
---

# SQLite upsert against a PARTIAL unique index fails at prepare time — and a sync layer that catches errors will hide it for months

**One-liner:** `ON CONFLICT(col) DO UPDATE` does not match a *partial* unique index (`... WHERE col IS NOT NULL`) unless the conflict target repeats that same `WHERE` clause — it throws when the statement is **prepared**, before touching a row, so it fails 100% of the time rather than intermittently; and if it lives inside a sync loop whose `catch` exists to stop one bad row from killing the batch, the feature is simply dead and looks exactly like "the server sent nothing."

## The symptom

A per-game "tips" feature synced **up** to the cloud from every device and never came **down** to the desktop. Nine rows sat in Postgres; the desktop's local table held exactly one — the one it had typed itself.

The first diagnosis was infrastructure, and it was wrong in an expensive way: the sync engine's rules are deployed from a dashboard, not the repo, so "the deployed rules must be stale" is an *extremely* plausible story that fits every symptom. It was re-deployed. Nothing changed. That dead end burned a session, because the real fault was one line of SQL in the client and there was no signal pointing at the client at all.

The tell that should have redirected it sooner: **sibling tables synced down fine.** Journal entries, screenshots and audio all arrived on the same connection, through the same code path, on the same boot. When one table out of six is broken, the transport is not the suspect.

## The mechanism

The local table used the standard local-first shape — an integer rowid PK plus a nullable cloud UUID, uniquely indexed only where present, so that pre-cloud rows can all sit at `NULL` without colliding:

```sql
CREATE TABLE game_tips (
  id   INTEGER PRIMARY KEY AUTOINCREMENT,
  uuid TEXT,
  ...
);
CREATE UNIQUE INDEX game_tips_uuid_unique
  ON game_tips (uuid) WHERE uuid IS NOT NULL;   -- PARTIAL
```

The download mirror upserted on that uuid:

```sql
INSERT INTO game_tips (uuid, ...) VALUES (?, ...)
ON CONFLICT(uuid) DO UPDATE SET ...             -- ❌
```

**SQLite rejects this at prepare time:**

```
Error: in prepare, ON CONFLICT clause does not match any PRIMARY KEY or UNIQUE constraint
```

The conflict target `(uuid)` is matched against the table's *uniqueness constraints*. A partial index only qualifies if the target carries the index's predicate too. Without it there is no non-partial unique constraint on `uuid`, so there is nothing to match — and because it fails at prepare, it fails on the very first row, every time, forever. There is no "some rows got through."

The error names a constraint that *visibly exists* in your schema, which is exactly why it reads as nonsense and gets misfiled as an ORM or driver problem.

### What actually matches (measured, SQLite 3.50.6)

| Conflict target | Result |
|---|---|
| `ON CONFLICT(uuid)` | ❌ prepare error |
| `ON CONFLICT(uuid) WHERE uuid IS NOT NULL` | ✅ matches |
| `ON CONFLICT(uuid) WHERE uuid NOT NULL` | ✅ matches — the comparison is semantic, not textual |
| `ON CONFLICT(uuid) WHERE uuid > ''` | ❌ prepare error — *implies* non-null, but SQLite is not a theorem prover |
| `ON CONFLICT DO UPDATE` (no target at all) | ✅ works, but see below |

Two things worth knowing from that table. The predicate match is **semantic within narrow limits** — an equivalent spelling is fine, a logically-stronger predicate is not — so "close enough" is not a strategy; copy the index's predicate verbatim.

And **omitting the conflict target entirely is legal for `DO UPDATE`** (contrary to a common belief that only `DO NOTHING` may omit it) and does resolve the conflict. It is still the worse fix: a targetless clause catches a conflict from *any* constraint on the table, including the primary key, so a genuine rowid collision you would want to hear about gets silently folded into your update path.

## Why it hid for months — the part worth internalizing

The SQL bug is a five-minute fix. The interesting failure is that a feature was **completely non-functional from the day it shipped** and nobody could tell.

**1. The resilience `catch` erased the only signal.** The sync write-through wrapped each mirror in the usual guard:

```js
try   { await mirror(rows) }
catch (err) { console.warn('[write-through] mirror error:', err) }   // ← the whole story, gone
```

That guard is *correct* as a resilience choice — one malformed row must not kill the sync loop for every other table. But it flattens two completely different worlds into the same observable state:

- a transient, per-row failure that will resolve itself, and
- a statement that can never execute under any circumstances

Both render as "the table is empty." A `console.warn` is not an error surface: the product owner never opens devtools, and in a desktop webview the console dies the moment the panel closes.

**2. Local-first hides down-leg failures structurally.** This is the part that generalizes past SQLite. In a local-first app, writes made *on this device* go straight to local storage — they never touch the download mirror. So the feature looked completely alive on whichever machine you were sitting at. Type a tip, it appears, it persists across restarts, it even reaches the cloud. Every check a developer runs by reflex passes.

The down-leg has no user on the other side of it. Nothing *asks* for those rows, so nothing notices they never came. It took a factory reset (which cleared the local rows that were masking the gap) **plus** a second client written months later (which read the same data over plain REST and correctly showed rows the desktop didn't have) before the absence became visible at all.

> **The general shape:** any code path whose only failure signal is "less data than expected" is invisible by construction. You cannot notice an absence you were not counting.

## The fix

Repeat the index's predicate in the conflict target:

```sql
INSERT INTO game_tips (uuid, ...) VALUES (?, ...)
ON CONFLICT(uuid) WHERE uuid IS NOT NULL DO UPDATE SET   -- ✅
  ...
WHERE excluded.updated_at >= game_tips.updated_at
```

Note the two `WHERE`s do different jobs and both belong there: the first identifies *which index* this conflict is about, the second is the guard deciding whether the incoming row actually wins. Easy to conflate, and a reviewer "simplifying" the duplicate-looking clause reintroduces the bug — so leave a comment saying the first one is load-bearing.

## How to audit for it

The bug is a one-line outlier among correct siblings, which is what makes a grep so effective — you are looking for the odd one out, not judging each on its merits:

```bash
# every partial unique index in your migrations
grep -rn "CREATE UNIQUE INDEX" migrations/ -A1 | grep -i "where"

# every conflict target; any hit WITHOUT a WHERE, on a column that has a
# partial index above, is the bug
grep -rn "ON CONFLICT" src/
```

In the real case, five mirrors carried `WHERE uuid IS NOT NULL` and one didn't. A diff of that grep's output against itself finds it in seconds.

**Reproduce before you ship the fix.** A scratch DB built to the migration's exact shape settles it in under a minute, and — because the failure is at prepare time — it reproduces deterministically with no sync stack, no network, and no app:

```bash
sqlite3 scratch.db "CREATE TABLE t(id INTEGER PRIMARY KEY, uuid TEXT);
                    CREATE UNIQUE INDEX t_u ON t(uuid) WHERE uuid IS NOT NULL;"
sqlite3 scratch.db "INSERT INTO t(uuid) VALUES('a') ON CONFLICT(uuid) DO UPDATE SET uuid=uuid;"
```

Extract the statement from the source file rather than retyping it — retyping is how you accidentally test the fixed version.

## The general rule

Three, in order of how far they travel:

1. **A partial index is a different constraint from the index it looks like.** Anything that references it — upserts, `ON CONFLICT`, some ORMs' `onConflict` builders — must carry the predicate. Copy it verbatim.
2. **Never let a catch-all swallow a prepare/compile-time error.** A statement that cannot compile is a *build defect wearing a runtime error's costume*: it is 100% reproducible, it will never succeed on retry, and it is exactly the class a resilience guard should re-raise rather than absorb. Row-level errors are what the guard is for; statement-level errors are not.
3. **Instrument the direction nobody is waiting on.** In any sync system the download path has no user to complain for it. A per-stream "last mirror failed / last successful sync" line in a diagnostics panel is cheap, and it is the difference between finding the next one of these in a day and finding it in a quarter.

## Related

- [tauri-sqlite-direct-sqlx.md](./tauri-sqlite-direct-sqlx.md) — the same "silent SQL failure in a local-first stack" family, including the migration-not-registered footgun and the `selectRows()` remap trap.
- [cross-boundary-dev-events.md](./cross-boundary-dev-events.md) — the structured ring buffer that makes swallowed errors observable after F12 closes. This bug is the strongest argument for it.
- [local-first-sync-with-d1.md](./local-first-sync-with-d1.md) — the surrounding sync patterns (outbox, UUID identity, tombstones).
- [instrument-before-patching.md](./instrument-before-patching.md) — the re-deploy that fixed nothing is what happens when you act on the most plausible story instead of a measurement.
- [powersync-steam-backend-architecture.md](./powersync-steam-backend-architecture.md) — the sync engine this happened in; its dashboard-deployed rules are what made the wrong diagnosis so believable.
