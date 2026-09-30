---
stack: [tauri, webkitgtk, wasm, sqlite, powersync, linux, debugging]
kind: gotcha
last_verified: 2026-09-19
---

# A WebKit webview eats 16 GB while every JS counter is frozen: JavaScriptCore's optimizing wasm tier compiling an Asyncify build

**One-liner:** a Tauri app on Linux (WebKitGTK) grew its web process by ~63 MB/s from launch until WebKit killed it at 16 GB, while the same app ran flat on Windows (WebView2/V8) every day. Heap profiling was useless: every JS-side counter froze while memory climbed. The cause was JavaScriptCore's optimizing wasm compiler tier (OMG) compiling the **Asyncify** build of SQLite-wasm (`wa-sqlite`, loaded by PowerSync). The fix is one engine flag, set from the native shell before the webview starts: `JSC_useOMGJIT=false`.

*Last verified 2026-09-19 on WebKitGTK 2.52.6 (Tauri 2, CachyOS, x86_64). The upstream bugs below were open then; re-check them before relying on the workaround.*

## Symptom

- `WebKitWebProcess` RSS rose linearly, unattended, ~63 MB/s from launch. After 3–4 minutes: `Unable to shrink memory footprint of process (18186 MB) below the kill thresold (16384 MB). Killed`. Then the Rust side logged that the frontend stopped answering. The machine had 124 GB; 16 GB is WebKit's own `MemoryPressureHandler` limit, not the system running out.
- Same code, same data on Windows WebView2: normal.

## What measurement ruled out (so you don't repeat it)

The first session's own hypotheses were each killed by a measurement before any fix was tried (write-up in the project's `docs/notes/D-47.md`):

| Suspect | Test | Result |
|---|---|---|
| CSS animations | a page with only the animations | flat, ~178 MB |
| Tauri itself | same frontend in WebKit's `MiniBrowser`, no Tauri (the app never even rendered) | 469 → 3334 MB in 20 s: still grows |
| a refetch/retry loop | request log | every request fired once |
| a no-OPFS fallback | OPFS absent even with COOP+COEP | not the trigger (see bisect) |
| wa-sqlite at all | 404 the wasm files | 191 MB flat vs 3334 MB |

The telling observation: **every JS-side counter froze** (14 IndexedDB transactions, 43 gets, 16 locks, 1 wasm instantiation, no errors, no retries) **while the process went 0.5 → 7.1 GB in 90 s.** Memory growing with no JS activity means the allocation is below the JS heap, in the engine.

## The bisect that proved it (60 s each, MiniBrowser)

| Variant | Peak RSS |
|---|---|
| Asyncify build + in-memory VFS (no IndexedDB, no PowerSync) | 11.0 GB, still climbing |
| Asyncify build + IDBBatchAtomicVFS (what the app uses) | 10.9 GB, still climbing |
| **Non-Asyncify** build + in-memory VFS, same workload | 0.27 GB, flat |
| Asyncify build, `JSC_useOMGJIT=false` | 242 MB, flat for 40 s |
| Asyncify build, `JSC_maximumOMGCandidateCost=20000` (default 100000) | 245 MB, flat (startup workload only) |
| a worker that instantiates the wasm but never calls it | 216 MB, flat |

So: not IndexedDB, not PowerSync, not Tauri. It needs the Asyncify transform plus actually running sqlite functions ("the compile only starts once sqlite functions actually run"), and it stops when OMG is off. Same mechanism as WebKit bug 304810 (Safari, same library) and powersync-js issue #1005 (Tauri 2 on WebKitGTK).

## The fix

JavaScriptCore reads options from `JSC_<option>` environment variables when the web process starts, and the web process inherits the app's environment. So set it natively, before the first window is created, and only on the WebKit platform:

```rust
#[cfg(target_os = "linux")]
fn tame_webkit_wasm_compiler() {
    const JSC_OMG_OPTION: &str = "JSC_useOMGJIT";
    // Respect a user who is already tuning JSC by hand.
    let already_tuned = std::env::vars().any(|(k, _)| k.starts_with("JSC_"));
    if !already_tuned {
        std::env::set_var(JSC_OMG_OPTION, "false");
    }
}
#[cfg(not(target_os = "linux"))]
fn tame_webkit_wasm_compiler() {}
```

**Cost:** wasm runs on the lower BBQ tier. That's fine when the only wasm is the SQLite engine. Verified by the user: 5+ minutes, flat around 1 GB.

**Not taken, and why:** the non-Asyncify build (needs OPFS, absent on that host); JSPI (WebKitGTK 2.54+, not exposed by the SDK then); raising WebKit's kill threshold (Tauri doesn't expose `WebKitMemoryPressureSettings`, and it wouldn't stop the growth, only delay the kill).

## The transferable method

1. **Frozen JS counters plus growing RSS means look below the heap.** Suspect the engine: JIT tiers, compiler threads, GPU process. Heap snapshots will show nothing.
2. **Reproduce outside your shell** (MiniBrowser, a bare page) to take your own framework out.
3. **Bisect by variant of the same module** (Asyncify vs sync build, real vs in-memory storage) and by **engine flag**, not by editing your code.
4. **Set engine flags from the native side before the webview spawns;** they're read once at process start.

## Sibling finding, same host

~1 s click latency on native Wayland in the same WebKitGTK app: `GDK_BACKEND=x11` fixed it (Playmoir prefers X11 when `DISPLAY` is set and no backend was chosen); `WEBKIT_DISABLE_DMABUF_RENDERER=1` made it far worse and crashed. Other Tauri apps report the same present-stall. Both Linux problems were engine settings, not reasons to go native.

## Related

- `first-build-on-a-second-os.md`: the build pass that surfaced this.
- `instrument-before-patching.md`, `negative-control-before-trusting-a-probe.md`: the measurement-first discipline that found it.
- `powersync-steam-backend-architecture.md`: where the wasm SQLite comes from.
