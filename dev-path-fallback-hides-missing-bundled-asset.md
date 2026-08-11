---
stack: [tauri, rust, electron, python, packaging, release-engineering, desktop]
kind: gotcha
last_verified: 2026-08-10
---

# A dev-path fallback hides a missing bundled asset from the only person who could catch it

**One-liner:** when your app looks for a bundled asset and falls back to a path derived at build time (`CARGO_MANIFEST_DIR`, `__dirname`, `__file__`, a repo-relative path), that fallback resolves **on the machine that compiled the binary and nowhere else** — so if you forget to actually bundle the asset, the feature works perfectly for you, is broken in 100% of installed copies, and cannot be discovered by anyone whose report you would believe. The bug survives every release until an outsider tries the feature.

## The shape

You add a feature needing a large asset — an ML model, a dictionary, a sample database, a binary helper. It's too big for git, so a setup script fetches it into the repo. Your locator is reasonable:

```rust
fn resolve_model_path(app: &AppHandle) -> Result<PathBuf, String> {
    // 1. production: shipped alongside the executable
    if let Ok(dir) = app.path().resource_dir() {
        let bundled = dir.join("resources/models/model.bin");
        if bundled.is_file() { return Ok(bundled); }
    }
    // 2. dev convenience: the copy the setup script fetched
    let dev = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("resources/models/model.bin");
    if dev.is_file() { return Ok(dev); }

    Err("model not found".into())
}
```

Then you defer the packaging work — "wire up `bundle.resources` in the packaging pass" — and never come back to it. Branch 1 never matches in production. Branch 2 always matches for you.

`env!("CARGO_MANIFEST_DIR")` is expanded **at compile time into a string literal**. The shipped binary contains, verbatim:

```
C:\Users\you\Documents\Projects\YourApp\apps\desktop\src-tauri
```

On your machine that directory exists and holds the asset. On a user's machine it is a path into a stranger's filesystem. The lookup fails, the feature errors, and the error is whatever generic thing your UI says when that subsystem fails.

Same trap, other ecosystems:

| ecosystem | the fallback that only works at home |
|---|---|
| Rust / Tauri | `env!("CARGO_MANIFEST_DIR")` |
| Electron | `__dirname` outside the asar, or `path.join(app.getAppPath(), '../assets')` |
| Python / PyInstaller | `os.path.dirname(__file__)` instead of `sys._MEIPASS` |
| Go | `runtime.Caller(0)` to find source-relative data |
| Java | a `src/main/resources` **file path** rather than `getResourceAsStream` |
| Node CLI | `process.cwd()`, which works because you always run it from the repo |

## Why it survives so long

Three reinforcing blind spots, and they are the actual lesson:

1. **The person best placed to notice is structurally unable to notice.** You test on the build machine. The build machine is the one machine where the bug is invisible. This is not carelessness; it is the topology.
2. **The error message describes the symptom, not the cause.** A missing model surfaces as "Couldn't transcribe that. Please try again." — which reads as flaky, invites a retry, and never says *file not found*. A user reports "voice is broken sometimes." Nobody says "your app is looking for a folder that only exists on your computer."
3. **The docs claim it's already done.** The deferral gets written down as if completed. Our `.gitignore` said the file was *"bundled into the production installer at build time via `bundle.resources`"*. It never was. Every future reader — including the author — checks that comment, sees the problem is handled, and moves on. **A confident comment about an unfinished step is worse than no comment**, because it converts an open question into a settled one.

Ours shipped in four consecutive releases and was found by a friend of the developer, on his own machine, on a feature the developer had "tested" many times.

## The fix, in order of importance

**1. Delete the compile-time fallback.** This is the whole lesson. Do not make it conditional on `cfg!(debug_assertions)`, which preserves the exact asymmetry — a dev build still succeeds where a user's fails. Remove it, so your dev run resolves the asset the same way a user's does and you *feel* the first-run path every time it changes. If the asset must exist for tests, let the tests pass an explicit path; test fixtures and runtime lookup are different concerns and should not share a code path.

**2. Decide bundle-vs-download deliberately, then verify the decision landed.** Bundling is simplest but every desktop update mechanism that replaces the installer re-ships the payload — a 141MB model becomes 141MB on every release for every user, including those who never use the feature. Downloading on first use keeps it in the app data dir, where it survives updates and costs each user once. Either way, **check the built artifact rather than the config**:

```bash
# Does the thing you shipped actually contain the thing?
ls -R "$INSTALL_DIR" | grep -i model
# And what path did the binary bake in?
strings App.exe | grep -iE '^[A-Za-z]:\\Users\\'   # any hit here is a bug
```

That second command is the cheap general-purpose detector: **a shipped binary containing an absolute path into a developer's home directory is a defect**, whatever it's for.

**3. Make "asset missing" a distinct, named error.** Not the generic failure the feature already has. Missing-asset and operation-failed need opposite UI — one offers setup, the other offers retry — and merging them produces a screen that invites users to retry something that can never succeed. A sentinel error value that survives the IPC boundary is enough.

**4. Check before the user commits effort.** If the asset is missing, say so when they press the button, not after they have spoken a two-minute voice memo. The ordering is free and the difference in insult is large.

## The generalisation worth keeping

**Any fallback whose success depends on properties of the build machine is a bug detector that is disabled on the only machine that runs it.** Compile-time paths are the clearest case, but the family is larger: an env var set only in your shell, a service running only on your box, a file in your home directory, a locally-installed dependency. If a code path can only succeed where it was compiled, it is not a fallback — it is a way of not finding out.

## See also

- [march-native-ships-an-unrunnable-binary.md](./march-native-ships-an-unrunnable-binary.md) — the same generalisation one layer down, and the same feature one release later: having fixed the missing model, the next release shipped one compiled with `-march=native`, so the asset was finally present and the CPU refused the *code*. File paths are the obvious build-machine leak; **compile flags are the invisible one**.
- [verify-the-artifact-your-user-receives.md](./verify-the-artifact-your-user-receives.md) — same family: what you built and what a stranger receives are different objects, and only one of them matters.
- [bot-challenge-blocks-your-auto-updater.md](./bot-challenge-blocks-your-auto-updater.md) — if you fix this by downloading the asset at runtime, read this before choosing the host. Your own CDN may refuse your own app.
