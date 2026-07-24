---
stack: [tauri, rust, sentry, javascript, vite, crash-reporting]
kind: gotcha
last_verified: 2026-07-24
---

# Turning ON source-map symbolication silently deletes every JS error report in a Tauri app

> The fix causes the bug. Before you wire up source maps, JS errors arrive in
> Sentry (unreadable, minified). The moment you add `@sentry/vite-plugin` so the
> stack traces become readable, **every JavaScript event stops arriving** — with
> no error, no warning, and no failed network request anywhere. Rust panics keep
> flowing the whole time, so the dashboard looks alive.
>
> Hit and independently root-caused in Playmoir (Tauri 2 + React +
> `tauri-plugin-sentry`) on 2026-07-24 after most of a night. It had already
> been diagnosed publicly seven weeks earlier — see **Upstream status** for the
> credit and, more usefully, for why an accepted root cause still has no fix.

## The symptom

- `Sentry.captureException()` fires. You can prove it: a `console.log` right
  before it runs, a breadcrumb, a debugger break. The call happens.
- Nothing appears in Sentry. Not delayed — never.
- **Rust panics and breadcrumbs from the same app arrive fine.** So the DSN is
  right, the network is fine, the project is right, the release exists.
- It only happens in **release** builds. Dev is clean.
- It started when you turned on symbolication, which is the last thing you'd
  suspect, because symbolication is supposed to be a *display* concern.

That last point is what makes this expensive. Everyone's instinct is that
source maps affect how a trace is *rendered*, not whether the event is
*delivered*. Here they decide delivery.

## The cause chain

Five links, each individually reasonable:

1. **`@sentry/vite-plugin` injects debug IDs** into your bundle. That is its
   entire job: stamp each file with an ID so Sentry can match a minified frame
   to an uploaded source map.
2. **`@sentry/browser` >= 7.44 notices those IDs** and attaches a
   `debug_meta.images` entry to every event:
   ```json
   { "type": "sourcemap", "code_file": "...", "debug_id": "..." }
   ```
