---
stack: [windows, rust, tauri, sentry, crash-reporting]
kind: dead-end-postmortem
last_verified: 2026-07-21
---

# A crash-reporter child process spins the Windows busy cursor for ~5s on every launch — and the fix you'd reach for is unreachable from stable Rust

> **This is a dead-end article.** There is no working fix here on stable Rust as of
> 2026-07-21. What it gives you is: how to identify this in about ten minutes
> instead of three hours, which promising-looking fix is *measured* not to work,
> and the pragmatic call that unblocks you. Written after a Playmoir session that
> spent most of a night on it and shipped the workaround, not the fix.

## The symptom

A Windows desktop app launches. The window appears, fully rendered, fully
responsive — you can click things, everything works. But the mouse pointer shows
the spinning blue "busy" ring for **~5 seconds** on **every single launch**.

Three things make this hard to place:

- **The app isn't busy.** Its UI is interactive the whole time. Profiling the app
  finds nothing, because nothing in it is slow.
- **It never reproduces in a debug build.** Dev is clean; only release does it.
- **It correlates with whatever you shipped recently**, so you'll blame the wrong
  feature. In our case it landed alongside an auto-updater and code signing, and
  we chased both for hours. It was neither.

## The cause

Any crash-reporting library that captures **native minidumps out-of-process**
spawns a helper child. The common design (Crashpad, and every Rust crate in this
space) is to **re-execute your own binary** with a marker argument or env var, and
have it branch into a socket-server loop.

That child is compiled from the same binary, so on Windows it inherits the
**GUI subsystem** flag. But it never opens a window and never pumps messages.

From Microsoft's [`STARTUPINFOW` docs](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/ns-processthreadsapi-startupinfow), verbatim:

> "If a GUI process is being started and neither STARTF_FORCEONFEEDBACK or
> STARTF_FORCEOFFFEEDBACK is specified, **the process feedback cursor is used.**
> A GUI process is one whose subsystem is specified as 'windows.'"

and

> "The system turns the feedback cursor off **after the first call to GetMessage**,
> regardless of whether the process is drawing."

So Windows starts the courtesy "app is loading" cursor for the child, waits for it
to prove it's alive, never gets the signal, and runs the timer to expiry. The
documented timing is 2s base, +5s once the process makes a GUI call.

**Your app was never busy. Windows was waiting on an invisible second process.**

This also explains the debug-build immunity: debug builds are typically
**console-subsystem** (`#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]`
is the standard Tauri/Rust idiom), and the doc's rule only covers GUI processes.

## Identifying it in ten minutes

1. **Open Task Manager and count your processes.** Two entries for your app, only
   one window? That's the crash reporter. This single check would have saved us
   the entire night.
2. **Toggle crash reporting off and relaunch.** If your app has a diagnostics
   opt-out that skips the reporter init, the cursor should vanish. That confirms
   the child is the cause without touching code.
3. **Build release *unsigned*** (e.g. `tauri build --no-bundle`, which skips the
   signing step). This is the discriminator that matters: signing and subsystem
   both change between dev and release, so a dev-vs-release comparison can't tell
   them apart. If the unsigned release build still spins, **Authenticode and
   certificate revocation are exonerated** — a common and plausible-sounding red
   herring, since new certs really do cause slow launches.

## The fix everyone else uses — and why you probably can't

Pass `STARTF_FORCEOFFFEEDBACK` in `STARTUPINFO.dwFlags` when spawning the child.
One flag. Prior art, all converged independently:

