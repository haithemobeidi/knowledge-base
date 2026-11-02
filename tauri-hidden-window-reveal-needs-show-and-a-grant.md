---
stack: [tauri, rust, windows, desktop]
kind: gotcha
last_verified: 2026-11-01
---

# A Tauri window hidden to the tray ignores `setFocus()` and `unminimize()`, and the webview may not be allowed to call `show()`

**One-liner:** Once a Tauri 2 app can hide its window (close-to-tray, launch-at-login straight into the tray), every path that "brings the app forward" must call `show()`, because on Windows `setFocus()` and `unminimize()` do nothing for a hidden window. And the obvious one-line fix, adding `show()` to the frontend call, can fail too: `core:window:default` does not grant `allow-show`, so the webview's `show()` is refused. Route the reveal through one Rust command that does all three steps, and never swallow its error.

## The shape

Playmoir shows a "log this session" prompt when a game exits. The prompt's reveal called `getCurrentWindow().unminimize()` and `.setFocus()` from the frontend, wrapped in `.catch(() => {})`. That worked while the window could only be minimized. Then the app gained close-to-tray (the default) and launch-at-login into the tray. From then on the prompt opened inside a window nobody could see, so the user never saw it. A tester reported "I didn't get the prompt to log my session". No error appeared anywhere.

The tray icon's own reveal worked all along, because it was written in Rust as `unminimize()` + `show()` + `set_focus()`. Two reveal paths had drifted apart: the one written after hiding existed knew about hiding, and the older one didn't.

## Why, gate one: Windows `set_focus` needs a visible, unminimized window

Read in tao 0.34.8, the windowing crate under Tauri 2:

- `platform_impl/windows/window.rs`: `set_focus` acts only `if is_visible && !is_minimized && !is_foreground`. A hidden window fails the first test, so the call returns quietly.
- `window_state.rs`: un-minimizing calls `ShowWindow(SW_RESTORE)` only when the MINIMIZED flag changes. A window that was hidden without being minimized has no flag to change, so nothing is shown.

Minimized and hidden are separate states on Windows. A window can be hidden without ever having been minimized, and only `show()` undoes hiding.

## Why, gate two: the webview isn't granted `show`

The ledger's prescribed fix was "add `show()` next to `unminimize()` in the frontend". Reading the app's capability file before writing that line showed it would fail. `capabilities/default.json` listed `core:window:default`, and that set holds only the read-only permissions (`allow-is-visible`, `allow-title`, `allow-get-all-windows` and the other getters, per `gen/schemas/acl-manifests.json`). Nothing granted `core:window:allow-show`, so the JS `show()` would have been refused at the IPC layer. The existing `.catch(() => {})` would have hidden that refusal exactly as it had hidden the first bug.

App-defined Rust commands are allowed by default (as long as `build.rs` is plain `tauri_build::build()` with no app-manifest restriction), so a command is the route that needs no new grant.

## The fix

```rust
// tray.rs: the ONE reveal, used by the tray click, the tray menu,
// the single-instance handler and now the frontend.
pub fn show_main_window(app: &tauri::AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.unminimize();
        let _ = w.show();
        let _ = w.set_focus();
    }
}

#[tauri::command]
pub fn reveal_main_window(app: tauri::AppHandle) {
    show_main_window(&app);
}
```

```ts
invoke('reveal_main_window').catch((e) => {
  console.warn('[quit-ritual] could not bring the window forward', e);
});
```

Register the command in `generate_handler!`. Granting `core:window:allow-show` to the main window would also work. The command is better because every reveal then shares one implementation, so the next one can't forget a step.

## The rule

- When an app first gains a hidden state, grep for every programmatic reveal (`setFocus`, `unminimize`, `show`, single-instance handlers, notification clicks) and send them all through one function. Auditing the tray's reveal alone misses the rest.
- Before writing a frontend window call, check the capability file grants it. `*:default` permission sets are often read-only.
- A `.catch(() => {})` on a window call turns both failures above into silence. Log it. See [[silent-refusals-make-clean-logs-meaningless]].

## Evidence

User-tested on the dev build, Windows 11 x64, 2026-11-01: from the tray, the window comes back with the prompt open; after a login launch (the app started with `--autostart`, confirmed from the process's command line); and with the window open or minimized. The old code failing was predicted from the tao source and the tester's report, but not reproduced on the shipped build.