3. **In a Tauri app the JS SDK does not POST to Sentry.** `tauri-plugin-sentry`
   installs a transport that hands the serialized envelope to Rust over IPC
   (the plugin's `envelope` command) so both language sides share one client,
   one release, one session.
4. **The Rust side parses that envelope with `sentry-types`**, whose
   `DebugImage` enum is `#[serde(tag = "type", rename_all = "snake_case")]` over
   a **closed** set: `apple`, `symbolic`, `proguard`, `wasm`. There is no
   `sourcemap` variant. `Envelope::from_slice` fails with
   `unknown variant "sourcemap"`.
5. **The plugin ignores the parse result.** The command is shaped
   `if let Ok(envelope) = Envelope::from_slice(&bytes) { ... }` — with **no
   `else`**. A parse failure is indistinguishable from "nothing happened."

Net effect: one unknown enum variant, added by a build plugin from the *same
vendor*, silently discards 100% of your JavaScript telemetry.

## Identify it in ten minutes instead of six hours

Run these in order. Each one halves the search space.

1. **Prove capture fires.** `console.log` immediately before
   `captureException`. If it logs, stop debugging your capture code — it is
   correct, and every hour spent on Sentry init options is wasted.
2. **Compare against the native side.** Trigger a deliberate Rust panic. If
   Rust events land and JS events don't, the problem is **at the JS→native
   boundary**, not in SDK configuration, DSN, sampling, or filters. This is the
   highest-value single test.
3. **Check whether your bundle carries debug IDs.** Grep the built assets for
   `debugId` / `sentry-dbid`. Present = you are in the failure mode. Absent =
   this article is not your bug.
4. **Confirm by removing the trigger.** Temporarily drop `@sentry/vite-plugin`
   from the build, rebuild, retest. Events come back (minified). That single
   observation identifies the whole chain and is worth doing before you write
   any patch.

Do NOT bother reading the plugin's network layer, adding `beforeSend` logging,
or raising sampling rates. Nothing is being *rejected*; something is being
*dropped without a code path*.

## The fix, until upstream moves

Vendor `sentry-types` and add the missing variant. Wire it in with
`[patch.crates-io]` so the whole dependency tree (`sentry`, `sentry-core`,
`tauri-plugin-sentry`) resolves to your copy:

```toml
# src-tauri/Cargo.toml
[patch.crates-io]
sentry-types = { path = "vendor/sentry-types" }
```

Two non-obvious details in the patch itself:

**The wire name is `sourcemap`, not `source_map`.** The enum carries
`rename_all = "snake_case"`, so the derived name for a `SourceMap` variant
would be `source_map` and would not match. It needs an explicit rename:

```rust
#[serde(rename = "sourcemap")]
SourceMap(SourceMapDebugImage),
```

**Make every field optional, and keep `debug_id` a `String`, not a `Uuid`.**

```rust
pub struct SourceMapDebugImage {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub code_file: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub debug_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub debug_file: Option<String>,
}
```

This patch exists *because* a strict parse silently ate whole events. Re-adding
strictness inside the fix — a required field, a typed `Uuid` that rejects an
oddly formatted ID — would recreate the same class of failure one layer down.
Relay validates this server-side anyway. Parse loosely at the boundary you do
not control.

Keep the vendored copy byte-identical to the published crate apart from the
patch, with every change marked by a greppable comment (`PLAYMOIR PATCH`), so a
future upstream release can be diffed against it. Exempt the directory from your
repo's file-size / docs-coverage rules; it is third-party code.

## Upstream status

All of the following verified on **2026-07-24** by reading the sources directly,
not from memory.

**Prior art — this was diagnosed publicly before we hit it.** Credit where it's
due: `ottosson` posted the identical cause chain (closed `DebugImage` enum →
`InvalidItemPayload` → the plugin's error-free `if let Ok`) on
[bundler-plugins#916](https://github.com/getsentry/sentry-javascript-bundler-plugins/issues/916)
on **2026-06-02**, with a minimal reproducer
([sentry-vite-plugin-repro](https://github.com/ottosson/sentry-vite-plugin-repro))
and a fix fork. The `sentry-tauri` maintainer agreed the next day. If you land
here, read that thread first — it is the canonical write-up. Cross-posted at
[sentry-tauri#35](https://github.com/timfish/sentry-tauri/issues/35).

**Nothing has shipped since.** `timfish/sentry-tauri`'s last commit is
2026-02-11 (predating the diagnosis), so the silent `if let Ok` is still live,
and `getsentry/sentry-rust` master still has no `sourcemap` variant.

**The fix is filed in the wrong place.** As of today a GitHub search of
`getsentry/sentry-rust` for a `sourcemap` / `DebugImage` issue returns **zero
results**. The diagnosis lives entirely on the *bundler plugin's* tracker, which
is the one repo that turned out not to be at fault. That is very likely why a
seven-week-old accepted root cause has produced no fix: nobody opened it against
the crate that has to change. If you are blocked on this, filing there is worth
more than another +1 on #916.

**Remove the vendor when** upstream ships a `sourcemap` `DebugImage` variant (or
tolerant envelope parsing) AND `tauri-plugin-sentry` depends on that release.
Then delete `vendor/` plus the `[patch.crates-io]` block, bump the deps, and
re-run a deliberate JS crash to confirm delivery still works. Re-check this at
dependency-bump time, not on a calendar.

## The transferable lessons

Three, in descending order of how often they will bite you again:

1. **`if let Ok(x) = parse(...)` at a boundary is a silent data destroyer.**
   Any parse-and-discard without an `else` converts a schema mismatch into
   nothing at all. At a telemetry boundary this is particularly cruel: the
   system whose job is reporting failures fails by reporting nothing. If you own
   such a boundary, log the parse error even if you cannot recover.
2. **A closed enum deserialized from a producer you don't control is a
   time bomb.** The producer will add a variant eventually. Prefer a tolerant
   fallback (`#[serde(other)]`, or capturing unknown variants into a raw value)
   for anything crossing a version boundary, especially when both sides ship on
   independent release cycles from the same vendor.
3. **Verify observability end to end, deliberately, per lane.** "Sentry is
   wired up" is not a state you can assume from a green build. Trigger a real
   error in *each* lane (JS, native, server) against a *release* build. Playmoir
   only found this because someone pressed a deliberate-crash button in a signed
   build and compared lanes; ordinary usage would have shown a quiet dashboard
   and been read as "no bugs."
