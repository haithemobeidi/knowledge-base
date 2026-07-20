---
stack: [sync, offline-first, powersync, distributed-systems]
kind: pattern
last_verified: 2026-07-20
---

# A tombstone is a claim of nonexistence — don't use one for data you don't own

**One-liner:** in any sync system with a trusted central server, a soft-delete tombstone means *"this record should not exist anywhere."* That claim is simply **false** for rows mirrored/re-derived from an external authoritative source (a Steam library, a GitHub org sync, a calendar integration, an imported CSV you re-import periodically) that the server deliberately keeps live. Soft-deleting those rows locally starts an unwinnable fight against the sync engine, which will faithfully re-send a row it's been told is still current — because that's the sync engine working correctly, not a bug in it. The fix is a **local-only, non-syncing "hidden" flag**, categorically distinct from delete.

## The trap, generalized

You have two kinds of rows that both currently go through the same "soft-delete" code path:

1. **Genuine user data** (a note, a manual entry, an uploaded file) — when the user deletes it, it should be gone everywhere. A soft-delete tombstone that syncs is exactly correct here: it's a real claim, and the server has a counterpart for it (the row IS actually being removed server-side too).
2. **A mirror/projection of an external source** (installed Steam games, synced calendar events, an imported repo list) — the server *keeps this row live on purpose*, because it's re-derivable and the external source is still the truth. If you locally soft-delete this row (e.g., "user disconnected this integration"), you've created a tombstone whose claim is false: the server row is live and will keep re-arriving. Every re-arrival looks like "resurrection," gets re-deleted, re-arrives again — a churn loop that isn't a bug in either the delete code or the sync engine; it's the wrong operation applied to the wrong kind of row.

**The tell:** a delete is only durable if it has a counterpart at the source of truth. If your delete is intentionally NOT mirrored to the authoritative source (because you want to keep syncing that data for everyone else, or because reconnecting should bring it right back), you don't have a delete — you have a **visibility** change, and visibility is local, not synced.

## What actually works (validated across systems with a trusted central server)

Comparable systems handle "hide, but don't destroy, a re-derivable thing" the same way, independent of their sync engine:

- **Linear** separates **Archive** (reversible, keeps the row, syncs the archived state) from **Delete** (destroys the row) — disconnect/hide is semantically an archive, never a delete.
- **Ditto** ships `isArchived` as an explicit soft-delete-flag-as-filter, distinct from its actual tombstone-producing `DELETE` — "a way to flag data as inactive while retaining it."
- **PowerSync** (and similar sync engines) support **local-only columns/tables** — writes to them never produce a sync/CRUD entry, so a local "hidden" flag never leaves the device and never collides with the live server row.

**The fix, concretely:** keep the synced/mirrored rows exactly as delivered (don't touch them). Add a separate **local-only, non-syncing** predicate — a local-only column, a local-only side table keyed by the mirrored row's id, or a single device-local boolean if it's an all-or-nothing integration — and filter your UI queries by it. Disconnecting = flip the local flag. Reconnecting = flip it back; the rows are already there, nothing re-imports. No tombstone is created, so there is nothing for the sync engine to "incorrectly" restore — the bug class disappears rather than getting mitigated.

**Only reach for an actual destructive delete** if disconnect is genuinely supposed to wipe the data (lose any local annotations on it) — and in that case, delete it server-side too (stop re-deriving it), so nothing re-inserts. That's a heavier, different feature ("disconnect and forget") than "disconnect and hide" — don't default to it just because delete-code already exists.

## Two related rules for genuine deletes (the case where soft-delete IS correct)

For rows where soft-delete really is the right model, two failure modes recur across every mature sync system's design docs (WatermelonDB, RxDB, Couchbase, Cassandra, Ditto):

1. **A write-through/mirror must never re-insert an already-tombstoned row.** When an incoming synced row carries a delete marker, treat it as "ensure locally absent," never "insert, then let garbage collection clean it up later." The insert-then-GC pattern is itself an insert→GC→re-insert churn engine if timing lines up wrong.
   - **Confirmed in production (Playmoir BUG-52, 2026-07-18):** every write-through in the family inserted an incoming tombstoned row unconditionally, even when no local row existed for it. Two distinct symptoms from one root cause: a local "delete forever" resurrected as a ghost seconds later (the cloud tombstone streams down forever — no server-side tombstone GC existed yet), and a *fresh* device imported ghosts for rows it never had at all (e.g. refund-pruned rows it was never sent as live in the first place). The concrete guard: `if (incoming.deleted_at) { if (no local row exists for this id) skip; }` — keyed by whatever the entity's natural id is (not the sync engine's own row id) — applied identically across every entity family (games, manual entries, journal entries) once one family (screenshots/audio) was found to already have it correctly. A tombstone for something you've never had is a no-op, full stop; it should never be the trigger for a first INSERT.
2. **Never clear a local tombstone just because the server's copy currently lacks one.** That's an unconditional "server wins," which is actually "server is ignorant" during the window where your delete hasn't uploaded yet — a classic resurrection bug (add-wins-by-accident). Guard it: only clear the local tombstone once the delete is server-acknowledged, OR the incoming row's `updated_at` is causally newer than your local `deleted_at` (a genuine later revive, not sync catching up).
3. **A fixed wall-clock GC timer on tombstones (e.g. "purge after 30 days") is resurrection-unsafe** for any client that can be offline longer than the timer. Every system that documents this (Cassandra's `gc_grace_seconds`, Ditto's TTL, Couchbase's purge interval) attaches an explicit resurrection warning to a fixed timer. The safe version ties purge to **proof of replication** (a high-water-mark cursor the server tracks per device, or an "await replication" check before purging), not a bare clock. With a trusted central server, this is easy: the server already knows each device's last-synced position, so it can prove a tombstone has been seen everywhere before hard-deleting it — no CRDT version-vector machinery required, that complexity is only necessary for genuinely peer-to-peer systems with no central authority.

## When NOT to overthink this

If you have a trusted central server (not peer-to-peer), you do not need version vectors, HLCs, or CRDT causal-stability tracking to get this right — that machinery exists for systems (Yjs, Automerge) that have no central authority to lean on. A central-server topology can just ask the server "has every device passed this point yet?" and that answer is sufficient. Reach for heavier conflict resolution (Hybrid Logical Clocks, `(updated_at, device_id)` tiebreaks) only if you actually observe clock-skew-driven ordering bugs in practice — not preemptively.

## Related

- [`local-first-sync-with-d1.md`](./local-first-sync-with-d1.md) — the sibling lesson on tombstones-with-matched-retention for **genuine** deletes; this lesson is specifically about the case that pattern does NOT cover (re-derivable/mirrored data).
- [`n-copies-of-truth-drift-guard.md`](./n-copies-of-truth-drift-guard.md) — a different sync-correctness failure mode (schema shape drift) from the same broader "local-first sync is subtle" family.

---
*Distilled from a 2026-07-06 research pass (13 named systems compared: PowerSync, ElectricSQL, Replicache/Zero, WatermelonDB, RxDB, Automerge, Yjs, Turso, Linear, Figma, Ditto, CouchDB, Couchbase) commissioned after a real production bug where "disconnect Steam" soft-deleted re-derivable library rows that PowerSync correctly kept re-sending.*
