---
stack: [cloudflare-worker, d1, sqlite, tauri]
kind: architecture
last_verified: 2026-05-14
---

# Local-First Sync to Cloudflare D1 — Patterns that survived contact with reality

> One month of building cross-device sync taught us roughly a dozen things that aren't in any tutorial. Most of them caused production incidents before we figured them out. This is the surviving design.

## The Problem

You're building a local-first app: SQLite (or similar) on each device, cloud as an "authoritative-but-optional" mirror. Users want their data to appear on a second device without manual export/import. The naive approach — "sync the rows" — fails in subtle ways once two devices write concurrently or one device gets reinstalled.

This lesson is the patterns we used to make local-first sync against Cloudflare D1 actually work, including the bugs we shipped (and shipped fixes for) along the way.

---

## Architecture: 3 layers, 1 wire format

```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ Frontend writes │──→ │ Local outbox     │──→ │ Cloud Worker     │
│ (React/TS)      │    │ (Rust IPC)       │    │ (Hono on D1)     │
│                 │    │                  │    │                  │
│ trackChanges()  │    │ sync_push        │    │ /api/sync/push   │
│ on every INSERT │    │ sync_pull        │    │ /api/sync/pull   │
│ /UPDATE         │    │ (sqlite outbox)  │    │ (D1 + R2)        │
└─────────────────┘    └──────────────────┘    └──────────────────┘
```

Frontend feature code never talks to the cloud directly. It writes to a local `sync_outbox` table via `trackChanges()` and the Rust layer drains it. This decoupling is what makes the app work offline — when the Worker is unreachable, writes accumulate in the outbox and drain whenever connectivity returns.

---

## Pattern 1: Field-level outbox, NOT row-level

**Wrong:** queue whole rows. `INSERT INTO sync_outbox (table, row_id, row_json) VALUES (...)`.

**Right:** queue individual field changes. Each row is `(table, row_id, field, value, updated_at, uuid, parent_uuid)`.

Why: field-level is what makes per-field last-write-wins work. Device A edits notes; Device B edits status; both pushes drain cleanly and both edits land. Row-level forces you to merge JSON blobs or pick a winner-take-all, which destroys real user edits when two devices touch different fields on the same row.

The cloud stores a `field_timestamps` JSON column on each table that records when each field was last updated. Conflict resolution is per-field — compare the incoming `updated_at` against `field_timestamps[field]`, accept if newer, otherwise reject silently.

```sql
-- Local outbox row shape
CREATE TABLE sync_outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  table_name TEXT NOT NULL,           -- 'games', 'journal_entries', etc.
  row_id INTEGER NOT NULL,            -- local SQLite rowid
  uuid TEXT,                          -- cross-device identity (Pattern 2)
  parent_id INTEGER,                  -- for child rows: local parent rowid
  parent_uuid TEXT,                   -- for child rows: parent's cross-device uuid
  field TEXT NOT NULL,                -- 'notes', 'status', 'deleted_at', etc.
  value TEXT,                         -- JSON-encoded value; NULL = column is NULL
  updated_at INTEGER NOT NULL,        -- ms since epoch, set by writer
  user_id TEXT                        -- account scoping (Pattern 3)
);
```

---

## Pattern 2: UUID v4 from day 1 — NEVER use AUTOINCREMENT for cross-device identity

This was the most painful lesson. We initially used local SQLite `AUTOINCREMENT` ids as the cross-device identifier. It collapses the moment two devices independently observe the same logical row (e.g. both scan the same Steam library):

- Device A inserts game "ESO" with `id=42`. Pushes to cloud.
- Device B is fresh-installed, scans Steam, inserts game "ESO" with `id=42` (autoincrement starts at 1 on each device).
- Device B pushes. Cloud sees two writes to game `id=42` — they conflict on every field, LWW picks one, the other device's edits silently lose.

