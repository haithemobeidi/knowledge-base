---
stack: [spa, react, webview]
kind: gotcha
last_verified: 2026-07-27
---

# SPA overlays dismissed via pushState/popstate: the history stack WILL drift from UI state

**One-liner:** if overlays/modals are wired to browser history (push an entry on open, `history.back()` on Back so mouse-back works), the stack and the UI drift apart through two structural leaks: **history state survives page reloads** (your app state resets, the stack doesn't — the base entry reboots claiming an overlay is open, your anti-double-push guard then skips its push, and Back becomes a silent no-op), and **any close path that bypasses history orphans its entry** (later Backs pop stale overlay states that your popstate handler "stays open" for — multi-click Back). Cure: normalize at boot, make Back self-sufficient, and consume entries on non-history closes.

## Symptom

- A **dead Back button**: clicks demonstrably hit the button (top of the hit-test stack), handler runs, and nothing changes on screen.
- "It takes several Back presses to actually leave" after mixing close methods (Back sometimes, sidebar/nav-away other times).
- Nav chrome and content disagree: sidebar highlights Home while the overlay is still displayed.
- Worse after dev reloads / long HMR sessions — but only half of this is dev-flavored (see Cause).

The diagnostic tell, from a capture-phase click ring: the click reaches the right handler and **no state change follows**. The only silent no-op in a `handleBack → history.back() → popstate → close` chain is `history.back()` with nothing to pop — the browser doesn't throw, doesn't warn, does nothing.

## Cause

Three interlocking mechanisms:

1. **`history.state` persists across reloads.** A reload landing while an overlay entry is current reboots the app with `{view:'overlay'}` baked into what is now its base entry. React/JS state resets; the stack does not. In a Tauri/Electron webview this is dev-flavored (HMR full reloads; a prod restart gets fresh history) — **in a plain browser SPA/PWA it is prod-real on every F5**.
2. **Anti-stacking push guards trust `history.state`.** The standard guard — "don't push if the current state already says overlay" (there to stop double-pushes) — reads the inherited base state and skips. Now the overlay is open with **zero poppable entries**: `history.back()` no-ops, Back is dead.
3. **Closes that bypass popstate orphan their entries.** Sidebar-nav/nav-away closes call the close function directly and leave the pushed `{view:'overlay'}` entry on the stack. Later pops land on those stale states, and the popstate handler's "landing on an overlay state → stay open" branch eats the click. Each mixed open/close cycle stacks another one.

Same root both directions: **two sources of truth (stack vs UI state) with no reconciliation**, and a Back handler that blindly trusts one of them.

## Fix (four pieces, all cheap)

1. **Normalize at boot.** `history.replaceState(null, '')` before mounting the app. A reload can no longer inherit overlay state into the base entry, which also restores the push guard's soundness: after boot-normalization, an overlay state can only exist because your code pushed it, so it's always poppable.
2. **Make Back self-sufficient.** Pop via history only when the stack actually has an overlay entry: `if (history.state?.view === 'overlay' /* or 'editing' etc. */) history.back(); else closeOverlay();`. On a healthy stack popstate stays the single close driver; on a drifted one Back still works instead of silently no-opping.
3. **Consume the entry on non-history closes.** When sidebar-nav closes the overlay directly, `history.replaceState(null, '')` so the stale entry's state is nulled. The entry itself remains in the stack — which leads to:
4. **Make close-of-nothing a no-op.** Popping a dead null entry still fires popstate → your close function with nothing open. If that function has side effects (animation flags, "returning home" choreography), guard it: nothing open and not mid-close → return. Otherwise mouse-back on an idle screen replays close visuals against an empty overlay.

## Caveat: some orphaned entries are load-bearing

Before consuming entries everywhere, audit for flows that *deliberately* leave one — e.g. "overlay → navigate to a full screen; mouse-back from there restores the source screen" works precisely because the overlay's entry was left behind and the popstate handler routes it. Consume selectively (the direct-close paths), not globally, or you'll break the flows that were using the stack correctly.

## Transfer notes

- Applies to any history-based dismissal wiring: React SPAs, Electron/Tauri webviews, PWAs, mobile-web back-button UX. The reload-inheritance half is most vicious in plain browsers (F5 is a user habit, not a dev event).
- The general shape is the classic two-copies-of-truth drift (see [n-copies-of-truth-drift-guard.md](./n-copies-of-truth-drift-guard.md)) applied to browser history: you can't diff-and-fail-the-build here, so the mitigation is boot normalization + a self-sufficient consumer.
- Diagnosed originally from a tripwire dump (click ring + state-machine stamps proving the close machinery was healthy and the clicks landed) — see [instrument-before-patching.md](./instrument-before-patching.md); without it, the freshly-rewritten animation code would have been the obvious-and-wrong suspect.
