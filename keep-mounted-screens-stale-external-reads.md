---
stack: [react, tauri, desktop, state-management]
kind: pattern
last_verified: 2026-07-31
---

# Keep-mounted screens turn mount-only reads of external state into boot-time snapshots

> Caught twice in one hour on Playmoir (2026-07-31), on two different surfaces
> reading the same OS fact, staleness pointing in both directions. The
> architecture that causes it is common and deliberate: screens that never
> unmount (visibility via a class toggle, so navigation is a cross-fade and
> per-screen state survives). The cost is invisible until a second writer
> shows up.

## The failure shape

A component reads externally-owned state (an OS registry flag, a file, another
process's setting — anything the app does not own) in a mount-only effect:

```tsx
useEffect(() => {
  void isAutostartEnabled().then(setAutostart);
}, []);
```

In a router that unmounts screens, this re-runs on every visit and looks
correct for years. In a keep-mounted shell, **mount is app boot** — the read
happens once per process. The toggle it renders is a boot-time snapshot:

- Settings showed autostart OFF after another surface enabled it; a hard
  reload (re-running mount) "fixed" it — the tell.
- The subtle variant: a surface that resets **on departure** (a remount keyed
  to leaving, so returning is fresh) reads the state at the moment the user
  LEAVES — exactly one interaction before they change it on the next screen.
  It re-read, and was still stale by one toggle.

The bug is invisible with one writer, because the only writer is also the only
reader and it updates its own local state optimistically. It surfaces the day a
SECOND writer appears (another screen, a tray menu, the OS itself via Task
Manager) — which is also the day you least expect a years-old read to be the
problem.

## The fix: read on ARRIVAL, keyed on visibility

The shell already knows which screen is showing. Thread that down and key the
read on it:

```tsx
useEffect(() => {
  if (!visible) return;
  void isAutostartEnabled().then(setAutostart);
}, [visible]);
```

Every arrival re-reads; the surface can no longer disagree with reality by more
than one visit. Departure-keyed resets are the wrong moment for reads — reset
on departure if you must, but *read* on arrival.

## Rules of thumb

- **Own-state can be derived or evented; external state must be re-read.**
  For flags your app owns, prefer deriving them from already-correct state
  (see [[derive-dont-track-ui-flags]] — that pattern eliminates reset paths).
  External state has no event you can subscribe to (the OS won't tell you
  about Task Manager), so polling-on-arrival is the honest floor.
- Audit trigger: **the moment you add a second writer for any external fact,
  grep every reader of that fact for `}, [])`.** In a keep-mounted app, each
  one is a boot snapshot.
- "A hard reload fixes it" is the diagnostic signature — reload is the only
  thing that re-runs mount-only effects in a keep-mounted shell.
- Comments like "read from the OS, never from a cached flag" on a mount-only
  effect are describing an intention the lifecycle doesn't deliver. The read
  IS a cache; the question is only when it refreshes.
