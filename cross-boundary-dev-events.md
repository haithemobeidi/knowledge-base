---
stack: [tauri, electron, capacitor, rust, typescript]
kind: pattern
last_verified: 2026-05-15
---

# Cross-boundary dev events — observability across Rust ↔ TS

> Silent failures across the IPC boundary kill productivity. `console.log` survives until you close F12 and disappears forever. The pattern below is a structured, in-app ring buffer that captures events from BOTH sides of the boundary, survives panel closure, and turns silent bugs into discoverable ones.

## The Problem

Apps with a frontend talking to a backend over IPC have three observability gaps that compound:

1. **Backend logs you can't see.** Rust's `eprintln!`, Go's `log.Println`, Python's `print` — all go to a terminal you're not watching while clicking around the UI.
2. **`console.log` that vanishes.** Open F12, see a log, close F12 to test something — the next log message lives in a dev-tools panel nobody is looking at.
3. **Swallowed errors.** `.catch(() => {})` on fire-and-forget IPC calls is a common pattern. Errors die there silently for months until someone instruments.

Concrete bugs we shipped behind this:
- A Zod schema mismatch in an outbox writer threw on every single call. Wrapped in `.catch(() => {})`. Hid for **weeks** until manual instrumentation surfaced it.
- A Rust sync push silently returned `Ok(())` after rejecting half the chunks. The HTTP error was in `eprintln!` which scrolled past the terminal we'd stopped watching.
- A React `setInterval` ran `setState(...)` for one piece of state but not another. UI showed stale data; no error anywhere. Found only by adding event taps to both the source and the sink.

## The Pattern: structured ring buffer + Tauri event bridge

Both sides of the IPC boundary write into a shared in-memory event ring buffer that the in-app debug screen renders live. The Rust side emits a Tauri event; the TS side has both a listener (Tauri → ring buffer) and a direct push function (`pushDevEvent`).

```
┌──────────────────────┐      tauri.emit("dev_log", payload)       ┌─────────────────────┐
│ Rust commands        │ ───────────────────────────────────────►  │ devLogListener.ts   │
│   emit_dev_log(...)  │                                            │  pushDevEvent(...)  │
└──────────────────────┘                                            └─────────┬───────────┘
                                                                              │
┌──────────────────────┐                                                      │
│ React feature code   │                                                      ▼
│   pushDevEvent(...)  │ ──────────────────────────────────────────► ┌─────────────────────┐
└──────────────────────┘                                              │ debugStore (ring     │
                                                                      │ buffer, max 500)     │
                                                                      └─────────┬───────────┘
                                                                                │
                                                                                ▼
                                                                      ┌─────────────────────┐
                                                                      │ DebugScreen — live   │
                                                                      │ log view + clear     │
                                                                      └─────────────────────┘
```

The ring buffer lives at module scope (not React state) so events from the Rust side that arrive before any component mounts still get captured. The debug screen subscribes via `useSyncExternalStore`.

---

## TypeScript side: ring buffer + listener

### Event shape (shared between Rust and TS)

```typescript
// features/debug/types.ts
export type DevLogLevel = 'info' | 'warn' | 'error' | 'success';

export interface DevLogEvent {
  timestamp: number;       // ms since epoch
  level: DevLogLevel;
  category: string;        // "sync-outbox", "hotkey", "exe-map", "db" — short tag
  message: string;
  data?: unknown;          // optional structured payload for click-to-expand
}
```

### Ring buffer

```typescript
// features/debug/debugStore.ts
import { useSyncExternalStore } from 'react';

const MAX_EVENTS = 500;

let events: DevLogEvent[] = [];
const subscribers = new Set<() => void>();

export function pushDevEvent(event: DevLogEvent): void {
  events = [event, ...events].slice(0, MAX_EVENTS);
  subscribers.forEach((cb) => cb());
}

function getSnapshot() { return events; }
function subscribe(cb: () => void) {
  subscribers.add(cb);
  return () => subscribers.delete(cb);
}

export function useDevEvents(): DevLogEvent[] {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
```

