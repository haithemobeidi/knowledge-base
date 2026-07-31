---
stack: [typescript, zod, sqlite, sql, tauri]
kind: postmortem-playbook
last_verified: 2026-07-31
---

# Digit-led snake_case segments break regex case bridges — and a required Zod field turns that into "all my data is gone"

> Post-mortem of a Playmoir outage (2026-07-30): one new SQLite column named
> `playtime_2weeks_minutes` made the app report an EMPTY game library, a dead
> game-detail page, and a failed first-run scan — over a fully intact table.
> Total code at fault: one regex that predated the column by months, plus one
> required field in a Zod schema. Fixed by renaming the column.

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
- Know whether your row schemas are strip-mode or required-mode at the parse
  boundary, because that decides whether a key mismatch is a silent data hole
  or an app-wide empty state.
- A required-field ZodError whose `path` names your newest field, over a table
  you can prove is full, is a KEY-SHAPE mismatch, not missing data. Check the
  bridge before checking the database.

## Bonus trap from the same outage

After the rename, one machine kept validating against the OLD schema through a
full app restart — Vite's dep-optimizer cache (`node_modules/.vite`) had
pre-bundled the workspace package and survives restarts. See the "third stale
layer" section added to [[monorepo-stale-dist-zod-strip]].