**Fix:** every row carries a `uuid` column (UUID v4) generated at INSERT time, client-side. The cloud uses `uuid` as the identity key. `client_id` (the local rowid) is wire-format-only, used to route field changes through the outbox; it never leaves the device as identity.

```typescript
// Frontend INSERT site
const uuid = crypto.randomUUID();
await db.exec('INSERT INTO games (uuid, name, ...) VALUES (?, ?, ...)', [uuid, name, ...]);
await trackGame(rowid, { uuid, name, ... });
```

For child rows (e.g. `journal_entries.game_id`), the outbox row also carries `parent_uuid` — the parent's cross-device uuid. The cloud uses `parent_uuid` to resolve which cloud row this child belongs to, falling back to `parent_id` only for legacy rows that pre-date the uuid migration.

**Backfill is pure SQL** — if your project ships before the migration, you can backfill UUIDs in a SQLite migration without any Rust/JS code:

```sql
-- Migration: backfill UUIDs for existing rows
UPDATE games SET uuid =
  lower(hex(randomblob(4))) || '-' ||
  lower(hex(randomblob(2))) || '-4' ||
  substr(lower(hex(randomblob(2))), 2) || '-' ||
  substr('89ab', 1 + (abs(random()) % 4), 1) ||
  substr(lower(hex(randomblob(2))), 2) || '-' ||
  lower(hex(randomblob(6)))
WHERE uuid IS NULL;
```

Verify with `SELECT uuid FROM games LIMIT 1` — the format should be `xxxxxxxx-xxxx-4xxx-[89ab]xxx-xxxxxxxxxxxx` (UUID v4 with the version + variant bits in the right positions).

---

## Pattern 3: User-scoped outbox writes — sign-out is NOT free

**Bug we shipped:** sign out from account A, sign in as account B on the same device, and the rows account A had pending in the outbox would drain to **account B's cloud namespace** the moment the next push fired. Real cross-account data leak.

**Fix:** every outbox row carries a `user_id` column. The Rust `sync_push` filters `WHERE user_id = ?` (active user). Rows tagged with a different `user_id` stay queued and only drain when that user signs back in.

Three protocol changes you need:

1. **Sign-in IPC** persists the user_id to `sync_meta` AND runs `UPDATE sync_outbox SET user_id = ? WHERE user_id IS NULL` to claim pre-sign-in writes for the first account that authenticates.
2. **Sign-out IPC** clears the active user_id meta key. Subsequent offline writes land with `user_id = NULL` and get claimed by the next sign-in.
3. **Push filter** scopes the SELECT by active user_id. Returns a clear error if the meta key is empty (recovery: re-sign-in).

```rust
// Sign-in
pub async fn sync_set_user_id(pool: &SqlitePool, user_id: String) -> Result<(), String> {
    set_meta(&pool, "user_id", &user_id).await?;
    sqlx::query("UPDATE sync_outbox SET user_id = ? WHERE user_id IS NULL")
        .bind(&user_id)
        .execute(&pool)
        .await
        .map_err(|e| e.to_string())?;
    Ok(())
}
```

---

## Pattern 4: Defense in depth — Worker-side cross-user identity check

Pattern 3 prevents leaks at the client. But a buggy or compromised client could send pushes tagged with the wrong user. The Worker MUST defend independently.

Before applying any row from a push, batch-SELECT all incoming uuids per table and reject any group whose uuid already belongs to a **different** user in cloud:

```typescript
// Inside push handler, before applying changes
const incomingUuids = changes.map(c => c.uuid).filter(Boolean);
const owners = await env.DB
  .prepare(`SELECT uuid, user_id FROM games WHERE uuid IN (${placeholders})`)
  .bind(...incomingUuids)
  .all<{ uuid: string; user_id: string }>();

const owned = new Map(owners.results.map(r => [r.uuid, r.user_id]));
for (const change of changes) {
  if (change.uuid && owned.has(change.uuid) && owned.get(change.uuid) !== currentUserId) {
    rejected++;
    errors.push(`uuid ${change.uuid} already owned by another user`);
    continue;
  }
  // ...apply change
}
```