Three details that matter:
- **Module-level state, not React state.** Events from Rust can arrive before any component mounts — usually during the first 50ms of app load. Module state captures them; React state would lose them.
- **Newest-first array (not a queue).** Makes log views trivial — no `.reverse()` per render.
- **Cap at ~500 events.** Unbounded growth is fine for a brief session but a long-running app accumulates memory. 500 is the right size to cover one bug-hunt without truncating useful context.

### Tauri event listener (Rust → TS bridge)

```typescript
// features/debug/devLogListener.ts
import { listen } from '@tauri-apps/api/event';
import { pushDevEvent } from './debugStore';

export async function startDevLogListener() {
  return listen<{
    level?: string;
    category?: string;
    message?: string;
    data?: unknown;
  }>('dev_log', (event) => {
    const payload = event.payload ?? {};
    pushDevEvent({
      timestamp: Date.now(),
      level: normalizeLevel(payload.level),  // tolerant of malformed Rust payloads
      category: typeof payload.category === 'string' ? payload.category : 'rust',
      message: typeof payload.message === 'string' ? payload.message : '(no message)',
      data: payload.data,
    });
  });
}
```

Mount this once in the App shell — gated on `import.meta.env.DEV` so it disappears entirely in production via Vite tree-shaking.

---

## Rust side: emit_dev_log helper

```rust
// commands/process_watch.rs (or wherever your first feature lands)
use serde_json::{json, Value as JsonValue};
use tauri::{AppHandle, Emitter};

/// Emit a structured event into the in-app Debug screen pipeline.
/// `pub(crate)` so sibling modules can mirror their eprintln chatter
/// into the Debug screen (hotkey handler, sync push, etc).
pub(crate) fn emit_dev_log(
    app: &AppHandle,
    level: &str,
    category: &str,
    message: String,
    data: Option<JsonValue>,
) {
    let _ = app.emit(
        "dev_log",
        json!({
            "level": level,
            "category": category,
            "message": message,
            "data": data,
        }),
    );
}
```

Three details that matter:
- **`pub(crate)` not `pub`.** This is dev infra, not a public API. Sibling modules can use it; outside callers can't.
- **Ignore the `Result`.** `let _ = app.emit(...)`. If the event channel is broken, the dev log being silent is the least of your worries — and we don't want production panics on a logging error.
- **Mirror, don't replace.** Keep your `eprintln!` / `tracing::info!` calls. The terminal log is still useful (cargo dev mode, CI logs, crash reports). `emit_dev_log` adds an in-app view; it doesn't subtract the terminal view.

### Calling pattern

```rust
emit_dev_log(
    &app,
    "success",
    "hotkey",
    format!("Overlay window built for appid={}", appid),
    Some(json!({ "appid": appid })),
);
```

Or with `error` for failures:

```rust
match build_result {
    Ok(_) => emit_dev_log(&app, "success", "hotkey", "Overlay built".into(), None),
    Err(e) => emit_dev_log(&app, "error", "hotkey", format!("Overlay build FAILED: {}", e), None),
}
```

---

## TypeScript side: in-feature instrumentation

Outside the Rust bridge, the TS side can `pushDevEvent` directly from feature code. This is where you instrument silent-fail paths:

