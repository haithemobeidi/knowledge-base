---
stack: [windows, tauri, desktop-overlay]
kind: gotcha
last_verified: 2026-07-27
---

# Always-on-top overlays vs exclusive-fullscreen games: out-painted but still eating clicks

**One-liner:** an always-on-top window cannot out-paint a game running in TRUE exclusive fullscreen (the game owns the display), but the window **keeps winning hit-tests from the z-order** — so you get an invisible click-eater: a click "on the game" lands on your hidden window, steals focus, and the exclusive-fullscreen game minimizes on focus loss. The OS-sanctioned answer is to bow out, using the same signal Windows uses to suppress its own toasts: `SHQueryUserNotificationState`.

## Symptom

- Your app pops a notification/recap/overlay window (borderless + always-on-top + maximized) around the time a game launches.
- The game paints over it — user never sees your window.
- Later, a click "in the game" inexplicably **minimizes the game**, revealing your window sitting there.
- If the window has an auto-dismiss countdown that pauses on hover: it may never self-clear, because the invisible window still receives mouse events, and the game's own cursor sitting mid-screen counts as hovering (observed as "stuck forever"; the hover-pause mechanism is the consistent explanation).
- Bonus at-open hazard: building the window with focus (`.focused(true)` in Tauri) steals focus at creation — if the game is *already* exclusive-fullscreen at that moment, it minimizes with no click at all.

## Cause

Painting and hit-testing are **separate systems**. Exclusive fullscreen hands the display to the game's swap chain — DWM stops compositing other windows, so "always on top" wins nothing. But the window is still in the z-order for input routing: `WM_MOUSE*` goes to whatever hit-testing finds, which is your invisible topmost window. Clicking it gives it foreground focus; exclusive-fullscreen D3D apps minimize when they lose focus. That's the whole failure: invisible for output, first-in-line for input.

Timing trap: if your window fires on process start (game_started-style watcher), launcher-first games pass any **fire-time-only** check — the launcher isn't fullscreen — and the game claims the display *after* your window is already up. Detection must run for the window's whole lifetime, not just at open.

## What does NOT work (measured or structurally dead)

- **More topmost/always-on-top flags.** Painting isn't the layer you lost. Nothing you set on your window makes DWM composite over an exclusive swap chain.
- **Click-through (`set_ignore_cursor_events`) as the whole fix.** It removes the click-eater but creates a chicken-and-egg: a click-through window can't be clicked when it IS legitimately visible (over a borderless game). Re-enabling on hover requires native cursor polling, and for a maximized window "inside bounds" is always true — you'd need the content-card rect from the webview, and re-enabling in that region reintroduces the click-steal exactly where users click.
- **Drawing over exclusive fullscreen at all.** The only way (what Steam/Discord/RTSS overlays do) is injecting into the game's render pipeline — anticheat-hostile, out of the question for a normal desktop app.

## Fix: bow out like the OS does

`SHQueryUserNotificationState` is the Windows shell's own "should notifications stay away" probe:

- `QUNS_RUNNING_D3D_FULL_SCREEN` → a D3D app owns the display exclusively. **Bow out.**
- `QUNS_BUSY` → fullscreen-ish but composited (borderless fullscreen, F11 apps, presentations). **DWM composites you fine — keep the overlay.** Do not treat BUSY as exclusive or you'll suppress yourself for most modern games.

Check it at **two points**:

1. **Fire time** — skip creating the window entirely (also prevents the `.focused(true)` steal from minimizing an already-fullscreen game).
2. **A lifetime watcher** — poll every ~1.5s while the window lives; the moment the game goes exclusive, quietly destroy your window (it's invisible at that point anyway, so there is nothing to lose and a click-eater to remove).

Rust (windows crate, feature `Win32_UI_Shell`):

```rust
fn exclusive_fullscreen_active() -> bool {
    use windows::Win32::UI::Shell::{SHQueryUserNotificationState, QUNS_RUNNING_D3D_FULL_SCREEN};
    match unsafe { SHQueryUserNotificationState() } {
        Ok(state) => state == QUNS_RUNNING_D3D_FULL_SCREEN,
        Err(_) => false, // probe failure → assume composited; worst case is pre-fix behavior
    }
}

// after building the window:
std::thread::spawn(move || loop {
    std::thread::sleep(std::time::Duration::from_millis(1500));
    if window.is_visible().is_err() { break; }   // destroyed by any dismiss path → done
    if exclusive_fullscreen_active() {
        let _ = window.destroy();
        break;
    }
});
```

Hold the window **handle** in the watcher, not the label — any dismiss path (button, click-away, timer, hotkey dead-man, a re-fire's replace-destroy) invalidates the handle and the loop self-terminates. A label-based loop races with rebuilds under the same label.

**UX complement:** disclose it. One line in settings ("games in exclusive fullscreen hide overlays entirely, so this steps aside for them; borderless fullscreen shows it") converts a mystery no-show into expected behavior. This matches user expectations already set by Windows toasts and Steam popups, which also don't appear over exclusive fullscreen.

## Caveats

- **Fullscreen Optimizations (Win10/11)** convert many technically-"fullscreen" games into a composited flip-model mode; those may not report `QUNS_RUNNING_D3D_FULL_SCREEN`. Failure mode is benign: your overlay stays, which is pre-fix behavior — and for FSO games it usually actually paints. The population that DOES report exclusive is old ports and FSO-opted-out titles — exactly the ones that break overlays.
- **Verification honesty:** the failure mechanism here (invisible window → click → focus steal → game minimized) was observed live. The fire-time probe's efficacy was verified only indirectly in the origin project (on retest the overlay didn't appear and nothing stranded; a non-qualifying trigger wasn't fully ruled out). The API itself is the documented notification-suppression signal.

## Related

- [tauri-multiwindow-dev-hmr-stranding.md](./tauri-multiwindow-dev-hmr-stranding.md) — the sibling failure class for the same window shape (dev reloads wedging an always-on-top webview whose dismiss paths are all JS-side).
- [instrument-before-patching.md](./instrument-before-patching.md) — the click-ring/hit-test tripwire that turns "clicks vanish" reports into named DOM/window facts.