Cost: one extra batched read per push, no extra round-trip. Equivalent to row-level security in Postgres (which you can't enforce declaratively in D1).

---

## Pattern 5: Server-side allowed-fields whitelist

Never let push payloads write arbitrary columns. Both the client AND the server should hold an explicit list of allowed `(table, field)` pairs.

```typescript
const ALLOWED_FIELDS: Record<string, ReadonlySet<string>> = {
  games: new Set(['name', 'platform', 'status', 'deleted_at', /* ... */]),
  journal_entries: new Set(['notes', 'intention_1', 'deleted_at', /* ... */]),
  journal_screenshots: new Set(['r2_key', 'sort_order', 'deleted_at']),
};

if (!ALLOWED_FIELDS[change.table]?.has(change.field)) {
  errors.push(`rejected: ${change.table}.${change.field} not in whitelist`);
  continue;
}
```

Mirror this on the pull side too — the client must reject server-sent fields it doesn't recognize (defends against a compromised server pushing into unsupported columns).

---

## Pattern 6: D1 `db.batch()` for chunking — drops subrequest count to near-constant

D1 has a 50-subrequest-per-request limit on the free plan (1000 on paid). A naive push of N rows fires N separate `db.prepare().bind().run()` calls = N subrequests = backfills die at ~50 rows.

**Fix:** wrap all writes in `env.DB.batch([...])`. Cloudflare counts a batched call as ~1-3 subrequests total regardless of statement count.

```typescript
const statements = changes.map(c =>
  env.DB.prepare(`UPDATE ${c.table} SET ${c.field} = ? WHERE uuid = ?`)
    .bind(c.value, c.uuid)
);
const results = await env.DB.batch(statements);
```

In our case: 4000-row backfill dropped from ~15 min (timeouts + retries on rate limits) to <1 min after switching to `db.batch()`. The new bottleneck became the per-user rate limit, not subrequest budget.

---

## Pattern 7: Tokio Mutex to serialize push — kill the debounced/manual race

If you have both auto-push (debounced on outbox writes) AND manual "Sync now" buttons, they race. N parallel push calls each individually hit the per-user rate limit, all 429, burn the retry budget competing with each other.

```rust
// Process-wide push lock. OnceLock<Mutex<()>> initialized once.
static SYNC_PUSH_LOCK: OnceLock<Mutex<()>> = OnceLock::new();

#[tauri::command]
pub async fn sync_push(app: AppHandle) -> Result<SyncPushResult, String> {
    let lock = SYNC_PUSH_LOCK.get_or_init(|| Mutex::new(()));
    let _guard = lock.lock().await;
    // ...rest of push logic; whoever holds the lock drains the outbox snapshot
    // it read at start; next caller picks up rows added during the previous push
}
```

Awaiting the lock is intentional — concurrent callers queue rather than fail. Each holder reads the outbox fresh, so a row written between two pushes still gets delivered in the second push.

---

## Pattern 8: Rate-limit + Retry-After exponential backoff

The Worker should rate-limit per user (e.g. 30-100 pushes/minute) using a sliding window. The client must honor `Retry-After` on 429:

```rust
const MAX_RATE_LIMIT_RETRIES: u32 = 5;
const RATE_LIMIT_FALLBACK_SECS: u64 = 65;  // 60s window + 5s buffer

let mut retries: u32 = 0;
let resp = loop {
    let r = client.post(...).send().await?;
    if r.status().as_u16() == 429 && retries < MAX_RATE_LIMIT_RETRIES {
        let wait_secs = r.headers()
            .get("retry-after")
            .and_then(|v| v.to_str().ok())
            .and_then(|s| s.parse::<u64>().ok())
            .unwrap_or(RATE_LIMIT_FALLBACK_SECS);
        let _ = r.text().await;  // drain body before sleeping
        tokio::time::sleep(Duration::from_secs(wait_secs)).await;
        retries += 1;
        continue;
    }
    break r;
};
```

Per-chunk retries (not per-request) — a long backfill can survive multiple rate windows without losing earlier progress.

---

## Pattern 9: Group-by-row chunking — fields of the same row MUST NOT split across chunks

If you naively split outbox rows into fixed-size chunks, you can split a single logical row's fields across two pushes. The server applies chunk 1 (some fields), then chunk 2 (other fields) — but if your server-side dedupe relies on a specific identity field (e.g. `steam_appid` for game rows), that field might not be in chunk 1, so chunk 1 inserts an orphan row with NULL identity. Now you have a polluted cloud row that's hard to clean up.

**Fix:** group outbox rows by `(table, client_id)` before chunking. Pack greedily — never split a group. Oversize single groups (a row with >chunk-size fields) get their own chunk.

```rust
let mut group_indices: HashMap<(String, i64), Vec<usize>> = HashMap::new();
let mut group_order: Vec<(String, i64)> = Vec::new();
for (idx, change) in all_changes.iter().enumerate() {
    let key = (change.table.clone(), change.client_id);
    if !group_indices.contains_key(&key) {
        group_order.push(key.clone());
    }
    group_indices.entry(key).or_insert_with(Vec::new).push(idx);
}

// Greedy bin-pack
let mut packed_chunks: Vec<Vec<usize>> = Vec::new();
let mut current: Vec<usize> = Vec::new();
for key in &group_order {
    let group = &group_indices[key];
    if !current.is_empty() && current.len() + group.len() > PUSH_CHUNK_SIZE {
        packed_chunks.push(std::mem::take(&mut current));
    }
    current.extend(group);
}
if !current.is_empty() {
    packed_chunks.push(current);
}
```

We hit this in production: a 595-row backfill produced 479 orphan rows in cloud because ~50 game rows had their `steam_appid` field land in chunk N+1 while the rest of the fields landed in chunk N. Cleanup required a bespoke SQL script. Don't do this.

---

## Pattern 10: trackChanges ALWAYS emits identity fields

Related to Pattern 9: even if a write only touches one field, the `trackChanges` writer should emit the row's identity field alongside (e.g. `steam_appid` for games, `entry_type` for journal entries). This lets server-side dedupe always have the identity in scope for a row write, no matter which field-level change triggered the push.

```typescript
async function trackGame(rowid: number, fields: Partial<Game>) {
  const identity = await fetchGameIdentity(rowid);  // steam_appid + uuid
  const enriched = {
    steam_appid: identity.steam_appid,  // always included
    ...fields,
  };
  await emitOutboxRows('games', rowid, enriched, identity.uuid);
}
```

Cheap defense — adds 1 extra outbox row per push at most (or zero if the field was already in the change set). Server-side dedupe gets simpler.

---

## Pattern 11: Tombstones with mirrored retention

Hard deletes don't sync. If Device A deletes a row and Device B is offline, B has no way to know — when B reconnects and pulls, the row is just *gone*, and B's local copy resurrects on the next push.

**Fix:** soft-delete via a `deleted_at` timestamp column. Push the `deleted_at` field through sync like any other field. Cascade children-first (`UPDATE journal_screenshots SET deleted_at = ? WHERE entry_id IN (...)`, then entries, then the game). Then a startup GC purges rows whose `deleted_at` is past the retention window.

```typescript
// gc.ts — runs on app boot
const TOMBSTONE_RETENTION_DAYS = 30;
const cutoff = Date.now() - TOMBSTONE_RETENTION_DAYS * 86400000;
await db.exec('DELETE FROM games WHERE deleted_at IS NOT NULL AND deleted_at < ?', [cutoff]);
// ... same for child tables
```

**Critical: retention window MUST match between client and server.** Mismatch causes resurrection bugs. Example: client retains 30 days, server retains 7 days. Device A deletes a row on day 0. Device B is offline. Day 8: server GCs the tombstone. Day 9: Device B comes online, pulls, sees no `deleted_at` for the row, has its own local copy, pushes it as a "new" row. Row resurrects.

Pin the constant in shared code or as a Worker env var; assert on startup if mismatched.

---

## Pattern 12: First-login backfill is one-shot, guarded by a meta flag

When a user signs in for the first time on a device that already has local data, push ALL existing rows once. Use a `sync_meta.initial_backfill_done` flag to guard against re-backfilling.

```typescript
async function maybeBackfill() {
  const done = await getMeta('initial_backfill_done');
  if (done === 'true') return;

  const games = await db.exec('SELECT * FROM games WHERE deleted_at IS NULL');
  for (const g of games) await trackGame(g.id, g);
  // ... same for entries, screenshots

  await setMeta('initial_backfill_done', 'true');
}
```

**Known limitation:** sign-out and re-sign-in as a different account on the same PC will NOT re-backfill. The flag persists. For v1 this is acceptable; for multi-account UX, namespace the flag by `user_id`: `initial_backfill_done_${user_id}`.

---

## Pattern 13: Last-pulled-at reset on factory reset

If your app has a "factory reset" / "disconnect and wipe" path, it must reset `sync_meta.last_pulled_at` to 0. Otherwise the next sync won't pull anything because the server filters by `since > last_pulled_at` and your local data is gone.

```rust
// Factory reset path
sqlx::query("DELETE FROM games").execute(&pool).await?;
sqlx::query("DELETE FROM journal_entries").execute(&pool).await?;
sqlx::query("DELETE FROM sync_outbox").execute(&pool).await?;
set_meta(&pool, "last_pulled_at", "0").await?;  // ← critical
```

Skipping this turns factory-reset into "factory-reset-and-stay-empty-forever" because the cloud will only send rows whose timestamp is > last_pulled_at, which is set to "yesterday afternoon."

---

## What NOT to do

- **Don't sync binary blobs through the outbox.** Cover images, audio files, etc. belong in R2 (or equivalent object storage). The outbox row carries the R2 key (a short string); the blob uploads on a separate transport. Putting blobs in the outbox makes pushes huge, slow, and exposes you to multipart-encoding fights.
- **Don't rely on cookies for the sync auth token.** Native apps and webviews don't share cookie jars with the system browser. Use a bearer token, store it in your local DB (`sync_meta.auth_token`), and send `Authorization: Bearer ...` on every sync request.
- **Don't trust `client_id` as identity** — it's only valid within one device. The only identity that crosses devices is `uuid`.
- **Don't skip the per-field LWW comparison server-side.** "I'll just take the latest push" forgets that two devices can push concurrently and chunk ordering means the wrong write can win.
- **Don't put the `Mutex` around the HTTP call only.** It has to wrap the outbox read + HTTP + outbox cleanup. Otherwise two callers each read the same outbox snapshot and double-push the same rows.

---

## Reference implementation layout

This pattern was first proven in a Tauri 2 + Cloudflare Worker + D1 desktop app. File layout in a project of that shape:

- Outbox writers (TS): `packages/frontend/src/features/sync/outbox.ts`
- Tombstone helpers (TS): `packages/frontend/src/features/sync/tombstones.ts`
- GC (TS): `packages/frontend/src/features/sync/gc.ts`
- Sync IPC commands (Rust): `apps/desktop/src-tauri/src/commands/sync/` (split: push, pull, status, auth, shared)
- Worker sync handlers (TS): `apps/cloud/src/sync/{push,pull,gc,routes}.ts`
- Shared types (TS): `packages/core/src/sync.ts` — wire-format types used by both client and Worker, validated via Zod
