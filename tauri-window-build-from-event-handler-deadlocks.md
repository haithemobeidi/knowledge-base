---
stack: [tauri, rust, windows, desktop]
kind: gotcha
last_verified: 2026-09-30
---

# Tauri 2 on Windows: building a window from an event handler deadlocks the main thread

**One-liner:** `WebviewWindowBuilder::build()` called from a global-shortcut callback, or any synchronous command or event handler, can hang the whole app on Windows. Tauri documents it: build windows from an **async command** or a **spawned thread**.

*Playmoir D-87, 2026-09-30, desktop 1.8.0.*

## The symptom

A global hotkey that opened an overlay window worked for weeks, then froze the app solid on one path: the hotkey pressed while a notification window was up. The app log stopped at "handler entered"; Windows' Application log recorded **AppHangTransient** (a main-thread hang, not a crash). Step logs put the hang inside the window build itself. The same build ran fine from the notification's own buttons, which go through async commands.

## The cause, in Tauri's own words

Tauri 2's `webview_window.rs` (line 115 in 2.12.0), on the builder:

> "On Windows, this function deadlocks when used in a synchronous command or event handlers ... use async commands and separate threads when creating windows"

Whether it bites depends on what else the main thread is doing in that tick (here: destroying another webview first), which is why it passed tests and then hung in one game.

## The fix

Hand the build to its own thread from the handler and return at once:

```rust
pub fn spawn_hotkey_overlay<F>(app: &AppHandle, build: F)
where F: FnOnce(&AppHandle) -> Result<(), String> + Send + 'static {
    let app = app.clone();
    std::thread::spawn(move || { let _ = build(&app); });
}
```

Window creation from commands should be `async fn` commands. Audit every place a window is built: shortcuts, tray menus, `on_window_event`, setup hooks.

## Related

- `tauri-multiwindow-dev-hmr-stranding.md`: another way a secondary window wedges.
