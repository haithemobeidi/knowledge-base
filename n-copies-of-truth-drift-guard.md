---
stack: [any, local-first-sync, monorepo, codegen, zod]
kind: pattern
last_verified: 2026-07-20
---

# N copies of one schema must agree — build the drift-guard, don't rely on discipline

**One-liner:** any app where a single piece of data is *described* in more than one independently-maintained place will drift, silently, no matter how careful you are — because the failure mode isn't an error, it's data quietly not showing up. The fix is a small script that diffs the copies and fails the build, not a checklist saying "remember to update all of them."

## The general shape (not specific to sync apps)

Think of it as **N copies of the same address book.** As long as they're identical, mail gets delivered. The moment you add a field to the "thing," every copy has to learn about it — and copies are, by construction, independent artifacts that don't know about each other:

- A database schema (columns that exist)
- A replication/sync layer's field allowlist (PowerSync sync rules, ElectricSQL shapes, a GraphQL resolver's selected fields)
- A client-side schema/type the app validates incoming data against (Zod, io-ts, a hand-written interface)
- A shared validator library consumed via a **compiled artifact** (`dist/`) that can itself go stale independently of its source
- A server-side write-allowlist (which columns a client is permitted to write back)
- Generated code from a schema-definition language (protobuf `.proto` → N language bindings, OpenAPI spec → generated client, GraphQL SDL → generated types)

