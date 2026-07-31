---
stack: [typescript, zod, sqlite, sql, tauri]
kind: postmortem-playbook
last_verified: 2026-07-31
---

# Digit-led snake_case segments break regex case bridges — loudly if you're lucky, silently if you're not

> Two sightings, one week apart, same regex.
>
> **2026-07-30 (loud):** one new SQLite column named `playtime_2weeks_minutes`
> made the app report an EMPTY game library, a dead game-detail page, and a
> failed first-run scan — over a fully intact table. A required Zod field turned
> a key mismatch into an app-wide empty state. Diagnosable in an hour.
>
> **2026-07-31 (silent):** the months-old `intention_1…3` columns hit the same
> regex in a path with no row schema and `?? null` fallbacks. Nothing threw.
> Every backup restore quietly dropped six columns of user data and mirrored the
> blanks to the cloud. Found only by reading the code.
>
> The second one is the reason this article has a second half. **The loud
> failure is the lucky one.**

## The symptom

Every surface that lists games goes empty at once. The data is verifiably
present (query the DB file directly). Error surfaces that show raw errors
display a ZodError like:

```
{ "code": "invalid_type", "expected": "number", "received": "undefined",
  "path": [0, "playtime2WeeksMinutes"], "message": "Required" }
```

The path names a field you *just added*, on a row that *has* the column.

## The cause — two innocent pieces, one break

**Piece 1: a hand-rolled snake→camel bridge.** Apps that bypass an ORM's query
builder often remap SQL column names to code-style keys in one place:

```ts
function snakeToCamel(key: string): string {
  return key.replace(/_([a-z])/g, (_, ch) => ch.toUpperCase());
}
```

That regex only matches a LETTER after the underscore. A digit-led segment
passes through untouched:

- `playtime_minutes` → `playtimeMinutes` ✓
- `playtime_2weeks_minutes` → `playtime_2weeksMinutes` ✗ (underscore kept, no
  key in the schema matches)

There is no spelling of a digit-led segment that camelizes cleanly — capitalizing
`2` is a no-op, so even a "fixed" regex (`/_([a-z0-9])/g`) produces
`playtime2weeksMinutes`, whose casing then has to be hand-matched in the schema
and will surprise the next person. The segment naming is the problem, not the
regex.

**Piece 2: the field was REQUIRED in the row schema.** `z.number().int().nullable()`
is nullable but NOT optional — the key must exist. So every `SELECT *` +
`schema.parse(rows)` throws, and every caller's `catch` resolves to its empty
state. **The app fails closed, loudly-empty, everywhere at once** — which is at
least diagnosable. (Contrast the sibling failure in
[[monorepo-stale-dist-zod-strip]]: there the parse *succeeds* and strips the
column silently. Required = everything visibly breaks; strip-mode = data
quietly vanishes. Pick your poison, but know which one your boundary does.)

## The fix

1. **Rename the column to all-letter segments**: `playtime_two_weeks_minutes`
   → bridges to `playtimeTwoWeeksMinutes`, matching the schema naturally.
2. **Roll forward, never edit the applied migration.** The bad name had already
   run on real databases (migration N). Editing N's SQL in place would leave
   deployed DBs on the old column while fresh installs get the new one —
   divergence with no error. Ship migration N+1:
   `ALTER TABLE games RENAME COLUMN ... TO ...` (SQLite supports RENAME COLUMN
   since 3.25).

## The checklist (before adding any column)

- Grep for the case bridge (`snakeToCamel`, `/_([a-z])/`, `camelize`) and
  know its rules. If your project has one, **it is part of your naming
  convention** whether documented or not.
- Never start a snake_case segment with a digit. Spell it out (`two_weeks`,
  not `2weeks`) — this also survives every other tool that assumes
  letter-led segments (serde renames, GraphQL, ORMs).
- Know which of THREE modes each parse boundary is in, because that decides
  what a key mismatch does to you: **required-mode** (app-wide empty state,
  loud, diagnosable) → **strip-mode** (column vanishes silently, see
  [[monorepo-stale-dist-zod-strip]]) → **no schema + `?? default`** (data is
  dropped and the code still looks correct — the worst, and the one that took a
  second sighting to find).
