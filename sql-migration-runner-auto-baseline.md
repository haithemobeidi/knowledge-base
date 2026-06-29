---
stack: [postgres, node, migrations]
kind: howto
last_verified: 2026-06-29
---

# A safe SQL migration runner (with auto-baseline on adoption)

**Problem:** you have numbered `.sql` migrations you've been running by hand (pasting into a dashboard SQL editor). You want one command — but a naive "run every file" runner will **wipe data** if any early migration starts with `drop table if exists` (common when an early migration replaced a throwaway spike table) and you point it at a DB that's *already* migrated.

## The core idea
Track applied migrations in a `_migrations` table; only run files not yet recorded. The subtlety is **adoption**: the first time you run the tool against a DB that was set up by hand, `_migrations` is empty, so a naive runner thinks NOTHING is applied and re-runs everything — including the destructive `drop table`s.

**Fix: auto-baseline.** On first run, if the tracker is absent BUT the schema clearly already exists (a known core table is present), **record every current file as applied and run NONE.** A truly fresh DB (core table absent) runs everything in order.

## Detection logic
```
trackerExisted = <_migrations table exists?>
ensure _migrations table (skip in --dry-run)
applied        = rows in _migrations (empty set if it didn't exist)
pending        = files not in applied

if pending is empty:                          -> up to date, nothing to do
else if !trackerExisted && coreTableExists:   -> BASELINE: insert all pending as applied, run NONE
else:                                          -> run each pending file in its own transaction, record it
```

## Implementation notes
- **One transaction per migration** (`BEGIN; <file sql>; INSERT _migrations; COMMIT`). On failure, `ROLLBACK` and STOP — earlier migrations stay committed; fix and re-run.
- **Multi-statement files:** with node-postgres, `client.query(fileText)` (no params → simple protocol) runs multiple `;`-separated statements in one call. Postgres DDL is transactional, so the wrapper gives atomicity per file.
- **`--dry-run` must write NOTHING** — don't even `CREATE TABLE _migrations` in dry-run; treat a missing tracker as an empty set. This lets you preview the plan against a live DB safely (read-only).
- **Reuse the app's DB connection config** (same `DATABASE_URL`, same TLS/CA settings) so the runner connects identically to the server.
- Numbered prefixes (`0001_`, `0002_`) sort lexically into apply order — keep the zero-padding.
- Idempotent: a second run reports "up to date."

## Verify before trusting it on prod
1. `--dry-run` against the live DB first (read-only). It should report the baseline plan: *"existing schema detected, would baseline N, run none."*
2. Run for real → it baselines (records files as applied, executes none).
3. Run again → must say "nothing to apply." That three-step check proves both the detection and the idempotency.

## Note: local vs cloud migrations
This is for the **cloud** DB (the one you hand-migrate). A local embedded DB (e.g. Tauri's SQLite via tauri-plugin-sql) usually has its **own** migration ledger that auto-runs on app launch — keep the two separate; this runner is not for those.

---
*Captured from the Playmoir migration runner, 2026-06-29 (`apps/server/migrate.js`, Supabase Postgres).*
