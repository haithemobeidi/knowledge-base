---
stack: [pnpm-monorepo, zod, vite, tauri, powersync]
kind: postmortem-playbook
last_verified: 2026-07-04
---

# Stale workspace `dist/` + Zod strip = data that vanishes with zero errors — and the stacked-bug post-mortem that found it

> Post-mortem of a cross-device sync bug (Playmoir BUG-48, 2026-07-03 → 07-04) that
> burned two full sessions because it was actually TWO independent bugs stacked in
> the same pipeline, each perfectly masking the other. The second bug is a
> monorepo trap that will recur anywhere a workspace package ships compiled
> output: **git said the code was current, but the runtime was importing a
> 7-day-old build artifact, and a Zod parse boundary silently deleted the new
> column from every row.** No error, no warning, no amount of restarting fixes it.

## The symptom

A new DB column (`session_summary`, an AI-generated per-session summary) synced
cloud → device B, but device B's UI showed the raw fallback text. Device A
(which generated the data) displayed fine. Every obvious check passed on
device B: right branch, right commit, clean tree, fresh dev-server restarts,
data verified present in the local SQLite file.

## The two stacked bugs

1. **Server (real, found first):** PowerSync sync rules are FROZEN at deploy
   time — a column added to Postgres after the last rules deploy is never
   streamed, and redeploying byte-identical `SELECT *` rules is a no-op that
   doesn't re-replicate. Fix: explicit column lists + real redeploy.
   (Lesson already in `powersync-steam-backend-architecture.md` territory;
   the yaml now carries a 5-layer migration-lockstep header.)
2. **Client (invisible, found a day later):** the frontend imports its shared
   types package (`@playmoir/core`) via `"exports": "./dist/index.js"` — the
   **compiled artifact, not source**. Device B's `dist/` was last compiled
   3 days before the column was added to the Zod schema. Zod object schemas
   **strip unknown keys by default**, so `z.array(rowSchema).parse(rows)`
   silently deleted the new field from every row between SQLite and React.
   Fix: `pnpm --filter @playmoir/core build` + clear `node_modules/.vite` +
   restart dev.

Each bug masked the other: while bug 1 was live, no data reached device B, so
bug 2 was unobservable. Once bug 1 was fixed, the data arrived — but bug 2 ate
it at render time, which made the (correct!) server fix look like a failure and
sent the investigation back through already-exonerated server levers.

## Lesson 1 — "git clean at the right commit" does NOT mean "runtime runs that code"

If any workspace package resolves through `dist/`, the runtime code is only as
fresh as the last **build**, not the last **pull**. `git status` / `git log`
cannot see this. Neither can restarting the dev server — Vite happily re-imports
the same stale artifact forever (and may ALSO cache a pre-bundle of it in
`node_modules/.vite`, so clear that too when in doubt).

**Checks when a feature works on machine A but not machine B:**
- `grep` the **built artifact** (not the source) for the new symbol:
  `grep sessionSummary packages/core/dist/db/types.js` → 0 matches = smoking gun.
- Compare the artifact's mtime against the date the schema last changed.
- Machine A is your control: run the identical checks there first, so you know
  what "healthy" looks like.

**Structural fixes (pick per project):**
- Make the dev task depend on building workspace deps (turbo `dependsOn: ["^build"]`)
  or run the package's build in watch mode alongside dev.
- Or point the package's `exports` at source for internal dev consumption
  (custom condition / `publishConfig`), so there is no stale artifact to serve.
- A CI/boot drift-guard that compares schema layers catches this class wholesale.

## Lesson 2 — a Zod parse boundary is also a data FILTER

Default Zod (`.strip()` mode) deletes unknown keys on parse. That's usually the
safe choice — but it means a schema-version mismatch doesn't error, it silently
narrows your data. When a field exists in the DB but is `undefined` in the UI,
suspect **the schema version the runtime actually loaded**, before suspecting
the query. (The same applies to any codegen'd validator/serializer: protobuf,
OpenAPI clients, drizzle snapshots.)

## Lesson 3 — stacked bugs: when a verified fix "doesn't work," verify STAGES, not the endpoint

The killer anti-pattern: fix bug 1, re-test the END-TO-END symptom, see it still
broken, conclude the fix failed, keep digging in the same (now-healthy) layer.

Instead, decompose the pipeline and find the FIRST stage where healthy and
broken machines diverge. Ours was:
`cloud Postgres → server sync stream → client replica → local SQLite → query+parse → rendered pixels`

Stage checks that cracked it:
- **Impersonate a fresh client at the protocol level.** We minted a real client
  JWT with the server's signing key and `curl`ed the PowerSync `/sync/stream`
  endpoint directly — ground truth of what the server sends, no dashboard, no
  second device. (Generalizes: hit the sync/API endpoint as a new client and
  read raw payloads.)
- **Read the broken machine's DB file directly** (SQLite `mode=ro` URI works
  fine while the app runs, WAL included).
- **Only then** touch the app layer — by now the fault is boxed into two stages.

Corollary: with the endpoint-only test, N stacked bugs cost O(N × whole-pipeline
investigations). With stage checks, one pass finds them all.

## Lesson 4 — two-machine debugging with a second agent + a committed runbook

Device B was physically elsewhere with a weaker agent (Sonnet) driving it. What
worked extremely well:

- Commit a **runbook file** to the repo; the remote agent pulls and follows it.
- Open with hard **rules**: read-only, no fixes, no installs, exact allowed
  commands, "if anything errors, STOP and report verbatim."
- Make the diagnostic script **self-classifying**: it prints `CASE: A/B/C/…`
  with a one-line meaning, so the remote agent exercises zero judgment and
  can't misread the data. Results come back as a committed report file.
- Test the script on the healthy machine first (it must print the "healthy"
  case there) before shipping it to the broken one.

## Small verification gotchas that cost real time

- `sum(col IS NOT NULL)` counts **empty strings** as present. UIs typically
  treat `''` as absent (`value?.trim() || fallback`). Verify **content**
  (`length(trim(col)) > 0` + sample the actual text), not just null-ness.
- `grep -c` counts **lines**, not occurrences — NDJSON payloads are giant
  single lines; 1 match may mean 65 values. Parse before concluding.
- "Fix applied" ≠ "fix confirmed": our final server remedy WAS correct, but was
  verified only minutes after applying, before the client could sync — logging
  it as failed. Give propagation time a seat in the verdict.
