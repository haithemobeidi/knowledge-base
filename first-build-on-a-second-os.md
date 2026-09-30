---
stack: [rust, tauri, cargo, git, linux, windows, release-engineering]
kind: checklist
last_verified: 2026-09-26
---

# The first build on a second OS: what silently rotted while only one OS ever compiled the code

**One-liner:** a Tauri app built only on Windows for months went to Linux for the first time (Playmoir, 2026-09-19). Nothing was "Linux-specific" in the plan, but five things had rotted silently because nothing had exercised them: a Windows-only crate in the unconditional dependency table, missing and outright *wrong* `#[cfg]` gates, a forced MSVC compiler flag in a config format with no per-target switch, git hooks without an executable bit, and a WebKit engine setting. Each was invisible from Windows by construction. If a codebase has only ever compiled on one OS, budget a pass for these before calling a port a porting job.

*Verified: Linux built from a clean clone in 43 s after the pass (2026-09-19); the gating changes re-verified with `cargo check` on x64 Windows on 2026-09-26.*

## 1. Platform code that never compiles elsewhere is untested code

- `windows-capture` (a Win32/WinRT crate) sat in `[dependencies]`, so cargo died before reaching any project code. It belongs in `[target.'cfg(windows)'.dependencies]` beside `winreg`/`wmi`/`windows`.
- About 26 `#[cfg(windows)]` labels were *missing* on already-Windows-only commands and helpers. That's labelling, harmless on Windows.
- **Two gates were plain wrong on main:** a `&str` const gated away from code that used it ungated, and a `#[cfg(windows)]` function imported without a gate. Neither could ever be noticed, since nothing compiled the crate off Windows.
- A platform-only function needs a no-op twin: `#[cfg(target_os = "linux")] fn x() {…}` plus `#[cfg(not(target_os = "linux"))] fn x() {}`, so the call site stays unconditional.

**Rule:** `cargo check --target <each supported target>` in CI or on a schedule, *even for targets you don't ship yet.* When you touch gates, compile on every target before believing "inert". This repo had no CI, so proving the Windows side took a week.

Cheap discovery: most "Windows-only" features were only registry-dependent; the file formats underneath (Steam's `.vdf`, library caches) were identical on Linux.

## 2. A forced config key with no per-target switch: use the tool's file hierarchy, not the environment

The repo-root `.cargo/config.toml` force-pinned `CXXFLAGS=/EHsc` (MSVC needs it for whisper.cpp's exception blocks). On Linux, gcc reads `/EHsc` as an input file name and the C++ build dies. The file's own comment had predicted it.

Cargo gives no direct lever: `[env]` has **no per-target conditionals**, and `force = true` **beats the process environment by design**, so no wrapper script can export its way around it. What works is cargo's **config merge**: it walks *up* from the working directory and the deeper file wins per key. Playmoir's commands run from `apps/desktop/src-tauri` and `apps/desktop`, so:

- a script writes `apps/desktop/.cargo/config.toml` (gitignored) overriding **only** `CXXFLAGS`;
- it runs from the root `package.json` `prepare`, so every `pnpm install` regenerates it;
- on Windows it writes nothing and deletes any stale copy, so Windows sees the root config unchanged;
- every other forced key (e.g. `GGML_NATIVE=OFF`, see `march-native-ships-an-unrunnable-binary.md`) is still inherited. Verified on a cleared build cache: gcc got `-fexceptions`, and `GGML_AVX512:BOOL=OFF` survived.

**General form:** when a build config has forced keys and no platform conditionals, generate a deeper, machine-specific override for just the one key from an install hook. Don't try to beat it with environment variables.

## 3. Git hooks committed from Windows have no executable bit

`post-checkout`, `post-rewrite` and `pre-push` were mode `100644` in the index (only `post-merge` was `100755`). Git for Windows ignores the mode, so this was invisible for months. On Linux, git **refuses to run a non-executable hook and only prints a hint**. `pre-push`, the hook that runs the whole project check before anything leaves the machine, had silently never run on that clone.

Fix: `git update-index --chmod=+x .githooks/<hook>` (a mode-only commit), and check `git ls-files -s .githooks` shows `100755` for every hook. A sourced library file stays `100644`. Activating hooks (`core.hooksPath` from `prepare`, see `n-copies-of-truth-drift-guard.md`) is only half of it; they also have to be executable.

## 4. The webview engine differs, and so does its memory behaviour

Same frontend, different engine (WebKitGTK instead of WebView2): an Asyncify wasm module ran the web process to 16 GB. See `webkit-wasm-optimizer-memory-runaway.md`. Also on native Wayland, ~1 s click latency; preferring X11 when `DISPLAY` is set fixed it.

## 5. The system-library preflight

Extend the dev-environment check for the new OS: cmake, a C++ compiler, and the `pkg-config` libraries the webview needs, with a clear message naming the missing package. It turns a 200-line linker error into one line.

## Checklist

- [ ] OS-specific crates in `[target.'cfg(...)'.dependencies]`
- [ ] every platform-only item gated, with a no-op twin where called unconditionally
- [ ] `cargo check` on every supported target (CI or scheduled)
- [ ] forced build-config keys reviewed for the new toolchain; override per machine via the config hierarchy
- [ ] git hooks `100755` in the index
- [ ] webview engine differences: memory, input latency, codecs
- [ ] dev-env preflight names the missing system packages

## Related

- `march-native-ships-an-unrunnable-binary.md`: the same root cargo config, from the CPU-feature side.
- `n-copies-of-truth-drift-guard.md`: hook activation.
