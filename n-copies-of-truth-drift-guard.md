---
stack: [any, local-first-sync, monorepo, codegen, zod, deploy]
kind: pattern
last_verified: 2026-08-01
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

## The stale-clone variant: a git-backed source of truth that nobody pulled

The N-copies problem has a time-axis twin that no consistency check can catch: **a local clone of a source of truth is stale by default, and a stale clone doesn't look broken — it looks complete and self-consistent.** Two independent instances hit the SAME day (2026-07-25): a project checkout opened 8 commits behind (its status docs confidently reported a closed item as the next action — `git status` said "up to date," which only compares against the last-fetched ref), and a knowledge-base clone used to answer "is this topic already covered?" while 16 commits behind (it reported "not covered" for topics that were, nearly filing a duplicate).

The structural point: **internal-consistency checks cannot detect staleness.** Stale copies of a set of documents agree with each other perfectly. The only defense is procedural and dumb: *any workflow step that READS a git-backed source of truth starts with a fetch/pull* — session-start protocols, coverage checks, doc generators, anything. Put the pull IN the step's script/checklist, before the read, not as general advice. And treat "up to date with origin/X" from `git status` as meaning "up to date with the last time this machine talked to the remote," which without a fetch can be days.

## The destructive variant: a "reader" that is secretly a writer

Everything above assumes the failure mode is **absence** — a field silently doesn't arrive. There is a nastier sibling where the failure mode is **destruction**, and the drift-guard as described will not catch it, because the offending layer isn't a schema copy at all.

The setup: two independent paths populate the same rows. A streaming/replication path (the one everybody thinks about), and a **bootstrap or fallback path** — a plain REST endpoint that fetches "the current set" and writes it locally on login, on a manual refresh, or for users who aren't on the streaming tier. The second path is filed mentally under *reading*, so it never occurs to anyone that it's a copy of the truth.

Then someone adds a column, walks the documented lockstep (DB → sync rules → client schema → write allowlist → server registry), and ships. The bootstrap endpoint isn't on that list, so its `SELECT` still doesn't carry the new column. Now look at what it does with what it fetched:

```sql
INSERT INTO games (id, name, reminder_at, ...)
VALUES ($1, $2, $3, ...)
ON CONFLICT(id) DO UPDATE SET
  name        = excluded.name,
  reminder_at = excluded.reminder_at,   -- <-- unconditional
  ...
```

`excluded.reminder_at` is NULL, because the source this path fetched from never selected the column. So every routine library refresh **erases a value the user set**, on a path whose entire job was supposed to be reading. Not "the field doesn't show up." The field is destroyed, repeatedly, in the background.

Why it survives all the usual nets:

- **The lockstep checklist misses it** — the checklist enumerates *schema layers*, and this is a *route*.
- **The drift-guard misses it** — the guard compares column lists between schema definitions. A hand-written `SELECT` inside a request handler isn't one of them.
- **Nothing throws.** A partial row is a perfectly valid row.
- **It only reproduces on the second write.** The first sync sets the value; the erasure needs a later refresh, so it won't show up in the "does it save?" test you just ran.

In the incident this comes from, the only thing that caught it was that the call site was **strictly typed** — adding two fields to the shared input interface made the compiler point at the one caller that couldn't supply them. With a loosely typed boundary (`any`, a bare `as`, an untyped JSON handoff) it ships as silent, recurring data loss.

### Three fixes, in order of leverage

1. **When adding a column, enumerate WRITE PATHS, not schema layers.** Grep the codebase for everything that ends in `INSERT` / `ON CONFLICT` / `UPSERT` / `PATCH` against that table and ask each one "can this run with a partial source?" A path that can write a row IS a copy of the truth, whatever you call it.
2. **Make partial-source upserts structurally incapable of erasing.** Either omit the column from the `DO UPDATE SET` list on that path, or write it defensively so a missing source value preserves what's there:
   ```sql
   reminder_at = COALESCE(excluded.reminder_at, games.reminder_at)
   ```
   Pick per column deliberately: `COALESCE` means the path can never clear the field, which is wrong for columns where NULL is a meaningful value the path is authoritative for (a tombstone being lifted, a status being unset). The general rule is that **only a path that is authoritative for a column may write NULL to it.**
