---
stack: [tauri, rust]
kind: gotcha
last_verified: 2026-04-13
---

# Tauri IPC Serde Conventions (Rust ↔ TypeScript)

> Save yourself an hour of "why is this field undefined?" debugging.

## The Gotcha

Rust structs serialize with `snake_case` field names by default. TypeScript code expects `camelCase`. Tauri's IPC just pipes the JSON through — it doesn't auto-convert.

Result: `status.loggedIn` is `undefined` on the JS side because the actual field is `logged_in`.

## The Fix

Always add `#[serde(rename_all = "camelCase")]` to any Rust struct that:
- Is returned from a `#[tauri::command]`
- Is deserialized from JS input
- Has any field with more than one word

```rust
use serde::Serialize;

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]  // ← ALWAYS add this
pub struct SyncStatusResult {
    logged_in: bool,        // becomes "loggedIn" in JS
    device_id: String,      // becomes "deviceId" in JS
    last_pulled_at: i64,    // becomes "lastPulledAt" in JS
    outbox_count: i64,      // becomes "outboxCount" in JS
}
```

## How to Spot the Bug

Symptom: TypeScript code like this silently fails:
```typescript
const status = await invoke<SyncStatus>('sync_status');
if (status.loggedIn) { ... }  // always false, even after login
```

Debug: log the raw response:
```typescript
console.log(JSON.stringify(await invoke('sync_status')));
// Output: {"logged_in":true,...}  ← snake_case gives it away
```

## Single-Word Fields Don't Show the Bug

This is why the bug hides — structs with only single-word fields serialize the same in both conventions:

```rust
pub struct SyncPushResult {
    pushed: i64,
    accepted: i64,
    rejected: i64,
    errors: Vec<String>,
}
// JS sees: { pushed, accepted, rejected, errors } — works without rename_all
```

So you can have a codebase where half the structs work and half don't, depending on whether any field happens to have a word break.

## Rule of Thumb

**Add `#[serde(rename_all = "camelCase")]` to every struct that crosses the Tauri IPC boundary, full stop.** Even if all fields are single-word today — your future self will add a `foo_bar` field and forget.

## Also Applies To

- `#[tauri::command]` parameter structs (input deserialization)
- Events emitted with `app.emit()` and received in JS
- Any `Serialize` + `Deserialize` struct sent through `invoke`

## Reference

Serde docs: <https://serde.rs/container-attrs.html#rename_all>
