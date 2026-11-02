---
stack: [node, npm, pnpm, cli, tauri]
kind: gotcha
last_verified: 2026-11-02
---

# `npm run` swallows one `--` before your script sees it, `pnpm` passes every one through, and `node -e` eats one too

**One-liner:** Forwarding arguments through a package-manager script shifts every `--` by a different amount depending on the tool. `npm run x -- a` hands the script `a`; `pnpm x -- a` hands it `-- a`. A command copied between the two (or from a README written for the other) moves the boundary between "options for the tool" and "arguments for the app". Probe with a real script file that prints `process.argv`, because `node -e` consumes a `--` itself and gives a wrong answer.

## Measured (Windows 11, 2026-11-02)

A package with `"scripts": {"show": "node probe.js"}` and `probe.js` printing `JSON.stringify(process.argv.slice(2))`:

| Command | Script receives |
|---|---|
| `npm run show -- -- a` (npm 11.5.2) | `["--","a"]`: one `--` removed |
| `pnpm run show -- a` (pnpm 10.33.0) | `["--","a"]`: nothing removed |
| `pnpm show -- -- a` | careful: `show` is a built-in pnpm command (registry lookup), not the script |
| `pnpm argz -- -- a` (implicit run, and with `-C <dir>`) | `["--","--","a"]`: nothing removed |

And the probe itself:

| Command | `process.argv.slice(1)` |
|---|---|
| `node -e "…" -- a` | `["a"]`: node treats `--` as the end of ITS options |
| `node probe.js -- a` | `["--","a"]` |

So an argv probe written as `node -e` reports one `--` fewer than a real script would see, which is exactly the wrong answer for this question.

## Where it bit: passing an app argument through `tauri dev`

Tauri's CLI takes `tauri dev -- [runnerArgs] -- [appArgs]` (from `tauri dev --help`, tauri-cli 2.10.1). To start a Tauri app in dev as if launched at login (`--autostart`), the command that worked from the repo root was:

```
pnpm -C apps/desktop tauri dev -- -- -- --autostart
```

Confirmed by the running process's command line: `target\debug\playmoir-desktop.exe --autostart`. pnpm passed all three `--` to the CLI. Which layer inside tauri-cli and cargo consumed the extra one was not measured; the likely candidate is the argument parser's own end-of-options marker. If a variant fails, check the process's command line (Task Manager's Command line column, or `Get-CimInstance Win32_Process`) instead of guessing.

The same session first concluded "pnpm strips one `--`", which is wrong. The script-file probe above disproves it. Measure each layer on its own instead of explaining the count after it works.

## Rule

- Treat `--` counts as tool-specific. Re-derive them when a command moves between npm and pnpm (or yarn, not measured here).
- Probe with a script file, never `node -e`, and never with a script name that collides with a built-in command (`pnpm show` queried the registry instead of running the script named `show`).
- For the final say, read the target process's own command line.