- Grep for bare `SELECT *` anywhere the results cross a bridge. Queries that
  alias explicitly are patched, not fixed, and they hide the bug everywhere
  else.
- A required-field ZodError whose `path` names your newest field, over a table
  you can prove is full, is a KEY-SHAPE mismatch, not missing data. Check the
  bridge before checking the database.

## Second sighting, different failure mode: no schema + a fallback = silent data loss

Found 2026-07-31 in the same codebase, one day later, in a completely different
path. Same regex, same digit-led column — but this time nothing threw, nothing
went empty, and nobody would ever have noticed. **This is the variant worth
fearing.**

The columns were `intention_1 … intention_3` and `intention_1_done …`, which had
existed for months. The bridge mangles them exactly as you'd expect:

- `intention_1` → `intention_1` (unchanged — no letter after the underscore)
- `intention_1_done` → `intention_1Done` (a mongrel: only the `_d` converts)

**Why the app looked fine for months.** The normal read path aliased in SQL:

```sql
SELECT intention_1 AS intention1, intention_1_done AS intention1Done, ...
```

Explicit aliases bypass the bridge entirely, so every screen worked. The bug
lived only in a path that used a bare `SELECT *` — the backup exporter, which
runs rarely and whose output nobody eyeballs.

**Why it was silent rather than loud.** Unlike the outage above, this boundary
had no row schema to violate: the backup manifest was typed
`z.array(z.record(z.unknown()))`, deliberately permissive. So the mangled keys
sailed through, and the *importer* read the names it expected:

```ts
e.intention1 ?? null      // undefined -> null
e.intention1Done ?? 0     // undefined -> 0
```

The `??` fallbacks are the trap. They exist to tolerate missing optional data,
and they cheerfully absorb a key-shape bug as if it were absent data. **Every
restore silently dropped all six columns** — every goal, every side quest, every
completion state — and then mirrored those blanks to the cloud, propagating the
loss to the user's other devices. Restored backups looked plausible: notes,
locations, milestones and screenshots all intact.

### The generalisable lessons

- **Explicit aliases hide bridge bugs, they don't fix them.** If some queries
  alias and others use `SELECT *`, your bridge is only exercised where you
  happened not to alias. Aliasing is a per-query patch masquerading as a fix —
  grep for bare `SELECT *` and treat each one as an untested bridge call.
- **A permissive schema is a bridge bug's best friend.** The "fails loudly"
  behaviour above is a *feature*: it required a strict schema at the boundary.
  Wherever you deliberately loosen validation (import/export, migrations,
  telemetry, anything handling foreign or historical shapes), you have also
  removed the thing that would have caught a key mismatch.
- **`?? default` at a deserialisation boundary converts bugs into data loss.**
  It cannot distinguish "the producer never wrote this" from "the producer wrote
  it under another name." If a field is required-in-practice, assert it rather
  than defaulting it — or at minimum, log when the default fires.
- **Bugs that reach a FILE FORMAT need a two-sided fix.** Repairing the writer
  is not enough, because every file already on disk carries the broken shape.
  The fix here aliased the six columns in the export *and* made the import read
  both spellings (`e.intention1 ?? e.intention_1`). Drop the reader half and you
  fix new backups while every existing one still restores empty — arguably worse,
  since users believe they're covered.
- **Aliasing on top of `*` beats replacing it.** `SELECT *, intention_1 AS
  intention1, …` keeps future columns flowing automatically *and* means a
  newly-written file restores correctly on an older build.

### How to sweep for it

Bound the blast radius with one grep — you only care about columns with a digit
after an underscore:

```bash
grep -oE "'[a-z_]*_[0-9][a-z_]*'" path/to/schema.ts | sort -u
```

If that returns nothing, your bridge is safe by construction. If it returns
something, check every bare `SELECT *` and every `?? default` that consumes
those rows. In the case above it returned exactly six names, all of them the
affected ones — which turned "audit the whole app" into "read two functions."

## Bonus trap from the same outage

After the rename, one machine kept validating against the OLD schema through a
full app restart — Vite's dep-optimizer cache (`node_modules/.vite`) had
pre-bundled the workspace package and survives restarts. See the "third stale
layer" section added to [[monorepo-stale-dist-zod-strip]].