3. **Type the boundary strictly, precisely so the compiler forces the question.** The strict interface is what converted "silent data loss discovered by a user weeks later" into "the build fails and names the file." This is the payoff for not reaching for `any` at sync boundaries.

### The generalized tell

> If a code path can write a row, it is one of the N copies — even when everyone on the team describes it as a reader.

Bootstrap fetches, "refresh" buttons, import/restore flows, admin backfill scripts, and cache-warming jobs are all in this category. They tend to be written early, when the table has five columns and carrying all of them is trivially easy, and they quietly become erasers as the table grows.

## The deployed variant: the copy your drift-guard cannot see

Build the script from the section below and you close the gap between the copies **in the repo**. There is one more copy, and it is the one that actually serves traffic: **the deployed artifact.** A checker that reads files on disk is structurally incapable of seeing it, so it reports green while production is broken.

The shape (Playmoir, 2026-07-27): a column was added and the full lockstep walked — Postgres migration applied, sync rules deployed, client schema, write-through, both upsert paths, PATCH allowlist, and the server's `WRITABLE` registry. Every layer agreed. `check:sync-contract` passed. The commit was pushed. **The server was never redeployed.** The `WRITABLE` change existed in git and nowhere else.

Why the blast radius was total rather than partial, and this is the part worth stealing:

- CRUD-style sync engines capture a write's **full replicated column set**, not just the columns your statement touched. So one unknown column doesn't drop that column — it invalidates the entire row write.
- The server validated with a **strict** schema (`.strict()` / `additionalProperties: false`), which is correct and is what you want. Combined with the above, it rejects the whole payload.
- Upload queues drain **in order**. The rejected transaction never completes, so everything queued behind it is stuck too — including writes that have nothing to do with the new column.

Net effect: a single missing column on one deployed file presented to the user as *"all backup is broken, and Retry doesn't help."* Retry cannot help, because the payload is permanently invalid against the deployed schema; it isn't a transient fault, so retrying forever is the correct behavior and also useless.

**The tell in the record:** every previous server change's log entry said "server deployed + verified." The one that broke it said only "pushed." If your handoff notes distinguish those two words, the diff between them is a deploy you owe.

Three defenses, in order of leverage:

1. **Expose the deployed version.** A `/version` endpoint returning the commit SHA turns "is prod current?" from an act of memory into one HTTP request — and lets the drift-guard compare it to `HEAD` for the server directory.
2. **Fail the check when the server dir has commits newer than the last recorded deploy.** Cheap, no infrastructure, catches exactly this.
3. **At minimum, name the step.** If "deploy the server" is implied rather than written in the lockstep checklist, it will be skipped by whoever is tired.

> The generalized rule: **a contract test that only reads the repo is testing agreement, not reality.** Agreement between copies you can see says nothing about the copy you can't.

### The lockstep sub-variant: one commit, two release mechanics

The section above is about a deploy someone *forgot*. This one is worse, because nobody forgot anything and the discipline was followed exactly.

The setup: the same logic lives in two languages — a prompt, a validation rule, a pricing table — because the two call sites are a native client and a server (see `byo-api-key-client-direct-tier.md` for why that duplication is sometimes correct). The accepted practice is to patch **both copies in lockstep, in one commit**. Do that and the copies are byte-correct and provably synchronised in git.

They are still not synchronised in production, because **the two copies ship through different release mechanics.** The native copy is compiled into the app binary and reaches users when they update. The server copy reaches users when someone runs `deploy`. One commit, two cadences, no signal anywhere that half of it is still on the shelf.

Playmoir, 2026-08-01: a prompt gained entity-tagging instructions; both copies were patched together and the commit landed at 03:52. The last server release had gone out at ~01:45 — **two hours before the commit existed.** Every generation for the next twelve hours ran the old prompt. `pnpm check` passed, the cross-layer contract check passed, the pre-push hook passed. Nothing was wrong with the code.

Two things make this specifically hard to notice:

