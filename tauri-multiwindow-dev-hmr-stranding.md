---
stack: [tauri, vite, multiwindow]
kind: gotcha
last_verified: 2026-07-26
---

# Multi-window Tauri + Vite dev: an entry-file edit can strand an always-on-top window

**One-liner:** in dev, every open Tauri window is a connected Vite client. An edit to a module that can't Fast Refresh (the entry file always qualifies — it has no component exports) triggers a **full page reload in every connected webview at once**. A reload forced into a secondary window mid-life can wedge that webview's IPC — and if every way to dismiss that window lives in its own JS, you now have a frameless, transparent, always-on-top window stranded over the desktop that nothing in the app can remove.

## Symptom

While an agent/dev is saving files, a secondary window (in-game overlay, recap splash, tray popover) suddenly:

- re-renders blank or with empty data (its post-reload fetches failed),
- ignores every dismiss affordance — button, click-away, auto-dismiss timer, hotkey handled in JS,
- may show a **ghost of its pre-reload frame** behind the live render (transparent windows don't clear the old compositor frame),
- survives closing the main window (close-to-tray keeps the process alive; the stranded window belongs to that process).

Task Manager appears to be the only way out. The terminal shows the tell:

```
[vite] (client) hmr invalidate /src/main.tsx Could not Fast Refresh ("true" export is incompatible)
```

— repeated once per connected webview. That message is vite-plugin-react's (badly worded) way of saying the module has no refreshable component exports; the invalidation reaches the entry, so Vite falls back to `full-reload`, pushed to **all** clients.

## Cause chain

1. Entry files (`main.tsx` with `createRoot`, window-mode branching) can never Fast Refresh → any edit to them = full reload everywhere. Component-file edits are safe (they self-accept).
2. The reload lands in a webview that was mid-lifecycle; its IPC bridge can come back wedged (data queries fail, `invoke` rejects).
3. Every dismiss path funnels through webview-side IPC — typically one shape: `getCurrentWindow().destroy().catch(() => {})`. With IPC dead, `destroy()` rejects and the `.catch` **swallows it silently**. All escape routes were the same broken route.

## Fix (two layers)

**Design layer — the dead-man must live in Rust, never in the window's own JS.** Register a global shortcut whose handler destroys the overlay-family windows directly:

```rust
// In the global-shortcut handler — pure Rust, works when the webview is brain-dead:
pub fn destroy_overlay_windows(app: &AppHandle) -> bool {
    let mut destroyed = false;
    for label in ["overlay", "recap"] {
        if let Some(win) = app.get_webview_window(label) {
            let _ = win.destroy();   // never consults the webview
            destroyed = true;
        }
    }
    destroyed
}
```

Reuse an existing muscle-memory hotkey if you have one (e.g. the same combo that opens the overlay: "clear any stuck overlay first, else open"). The property that matters: `WebviewWindow::destroy()` is a window-manager operation — it succeeds regardless of the webview's health.

**Workflow layer — close secondary windows before saving files in dev**, especially before edits to the entry or any non-Fast-Refreshable module. If an AI agent is doing the editing, make this an explicit session rule; the agent's save bursts are exactly the trigger.

## Scoping — is this a production bug?

The *trigger* is dev-only: shipped builds have no Vite and no live-reload. But the *design flaw* it exposes — all dismiss paths behind a single fragile IPC call with a swallowed error — is production-real; anything else that kills the webview's JS (crash loops, OOM, a wedged render) strands the window identically. Ship the Rust dead-man regardless. (A crashed-webview fallback UI does not cover this: the webview here is alive enough to render, just unable to execute its dismiss.)

## What NOT to do

- Don't add retry loops around `destroy()` in JS — if IPC is dead, retries are dead too.
- Don't make the escape "close the main window" — close-to-tray apps keep the process (and the stranded window) alive.
- Don't auto-destroy overlay windows on every reload/game-exit as the fix — a healthy overlay may be holding unsaved user input (a half-typed note); destroying it costs data. The dead-man is user-invoked for exactly this reason.