Any stack that has **2 or more** of these for the same conceptual "thing" is exposed. Playmoir has six (Postgres, `powersync-sync-rules.yaml`, the PowerSync client schema, `packages/core`'s Zod types, the server's `WRITABLE` column allowlist, and `packages/core/dist`'s build-artifact freshness) — but the pattern is the same whether it's 2 layers or 6.

## Why it's insidious: the failure mode is silence, not an error

This is what makes it worse than a normal bug class — **nothing throws.**

- Validation libraries with strip-unknown-keys-by-default semantics (Zod's default `.parse()` behavior, and most others) don't error when a payload has fewer fields than expected — they just don't populate the field. A dropped column looks identical to "this value is empty," not "this value failed to load."
- Replication/sync engines often **freeze field lists at deploy time.** Redeploying byte-identical rules (`SELECT *`, or an unchanged shape definition) is frequently a no-op — the engine doesn't re-diff and re-stream historical rows just because you re-clicked deploy. A column added to the source DB after the last rules deploy is invisibly never sent, forever, until someone notices.
- Workspace-package / monorepo builds resolve through a **compiled artifact**, not source. `git status` is clean, the source file has the new field, but the runtime is running a build from days ago. No tooling surfaces this by default — restarting the dev server re-imports the *same* stale artifact.
- The tool that WOULD catch a lot of this (`tsc`, a real type-checker) frequently **isn't in the hot path.** Vite/esbuild/swz transpile-only pipelines strip types without checking them; you only get the error if you separately run `tsc --noEmit`, and most projects don't wire that into every dev-server restart.

Put together: you can add a field to your "source of truth," ship it, and have it be silently absent on some device/client/environment for days, with a fully green build and no console error anywhere.

## Concrete incidents (Playmoir, 2026-06 → 2026-07)

Two independent production bugs, same root shape, ~10 days apart:

1. **`session_summary` column** (an AI-generated field) synced to Postgres but the PowerSync sync rules were still the pre-column version — redeploying the (byte-identical-looking, but actually stale) rules didn't re-stream it. Separately, one device's `packages/core/dist` was compiled 3 days before the Zod schema added the field, so even after the sync-rules fix landed, Zod silently stripped the column from every row on that device. Two bugs stacked, each masking the other — see `monorepo-stale-dist-zod-strip.md` for the full postmortem.
2. **`installed` columns** (a free-tier install-state feature) went missing from one of the schema layers in the very same session this lesson was written, and nothing caught it — because `tsc` doesn't run automatically in this project's dev loop.

Both were caught by a human noticing wrong behavior in the UI, not by tooling. Both cost a debugging session that a 30-line script would have prevented.

## The fix: a script, not a reminder

> "The drift-guard is a tiny script that reads all five copies and yells if they disagree. Users never see it — it's a test that runs when we build."

Concretely, for each pair of layers that describes the same "thing," write a check that:

1. **Extracts the field/column list from each layer programmatically** — not by eyeballing files:
   - DB: introspect `information_schema.columns` (Postgres) or parse migration files for the current column set.
   - Sync rules: parse the YAML/config and pull the explicit column list (this is also *why* explicit column lists beat `SELECT *` in a sync-rules file — `SELECT *` can't be diffed against anything, and can't be told apart from itself when it silently doesn't cover a new column).
   - Shared validator: Zod schemas are introspectable at runtime — `Object.keys(schema.shape)` gives you the field list without re-parsing source. (Equivalent facilities exist for io-ts, Yup, protobuf reflection, etc.)
   - Server write-allowlist: it's just an array/object in source — import it and read the keys.
   - Build-artifact freshness: compare the `dist/` file's mtime (or a content hash) against its source file's mtime/hash; flag if source is newer.
2. **Asserts set-equality (or a defined superset relationship)** between each pair, and prints a **diff table** on mismatch — which layer has the field, which doesn't — so the failure is immediately actionable, not a generic "schemas don't match."
3. **Fails the build/CI**, not just logs a warning. A drift-guard that only warns gets ignored the same way the manual checklist did.
4. **Runs on every build**, not on a schedule or "when someone remembers." Wire it into whatever already gates merges/deploys (a `pnpm build` prestep, a CI job, a pre-push hook) so it's structurally impossible to skip.
   - **A committed git hook only runs once someone has locally activated it** (e.g. `git config core.hooksPath .githooks`), and that's a manual, easy-to-forget, per-clone step — a drift-guard living in a hook nobody activated is exactly as unenforced as a checklist. Close the gap with your package manager's install lifecycle instead of a README instruction: an npm/pnpm `"prepare"` script (`git config core.hooksPath .githooks && <build the guarded package>`) runs automatically on every `install`, on every machine, with zero action from the developer — turning "did you remember to activate the hook" into a non-question. Pair it with a **dev-server prestep** that rebuilds the workspace package before starting (`"dev": "pnpm --filter <pkg> build && vite"`), so `pnpm dev` itself cannot serve a stale `dist/` even between hook-gated pushes.

## When to build one

Build the drift-guard **before** any piece of work that has to touch every layer at once — a schema migration, a new synced field, or (Playmoir's trigger) gating a subsystem behind a paywall, which by nature touches DB + sync + client + server write path simultaneously. That's the moment the N-layer surface is guaranteed to move, so it's the cheapest point to add the seatbelt: cheap insurance right before the drive that most needs it, not a retrofit after the next silent-data-loss bug.

## What NOT to do

- **Don't write "remember to update all N places" in a doc and call it solved.** That's exactly the discipline-based approach that already failed twice on the same project. Docs don't run; scripts do.
- **Don't treat "no error in the console" as "no drift."** The whole danger of this bug class is that the default behavior of most validation/replication tooling is to hide the mismatch, not surface it.
- **Don't rely on redeploying a sync-rules/config file as proof it re-took effect.** If the new deploy is byte-identical to the old one (e.g. `SELECT *` both times), many sync engines treat it as a no-op. Prefer explicit field lists specifically because they force the tooling to notice a change.
- **Don't scope the guard to just "the sync layer."** Include build-artifact freshness as its own layer in a monorepo — a stale compiled `dist/` is invisible to every other check and needs its own mtime/hash comparison.

## Related

- [`monorepo-stale-dist-zod-strip.md`](./monorepo-stale-dist-zod-strip.md) — the detailed postmortem of incident #1 above; that doc's "structural fixes" section is what this lesson generalizes into a standalone pattern.
- [`powersync-steam-backend-architecture.md`](./powersync-steam-backend-architecture.md) — the 6-layer architecture this pattern was extracted from.
