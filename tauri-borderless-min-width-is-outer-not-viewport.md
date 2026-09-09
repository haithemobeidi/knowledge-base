---
stack: [tauri, tao, windows, webview2, css, desktop]
kind: gotcha
last_verified: 2026-09-09
---

# A borderless Tauri window's `minWidth` is the OUTER size — the webview viewport is 16px narrower

**One-liner:** With `decorations: false` (and the default window shadow on), Tauri on Windows applies `minWidth`/`minHeight` to the window's outer rectangle but carves an invisible 8px resize inset off every side of the client area — so at the minimum the webview's `innerWidth` is `minWidth − 16`, and its height is `minHeight − 9` on Windows 11 (`− 8` on Windows 10). Any CSS threshold you derive from the config number ("five columns fit at the minimum") is off by exactly those pixels and fails precisely at the resize stop, where a user is most likely to be looking.

## Symptom

A layout rule that "just fits" at the configured minimum falls off a cliff at the stop: a column drops, a breakpoint flips, a flex row wraps. Everywhere above the minimum it behaves. You check the arithmetic against `minWidth`, it is correct, and you conclude the layout code is wrong. It is not — the viewport is smaller than the number you did the arithmetic with.

## Mechanism (read from tao 0.34.8, `src/platform_impl/windows/`)

Two handlers disagree about what "the size" means:

1. **`WM_GETMINMAXINFO`** converts the configured minimum with `util::adjust_size(hwnd, min, is_decorated)`. For an *undecorated* window `adjust_window_rect` strips `WS_CAPTION` and `WS_SIZEBOX` before calling `AdjustWindowRectEx`, so no frame is added: `ptMinTrackSize` = your `minWidth` × scale factor, applied to the **outer** window.
2. **`WM_NCCALCSIZE`** for an undecorated, non-maximized, non-fullscreen window with the `MARKER_UNDECORATED_SHADOW` flag (Tauri's `shadow: true`, the Windows default) shrinks the client rect by `calculate_window_insets(hwnd)`:
   - left / right / bottom = `SM_CXSIZEFRAME + SM_CXPADDEDBORDER` for the window's DPI — **4 + 4 = 8px at 96 DPI**, scaling with DPI so it stays ~8 *logical* px;
   - top = `round(dpi / 96)` on Windows 11 (build ≥ 22000), 0 on Windows 10 (a non-zero top inset would make Windows draw a native title bar).

The client rect is the WebView2 bounds, so `window.innerWidth === minWidth − 16` at the stop. The same offset applies to the *default* `width`/`height`: a configured 1440 opens a 1424px viewport.

## Fix

- **Derive thresholds from the viewport, not the config.** Write the arithmetic against `minWidth − 16` (and `minHeight − 9` / `− 8`), and say so in a comment next to both numbers, because whoever changes one will not know about the other.
- **Or set the config from the viewport you want:** `minWidth = desiredViewport + 16`.
- **Don't let a layout rule hinge on hitting a width exactly.** A rule of the form "N columns until fewer than N × floor fit" is a cliff waiting for a 4px error; prefer "N columns at every width the window allows, and let the window minimum enforce the floor", so the count cannot change at the stop no matter what the exact viewport is.
- **Verify at the stop with `window.innerWidth`,** not by reading the config back.

## Conditions

- Windows only (tao's `platform_impl/windows`); macOS and Linux compute differently.
- `decorations: false`. A decorated window's `AdjustWindowRectEx` accounts for the real frame and the client size comes out as configured.
- Shadow on (`shadow: true`, the default). With `shadow: false` the `MARKER_UNDECORATED_SHADOW` branch is skipped and there are no insets — but you also lose the drop shadow and the OS-drawn resize affordance, which is why nobody turns it off.
- Not maximized (a different branch clamps to the monitor's work area) and not fullscreen.

## How to confirm in 30 seconds

PowerShell, no build needed — these are the two metrics tao sums:

```powershell
Add-Type -Namespace W -Name M -MemberDefinition '[DllImport("user32.dll")] public static extern int GetSystemMetrics(int i);'
[W.M]::GetSystemMetrics(32) + [W.M]::GetSystemMetrics(92)   # SM_CXSIZEFRAME + SM_CXPADDEDBORDER → 8 on stock Windows
```

Or in the app at the resize stop: compare `window.innerWidth` with the configured `minWidth`.

## Related

- [webview2-react-render-traps.md](./webview2-react-render-traps.md) — the other WebView2/Tauri surprises that don't exist in Chrome dev.
- [always-on-top-overlay-vs-exclusive-fullscreen.md](./always-on-top-overlay-vs-exclusive-fullscreen.md) — the other place where Windows windowing rules, not your code, decide what the user sees.
