---
stack: [local-first, sync, powersync, sqlite, dev-tooling, reliability]
kind: gotcha
last_verified: 2026-07-29
---

# A local-only dev fixture silently reverts under a sync engine that owns the same columns

**One-liner:** your "seed some test data" / "backdate this record" debug button writes to the local database, the UI renders it, and a few seconds later it evaporates — because a server-authoritative sync engine upserts the real row back down on its next tick; the giveaway is that it **partially** reverts (the columns the server owns snap back, the ones it doesn't survive), and the guard you already wrote to prevent this probably guards a different sync path than the one doing the damage.

## Why this bites specifically in local-first apps

Dev tooling almost always predates the sync layer. When the app was local-only, "UPDATE the row, reload, look at it" was a complete and durable operation. Then sync lands, the server becomes authoritative for some columns, and every one of those debug helpers quietly becomes a write that gets rolled back — with no error, no log line, and no test failure, because nothing about a fixture asserts that it *stayed*.

The fixture still "works" in the sense that the write succeeds. It just doesn't persist.

## The symptom, precisely

Not "it doesn't work." It's:

1. Click the debug button. It reports success.
2. The app reloads and the UI shows exactly what you expected.
3. Within seconds — often before you've finished reading the screen — the data reverts and the UI empties.

If you're not watching closely you'll report this as "it flashed and disappeared," and start looking at your render logic. The render logic is fine.

## The diagnostic that identifies it in one query: partial revert

This is the tell, and it's what separates this from a UI bug, a race, or a bad query.

Dump the state *after* it reverts and compare against what the fixture wrote. You will find a split:

| What the fixture wrote | State after revert | Who owns it |
|---|---|---|
| `journal_entries.created_at` shifted back 16 days | **still 16 days back** | client |
| `games.last_played_at` set to 16 days ago | **back to 2 hours ago** | server |
| `games.status` forced to `'playing'` | **back to `NULL`** | server |

A UI bug does not revert three columns and leave a fourth. **A clean split along "which side is authoritative for this column" is proof of the mechanism**, and it also hands you the fix, because it tells you exactly which writes need help and which don't.

Concretely, the offending path looks like this — an ordinary sync-down that upserts the whole row:

```sql
-- runs on every sync tick, from the server's copy
INSERT INTO games (uuid, name, last_played_at, status, ...)
VALUES (...)
ON CONFLICT(uuid) DO UPDATE SET last_played_at = excluded.last_played_at,
                                status         = excluded.status, ...
```

Nothing is wrong with that statement. It is doing its job. Your fixture just isn't part of the conversation.

## The trap: a guard that names the right intent and the wrong mechanism

Here's the part that cost the most time, and it generalises well beyond sync.

The codebase already had a flag for exactly this problem:

```ts
/** Debug-only flag set by the "simulate stale data" button. While truthy,
 *  auto-sync is suppressed so the backdated timestamp doesn't get
 *  overwritten by the real value on the next focus event. */
export const SIMULATE_KEY = 'simulate-active';
```

Read that comment. It states the exact failure. Someone had already hit this, understood it, and written a guard.

The guard suppressed **the focus-triggered library sync** — a client-initiated pull that fires when the window regains focus. The thing actually reverting the data was **the sync engine's down-stream write**, a completely different code path that the flag never touched.

So the flag was real, correctly named, correctly documented, and irrelevant. And it was *worse* than having no flag at all, because reading it convinces you the case is handled and sends you looking somewhere else.

> **The generalisable rule:** when a guard exists for the symptom you're seeing and the symptom is happening anyway, do not assume the guard is buggy. Check whether it guards the mechanism you're actually facing. "There's a flag for that" is a hypothesis, not a finding.

## Fixes, in order of how much they cost

**1. Mirror the fixture write to the server.** If your client is already allowed to patch that column, the fix is one call — write locally *and* push the same value up, so the next sync-down agrees with you instead of correcting you:

```ts
await db.execute("UPDATE games SET status = 'playing' WHERE id = $1", [id]);
await patchRowInCloud(id, { status: 'playing' });   // <- the whole fix
```

Check whether a *working* fixture elsewhere in the codebase already does this. Ours did: a different debug tool had the mirror call and a comment reading "so the next down-sync agrees instead of reverting us." One helper had learned the lesson and the other hadn't.

**2. Accept that some columns can't be mirrored, and make the fixture not need them.** Not every column is client-patchable. If a server-side integration owns it (a storefront's "last played" timestamp, a billing system's plan field), a client PATCH is either rejected by your allowlist or accepted and then clobbered by the next integration run. In that case, change what the *feature* reads while the fixture is active:

```ts
// Normally: the later of a logged session and the storefront's timestamp.
// While simulating: the session timestamp alone — the only half a local
// fixture can make stick, because the other is server-owned.
const touched = simulating
  ? 'IFNULL(entry.created_at, 0)'
  : 'MAX(IFNULL(entry.created_at,0), IFNULL(g.last_played_at,0))';
```

Be honest that this puts a dev-only branch inside a production query. It is a wart. It's justified when the alternative is a fixture layer bigger than the feature under test — but write down *why*, because the next person will otherwise delete it as debug cruft, and one such branch is a special case while two is a pattern that needs a real seam.

**3. Build a fixture layer sync doesn't own.** A dev-only offline mode, a seeded local-only account, or a test double for the sync client. Correct, and usually more work than the thing you're testing.

## The prevention

**Any dev helper that writes to a synced table should be treated as production code with respect to the sync contract.** Practically:

- When you add sync to an app that has debug tooling, audit that tooling. It won't announce that it broke.
- Have fixtures assert persistence, not just the write — re-read after a sync tick, not immediately.
- Put the reason in a comment at the fixture, naming the sync path, not just "don't remove this."

## Related

- [powersync-steam-backend-architecture.md](./powersync-steam-backend-architecture.md) — the architecture this shows up in: server-authoritative rows streamed down over a local SQLite mirror.
- [local-first-sync-with-d1.md](./local-first-sync-with-d1.md) — the general local-first sync shape.
- [n-copies-of-truth-drift-guard.md](./n-copies-of-truth-drift-guard.md) — the same family of bug: two places that must agree, only one of which you edited.
- [instrument-before-patching.md](./instrument-before-patching.md) — dumping the post-revert state instead of theorising is what turns this from a week into an hour.
