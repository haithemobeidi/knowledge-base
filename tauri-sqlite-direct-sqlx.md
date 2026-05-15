---
stack: [tauri, rust, sqlite, sqlx]
kind: howto
last_verified: 2026-05-14
---

# Tauri + SQLite with direct sqlx access (alongside tauri-plugin-sql)

> Pattern for projects where the JS side uses `tauri-plugin-sql` for read/write but Rust commands also need direct DB access. Plus the migration footgun that cost us a whole session.

## When you need this

`tauri-plugin-sql` is great for JS-side DB access: SELECT/INSERT/UPDATE from your React code, no IPC wrapper needed per query. But once Rust commands need DB access — say, an OAuth flow that writes `auth_token` to `sync_meta`, or a sync push that reads from `sync_outbox` — you hit a wall:

**`tauri_plugin_sql`'s `DbPool` is `pub(crate)`.** You can't `.state::<DbInstances>()` and reach in. Their team intentionally hid it so consumers don't lock themselves into the plugin's internal connection pool.

The workaround is straightforward but non-obvious: **open your own `sqlx` pool against the same SQLite file.** Both pools coexist safely because SQLite WAL mode allows multiple concurrent readers + serialized writers at the filesystem level.

## The pattern

```rust
// commands/your_feature.rs
use sqlx::SqlitePool;
use tauri::{AppHandle, Manager};

async fn open_db(app: &AppHandle) -> Result<SqlitePool, String> {
    let app_dir = app
        .path()
        .app_config_dir()
        .map_err(|e| format!("No app config dir: {}", e))?;
    let db_path = app_dir.join("myapp.db");  // same file tauri-plugin-sql uses
    let url = format!("sqlite:{}", db_path.display());
    SqlitePool::connect(&url)
        .await
        .map_err(|e| format!("Failed to open DB: {}", e))
}

#[tauri::command]
pub async fn my_command(app: AppHandle) -> Result<String, String> {
    let pool = open_db(&app).await?;
    let row = sqlx::query("SELECT value FROM sync_meta WHERE key = ?")
        .bind("auth_token")
        .fetch_optional(&pool)
        .await
        .map_err(|e| e.to_string())?;
    // ...
}
```

### Why this is safe (and why people get nervous)

The first time you do this, you ask: "isn't opening a second pool to the same DB file a recipe for corruption?" No. SQLite handles this fine:

- **WAL mode allows concurrent readers.** N pool connections all reading at once = no contention.
- **Writers serialize at the file level.** Both pools' write attempts are queued by SQLite itself; no extra coordination needed in your code.
- **Both pools see each other's commits.** WAL means a commit on one pool is visible to readers on the other pool within milliseconds (after the next read transaction starts).

What you DO have to be careful about:
- **Don't try to share an in-flight transaction across pools.** Each pool's transactions are isolated. A `BEGIN` on pool A is not visible to pool B until the COMMIT lands.
- **Don't init each pool with conflicting PRAGMAs.** The plugin sets WAL/journal mode at startup; let it. Your sqlx pool inherits the file's mode.

## The migration footgun — your migration MIGHT NEVER RUN

This is the bug that ate a full session and shipped to production briefly. **Every new migration file MUST be appended to your `migrations` vec in `lib.rs`. There is no auto-discovery.**

Most tutorials show migrations like this:

```rust
.plugin(
    tauri_plugin_sql::Builder::default()
        .add_migrations(
            "sqlite:myapp.db",
            vec![
                Migration {
                    version: 1,
                    description: "initial schema",
                    sql: include_str!("../migrations/0001_initial.sql"),
                    kind: MigrationKind::Up,
                },
                // ...
            ],
        )
        .build(),
)
```

What's not stated is that **the `vec!` is the entire source of truth for which migrations run.** If you add `migrations/0020_add_user_id.sql` to your filesystem but forget to append a `Migration { version: 20, ... }` entry to that `vec!`, the SQL file might as well not exist. No error. No warning at build time. No warning at runtime. Migration silently no-ops.

We shipped exactly this bug: an entire feature (BUG-22 cross-account outbox scoping) was "complete" with code that referenced the new `user_id` column, but the column was never added because the migration was never registered. The code path that read the column got `0 rows` results and silently ate the feature.

**Mitigation patterns:**

1. **Treat the `migrations` vec as the schema's source of truth, NOT the filesystem.** When you add a SQL file, also add the vec entry in the same commit. A pre-commit hook can enforce this (grep for `migrations/000*_` files vs `version: N` in lib.rs and complain on mismatch).

2. **Drift assertion on startup.** Run a quick check at app boot that compares your schema's expected columns against the actual columns SQLite reports via `PRAGMA table_info`. If a column you expect is missing, panic loudly with a message that names the migration that should have added it. This catches both "forgot to register" and "migration ran on an older version of the file."

3. **`_sqlx_migrations` table introspection.** `tauri-plugin-sql` keeps a record of applied migrations. After a migration runs, verify with:
   ```bash
   sqlite3 ~/AppData/Roaming/com.your-app/myapp.db \
     "SELECT version, description, installed_on FROM _sqlx_migrations ORDER BY version DESC LIMIT 5"
   ```
   If your latest version isn't there, the migration didn't run.

4. **Numbering convention enforced by linter.** We use a strict `NNNN_description.sql` pattern (`0001_`, `0002_`, ...) and a script that walks the migrations dir + checks each file has a matching `version: N` entry in `lib.rs`. If you regularly touch migrations, this is worth ~30 minutes to write.