- **Chromium / Crashpad** — `client/crashpad_client_win.cc`: `startup_info.StartupInfo.dwFlags = STARTF_USESTDHANDLES | STARTF_FORCEOFFFEEDBACK;` (commit message: *"add STARTF_FORCEOFFFEEDBACK to prevent busy cursor on process launch"*). Inherited by Chrome, Edge, and every Electron app.
- **CPython** — same flag in `popen_spawn_win32.py` (2024).
- **Microsoft WSL** — [PR #14293](https://github.com/microsoft/WSL/pull/14293), sets it by default for spawned processes.

**The Rust trap:** `std::process::Command` has **no stable API for
`STARTUPINFO.dwFlags`**. The obvious candidate is a decoy —
`CommandExt::creation_flags()` sets `dwCreationFlags`, a *different field*, and
`CREATE_NO_WINDOW` / `DETACHED_PROCESS` concern console allocation only. They do
nothing here. The correct API, `startupinfo_force_feedback`, landed in 1.89.0 but
is still behind `#![feature(windows_process_extensions_startupinfo)]`
([rust-lang/rust#141010](https://github.com/rust-lang/rust/issues/141010)) as of
2026-07-21.

Consequence: **any Rust crate spawning via `std::process::Command` physically
cannot set this flag on stable.** Switching *your* project to nightly does not
help — the spawn happens in the dependency's code, not yours. The only routes are
forking the crate onto a hand-written `CreateProcessW`, or waiting for
stabilization.

## What does NOT work — measured, not assumed

**Calling `PeekMessageW` early in the child does not clear the cursor.**

The reasoning is seductive: the docs say `GetMessage` clears it, `GetMessage`
blocks so you can't use it, and `PeekMessage`'s `PM_NOYIELD` flag is documented as
*"prevents the system from releasing any thread that is waiting for the caller to
go idle"* — implying that `PeekMessage` *without* it does signal idle. An archived
MSDN thread states this outright.

We implemented it as the **first statement in the process**, verified via a file
probe written from inside the child (a windowless GUI process has nowhere to log,
so a file is the only channel) that the branch executed and `PeekMessageW`
returned. **The cursor was completely unaffected.** Tried twice — once after the
crash-reporting SDK init, once as the literal first line — to rule out the call
simply happening too late.

Do not spend time on this. If you want to try a variant, the only untested one is
`PostThreadMessage` to self followed by a real `GetMessage` (which would return
immediately with a message queued) — but that's a hack layered on an approach
already proven not to work.

## The pragmatic call: turn native minidumps off

For most apps this is the right answer, and it's usually a one-line feature flag.
(Tauri + Sentry: `tauri-plugin-sentry = { version = "0.5", default-features = false }`
drops the `minidump` feature and with it `sentry-rust-minidump`,
`minidumper-child`, `crash-handler`, `minidumper`.)

**Only the minidump lane spawns the child.** Everything else survives: JS errors,
unhandled rejections, UI error boundaries, **Rust panics**, and release-health
session tracking. None of those need a helper process.

What you actually lose: access violations, stack overflows, heap corruption, and
crashes inside C/C++ dependencies — the classes a language-level panic hook can't
catch.

**Weigh it honestly.** In our case the minidump lane had never caught a real bug
in months of use; it had only ever fired on a deliberate test crash from a debug
menu, while every genuine crash we'd caught came through the panic and JS lanes.
If your app has heavy native surface (we had whisper.cpp, D3D screen capture,
image codecs) the calculus may differ — but "we have native code" is not the same
as "native crashes are the ones we actually see." Check your own data before
paying a permanent fork to keep it.

**Also worth knowing:** for a webview-based app (Tauri, Electron), **renderer
crashes are invisible to every option here.** WebView2/Chromium run renderers in
separate processes that an in-process handler can't observe. So the scariest
failure mode — "the app just went white" — isn't covered whether you keep
minidumps or not. That materially lowers what you're giving up.

## When to revisit

Any of these unblocks the proper fix:

- `windows_process_extensions_startupinfo` stabilizes in Rust → the crate can set
  the flag with a one-line change.
- The crash-reporter crate switches to a raw `CreateProcessW` spawn.
- Your project gains enough native-crash volume to justify maintaining a fork.

**File the upstream issue if it doesn't exist.** When we hit this, a search across
every relevant repo (`minidumper-child`, `sentry-rust-minidump`, `sentry-tauri`,
`crash-handling`, `tauri-apps/tauri`) found **zero** reports — despite Crashpad,
CPython and Microsoft all having fixed the identical bug. Nobody had connected
those dots publicly. A good report with that precedent attached is cheap and makes
the fix likely.

## The meta-lesson

Three separate hypotheses were reasoned out confidently and two were wrong: the
auto-updater's network check (ruled out — it renders no UI and waits 5s before
even starting), and Authenticode revocation on a fresh code-signing cert (ruled
out by the unsigned release build). What finally resolved it was a **controlled
experiment changing one variable at a time**, not more reading.

When a symptom appears in release but not dev, list *everything* that differs
between those builds — subsystem, signing, optimization, bundled assets — and
find the build configuration that isolates one. Here that was
"release + unsigned," a combination neither dev nor the shipped installer
produces, and it killed a whole hypothesis in a single 40-second build.