```typescript
// features/sync/outbox.ts — instrument the fire-and-forget trackChanges
export async function trackChanges(table: string, rowId: number, fields: FieldChange[]) {
  try {
    await emitOutboxRows(table, rowId, fields);
    pushDevEvent({
      timestamp: Date.now(),
      level: 'success',
      category: 'sync-outbox',
      message: `trackChanges ${table}#${rowId} emitted ${fields.length} field(s)`,
      data: { table, rowId, fields: fields.map((f) => f.field) },
    });
  } catch (err) {
    pushDevEvent({
      timestamp: Date.now(),
      level: 'error',
      category: 'sync-outbox',
      message: `trackChanges ${table}#${rowId} FAILED: ${String(err)}`,
      data: { table, rowId, error: String(err) },
    });
    throw err;  // re-throw — instrumentation should not swallow
  }
}
```

The **re-throw after logging** is important. The original `.catch(() => {})` swallowed errors. Replacing it with instrumentation that ALSO swallows just makes the bug instrument-visible but still production-broken. Log + re-throw turns the dev-event into a "this errored" signal AND keeps the error path live for upstream handling.

---

## What this caught for us

Real bugs found by adding `pushDevEvent` / `emit_dev_log` calls, that had been silently broken for weeks:

1. **Zod camelCase remap trap** — A select helper auto-converted snake_case columns to camelCase. The Zod schema still expected snake_case. Threw `expected number, received undefined` on every call. The `.catch(() => {})` swallowed it. Surfaced the instant we added `pushDevEvent` inside the catch block.
2. **Worker push silently rejecting half the chunks** — Sync push HTTP responses included a 200 OK with a body containing per-row rejection arrays. Rust code only checked status code; rejections weren't surfaced. Added `emit_dev_log` for chunk responses including rejection counts — bug became obvious within one push cycle.
3. **`setInterval` updating only half the state** — A status-poll interval called `setState(...)` for one variable but never `setLastSync(...)`. UI showed stale timestamps. No error anywhere. Found by event-tapping both the interval tick AND the IPC response — the responses showed fresh data, the UI didn't reflect it, narrowed to the missing setter call.

The general pattern: **any boundary where you don't directly see the data flowing should have an event tap.** It's cheap (~5 lines of code per tap), zero production cost (tree-shaken via `import.meta.env.DEV`), and pays for itself the first time a silent bug surfaces.

---

## When to instrument vs not

**Instrument:**
- Any IPC call where errors could be silently caught
- Any background interval / scheduled task whose execution you don't visually observe
- Any sync/network boundary (push, pull, retry paths)
- Any "fire and forget" pattern in your codebase (`.catch(() => {})` is the smell)
- Hot paths that surprise you when they fire too often (e.g. "why did this trigger 12 times?")

**Don't instrument:**
- Pure functions (their output is observable from the call site)
- Render-path code (React DevTools handles this better)
- Anything that fires hundreds of times per second — the ring buffer will fill with noise. If you really need it, sample (`if (Math.random() < 0.05)` or `if (counter % 50 === 0)`).
- Anything that requires you to log sensitive data to reproduce (PII, auth tokens). Find another way.

---

## What NOT to do

- **Don't use `console.log` for cross-boundary observability.** It works until you close DevTools, then evaporates. The whole point of the ring buffer is to survive panel closure.
- **Don't ship the debug screen in production.** Gate every entry point on `import.meta.env.DEV` (Vite), `process.env.NODE_ENV === 'development'` (Webpack), or equivalent. Vite tree-shakes the entire feature directory if the imports are all dev-gated.
- **Don't write the ring buffer to disk on every event.** It's a debugging tool, not an audit log. If you need persistent logs, write a separate file appender on a debounce — don't make every event hit `fs.writeFileSync`.
- **Don't swallow errors AND instrument them.** Re-throw after logging. The instrumentation is supposed to make the error visible, not "tame" it.
- **Don't let categories proliferate without a list.** "sync-outbox", "hotkey", "exe-map", "db" — keep the set small. If you have 30 categories, the filter UI is useless. Cap at ~10–15 and group narrower events under broader category tags.

---

## Reference implementation layout

Built in a Tauri 2 + React + TS desktop app. File layout in a project of that shape:

- TS ring buffer + hook: `packages/frontend/src/features/debug/debugStore.ts`
- Tauri → TS bridge listener: `packages/frontend/src/features/debug/devLogListener.ts`
- Event types (shared with Rust JSON): `packages/frontend/src/features/debug/types.ts`
- In-app log viewer: `packages/frontend/src/features/debug/DebugScreen.tsx`
- Rust `emit_dev_log` helper: `apps/desktop/src-tauri/src/commands/process_watch.rs` (lives wherever the first feature needs it; siblings re-use via `pub(crate)`)

Mount the Tauri listener once in your app shell, gated on dev mode:

```typescript
// App.tsx
useEffect(() => {
  if (!import.meta.env.DEV) return;
  let unlisten: (() => void) | undefined;
  startDevLogListener().then((u) => { unlisten = u; });
  return () => unlisten?.();
}, []);
```

Total cost: ~200 lines of code across 4 files. Zero production cost (tree-shaken). Pays for itself the first time a silent bug surfaces — which, in practice, has been within the first week of having it.