## WAL mode semantics in 30 seconds

- **Multiple readers, single writer**, serialized at file level by SQLite.
- **Writers don't block readers** (and vice versa, mostly). A long-running SELECT won't make an INSERT wait.
- **`wal-checkpoint`** rolls the WAL into the main DB file. Happens automatically; you usually don't manage it.
- **`.db-wal` and `.db-shm` sidecar files** are normal — don't delete them outside the app. They're how WAL coordinates between processes.
- **Backups must capture all three files** (`.db`, `.db-wal`, `.db-shm`) or use `VACUUM INTO` / the SQLite backup API to write a checkpoint-included single file.

## Pure-SQL UUIDv4 backfill (no Rust generation needed)

If you need to backfill UUIDs for existing rows during a migration (see local-first-sync-with-d1.md Pattern 2), you don't need Rust code. SQLite's `randomblob()` + `hex()` produces valid UUID v4 from pure SQL:

```sql
-- migrations/NNNN_add_uuid_backfill.sql
ALTER TABLE games ADD COLUMN uuid TEXT;

UPDATE games SET uuid =
  lower(hex(randomblob(4))) || '-' ||
  lower(hex(randomblob(2))) || '-4' ||
  substr(lower(hex(randomblob(2))), 2) || '-' ||
  substr('89ab', 1 + (abs(random()) % 4), 1) ||
  substr(lower(hex(randomblob(2))), 2) || '-' ||
  lower(hex(randomblob(6)))
WHERE uuid IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_games_uuid ON games(uuid);
```

Decoded: 4 + 2 + 2 + 2 + 6 = 16 bytes (32 hex chars + 4 dashes = 36 char UUID). The literal `'-4'` after the second hyphen enforces UUID version 4. The `substr('89ab', ...)` picks one of `8`, `9`, `a`, `b` for the variant bit position (UUID v4 requires `[89ab]` for the first hex digit of the 4th group).

Verify the result with `SELECT uuid FROM games LIMIT 5` and check the format matches `xxxxxxxx-xxxx-4xxx-[89ab]xxx-xxxxxxxxxxxx`.

## Schema drift detection at startup (recommended)

We added a drift check that runs on app boot and panics if expected columns are missing. Cheap insurance against the migration-not-registered footgun:

```rust
async fn assert_schema(pool: &SqlitePool) {
    let expected: &[(&str, &[&str])] = &[
        ("games", &["id", "uuid", "name", "status", "deleted_at"]),
        ("sync_outbox", &["id", "table_name", "row_id", "uuid", "user_id"]),
        // ... pin every table you care about
    ];

    for (table, cols) in expected {
        let actual: Vec<String> = sqlx::query(&format!("PRAGMA table_info({})", table))
            .fetch_all(pool)
            .await
            .expect("schema check failed")
            .into_iter()
            .map(|r| r.get::<String, _>("name"))
            .collect();

        for col in *cols {
            assert!(
                actual.contains(&col.to_string()),
                "schema drift: expected column {}.{} missing. \
                 Was the migration registered in lib.rs?",
                table, col
            );
        }
    }
}
```

Call from your setup hook. ~2ms total at boot, catches the entire class of "I forgot to register the migration" bugs the instant you launch the app.

## Common gotchas

1. **`sqlx::query` vs `sqlx::query_as` for typed rows.** If you want typed structs, derive `sqlx::FromRow` and use `query_as::<_, MyStruct>(...)`. For ad-hoc reads, plain `query` returns `SqliteRow` and you call `.get::<T, _>("col")` per field.

2. **Always use `Option<String>` for nullable columns.** A `SELECT value FROM sync_meta WHERE key = ?` returning a row with `value = NULL` panics if you `.get::<String, _>("value")`. Pin the type to `Option<String>`.

3. **`sqlx::query("...").bind(x).execute(&pool)` doesn't return `rows_affected` by default** — it returns a `SqliteQueryResult` which has `.rows_affected()` as a method. Check it for UPDATE/DELETE if you care about whether the row matched.

4. **Don't pass `&str` to `.bind()` for variable-length params and expect them to outlive an async boundary** unless you `.to_string()` first. Rust's borrow checker usually catches this but the error message is opaque ("future is not Send"). When in doubt, `.bind(s.to_string())`.

5. **Path handling on Windows.** `format!("sqlite:{}", db_path.display())` works on all OSes including Windows, but be careful of backslashes if you build the URL with `format!` and a quoted path. The `display()` impl handles this; manual string concat doesn't.

## What NOT to do

- **Don't try to bypass `pub(crate)` on the plugin's pool with `unsafe` or feature flags.** It will break on the next plugin minor version. Just open your own pool.
- **Don't run schema migrations from BOTH `tauri-plugin-sql` AND your sqlx pool.** Pick one (the plugin) and let it own migrations. Your sqlx pool just reads the migrated schema.
- **Don't open a pool per request.** `open_db()` should ideally return a clone of a pool stored in Tauri state (`app.state::<SqlitePool>()`), not a fresh pool every call. For a v1 it's fine to open per-command (sqlx is fast); for production, hoist the pool to state at setup time.

## Reference implementation layout

- Migration files: `apps/desktop/src-tauri/migrations/NNNN_description.sql`
- Migration registration: `apps/desktop/src-tauri/src/lib.rs` (in `.add_migrations(...)` call)
- Shared db open helper: `apps/desktop/src-tauri/src/commands/sync/shared.rs` (or wherever your first feature needed it)
- Schema drift assertion: called from Tauri `.setup(|app| ...)` hook