- **The commit is the alibi.** "Both copies patched in lockstep" is what you'd write in the message, and it's true. Someone auditing later reads the diff, sees both files changed together, and concludes the surface is consistent — which it is, in the only place they're looking.
- **It splits your users by tier, so testing on the wrong account shows nothing.** The routing fork (native-direct vs. via-your-server) usually maps to an entitlement: bring-your-own-key users take the native path, subscribers take the server path. So the fix was live *immediately* for BYO users and *not at all* for subscribers. Whoever tests decides whether the bug exists. Here the dev account had no personal key, which is the only reason it surfaced at all.

**The mechanical tell, and it's better than reading handoff notes:** compare the deployment's timestamp to the commit's. `fly releases -a <app>` (or your platform's equivalent) against `git log -1 --format=%cd -- <server-dir>`. If the newest release predates the newest commit touching that directory, the deployed copy is stale — one command, no memory involved, and it answers the question for *every* duplicated-logic pair at once rather than per-feature.

**Don't debug the display layer first.** The natural first move when tagged output doesn't render is to suspect the renderer. Query the datastore instead and look at what was actually *written* — if the stored values have no tags in them, the problem is upstream of every line of UI code, and you've skipped the entire front-end investigation. In this incident that was one read-only query against a copy of the local DB, and it turned a display bug into a deploy bug in about a minute.


## The write-side variant: writing to the copy that loses

The variants above are about *reads* — a field that doesn't arrive, or arrives and erases. There's a write-side twin: **in a system where one copy is authoritative, a write to a non-authoritative copy is temporary, and it un-does itself later and somewhere else.**

Concretely (same project, same day): a dev tool backdated some timestamps by writing straight to local SQLite with raw SQL. It worked — the UI updated, the feature became testable. Then, minutes later and after an unrelated user action, the rows reverted. The mirror layer was **one-way, cloud → local**: it exists to write server-delivered rows into the local DB, and its own header said it does not push. So the local edit was never propagated, and the next time the server re-delivered those rows the original values came back.

What makes this expensive to diagnose:

- **It fails at a distance.** The bug surfaces after an unrelated action (anything that triggers a sync), so the write and the failure aren't adjacent in time or in the user's mental model. The reported symptom was "I clicked X and unrelated thing Y broke."
- **It looks like a reactivity bug.** Data that was on screen and then isn't reads as a stale-cache or re-render problem. It is worth checking whether the surface *re-queried* — if a full remount still shows the old state, the data genuinely changed and the UI is innocent. That single check redirects the whole investigation.
- **Dev and seed tooling is where it bites**, because that's the code most likely to reach for raw SQL and least likely to go through the app's write helpers. It's also the code nobody reviews.

The rule: **any write path must go through whatever keeps the copies in lockstep, including throwaway tooling.** If your `setThing()` helper writes local *and* mirrors, then a debug tool that writes only local isn't a shortcut, it's a different and broken operation. Put the dev-only function next to the real write functions so it inherits the same lockstep by proximity — not in the debug screen where it will be written as raw SQL.

A corollary worth checking before you mirror: **confirm the field is even writable from the client.** Server-authoritative columns are often absent from the write allowlist, so mirroring them silently no-ops and you get the same revert with an extra layer of confusion. Prefer changing a field you *are* allowed to write to achieve the same test condition.

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
- [`write-triggered-enforcement-blind-to-deletion.md`](./write-triggered-enforcement-blind-to-deletion.md) — the same blindness in a different axis: an enforcement mechanism that structurally cannot observe a whole class of change. "Deployed copy" and "deleted file" are two things an in-repo checker never sees.
- [`instrument-before-patching.md`](./instrument-before-patching.md) — both variants added here were diagnosed by finding the layer that could report the truth (a deployed-schema rejection, a one-way mirror's own header comment) rather than by guessing at fixes.
- [`local-sqlite-app-wide-change-signal.md`](./local-sqlite-app-wide-change-signal.md) — relevant to the write-side variant's red herring: when data vanishes after a navigation, check whether the surface actually re-queried before blaming reactivity.
