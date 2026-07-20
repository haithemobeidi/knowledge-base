---
stack: [zod, sql, typescript, graphql]
kind: gotcha
last_verified: 2026-07-08
---

# One shared parse schema, many row-producers — a centralized helper isn't enough

**One-liner:** when several independent queries (or resolvers, or handlers) each produce their own row shape but all get validated by ONE shared schema, adding a required field to that schema does not automatically make every producer emit it. This is a same-repo, same-commit flavor of schema drift — no staleness, no separate system, just N places that build a row and one schema that all of them feed. It recurred **twice** in the same codebase, in the same shape, because the fix the first time (extract a shared column-list helper) only protects the call sites that actually adopt it.

## The trap, concretely

`journalEntrySelectSchema` (a Zod schema) gained a required field (`uuid: z.string().nullable()`) during a UUID migration. Two SQL projections fed rows into `.parse(journalEntrySelectSchema)`:

```ts
// queries.ts — the CENTRALIZED helper, extracted after the first time this bug happened
const SESSION_ENTRY_COLUMNS = `
  id, uuid, game_id AS gameId, notes,
  intention_1 AS intention1, /* ...more columns... */
  created_at AS createdAt, updated_at AS updatedAt
`;
// this one got updated when `uuid` was added — it's the ONE place the column list lives
```

```tsx
// GameDetail.tsx — a SECOND, independent inline SELECT that never adopted the helper
const rows = await db.select(`SELECT id, game_id AS gameId, notes, /* no uuid */ ...
  FROM journal_entries WHERE game_id = $1 ...`);
z.array(journalEntrySelectSchema).parse(rows); // throws: uuid is required but missing
```

Only the centralized helper's projection was updated. The inline one wasn't — because nothing forced `GameDetail.tsx` to use the helper instead of writing its own `SELECT`. Zod threw on every row from the inline site. The surrounding code had a silent `catch {}`, so the array quietly stayed `[]`. The UI sections gated on `entries.length > 0` silently never rendered. Meanwhile a completely different part of the same screen kept working, because it read from a *different* schema/query pair — so the bug presented as "this one panel is empty," not "the schema/projection contract broke," and took real debugging time to trace back to a one-line projection gap.

## The general shape

Any time you have:
- **One shared validation schema** (Zod, io-ts, a GraphQL type, a Pydantic model) that multiple code paths validate rows against, AND
- **More than one producer** of rows for that schema (multiple SQL queries, multiple resolvers, multiple API handlers)

...you have this exposure. Adding a required field to the schema is a **type-level** change, but the producers are often untyped strings (raw SQL) or otherwise not statically checked against the schema's shape — so the compiler doesn't catch a producer that's now short a field. The mismatch only surfaces at runtime, at the `.parse()` call, and only for the producer(s) that didn't get updated.

## Why "extract a shared helper" only half-fixes it

Playmoir already hit this once and extracted `SESSION_ENTRY_COLUMNS` specifically to centralize the column list. That worked for every call site that imports and uses the helper. It did **nothing** to stop a later call site from writing its own inline `SELECT` instead — which is exactly what happened. A centralized helper is opt-in; nothing enforced its use.

## Mitigation menu (pick based on how much you want to spend)

1. **Procedural (free, relies on memory):** when you add a required field to a shared schema, grep every `.parse(<schemaName>)` call site in the codebase and manually verify each upstream projection includes the new column. Cheap, works, but only as reliable as remembering to do it.
2. **Structural — one helper per table, enforced by review/grep:** export exactly one "these are the columns" helper per table, and treat any *other* inline `SELECT` targeting that table as a review red flag. A one-line CI grep (`rg 'FROM journal_entries' --files-without-match 'SESSION_ENTRY_COLUMNS'`) can flag new inline SELECTs against a table that's supposed to only be queried through its helper.
3. **Structural, stronger — derive the SELECT list FROM the schema at runtime:** instead of a helper that's a second hand-maintained copy of the field list, generate it from the schema itself, e.g. `Object.keys(schema.shape).map(camelToSnake).join(', ')`. Now there is only **one** place the field list is ever written down — the schema — and every query that spreads the derived list picks up a new field automatically. This eliminates the "two places to keep in sync" problem instead of just centralizing it into a helper a second caller can still bypass.
4. **Defensive, always do this regardless of the above:** never let a `.parse()` failure at a data-loading boundary disappear into a silent `catch {}`. Log it at minimum. The reason this bug cost real debugging time wasn't the missing column — it was that the failure mode was "empty state," not "visible error." A logged parse failure turns an invisible bug into an actionable stack trace the moment it happens.

## Relationship to the drift-guard pattern

This is a sibling of [`n-copies-of-truth-drift-guard.md`](./n-copies-of-truth-drift-guard.md) but a different flavor: that lesson is about copies of a schema spread across **independent systems** (DB, sync layer, client, server) that go stale relative to each other over time. This one is about copies **inside the same repo, same commit** — multiple query sites that happen to feed one shared type, where nothing but convention keeps them aligned. Same root cause (one conceptual schema, N independent producers, silent-by-default validation), different blast radius (cross-system vs. cross-call-site).

---
*Captured from Playmoir's journal-entries UUID migration bug (fixed commit `f814635`, 2026-05-17) — noted in the codebase's own bug log as "the second drift bug of this exact shape."*
