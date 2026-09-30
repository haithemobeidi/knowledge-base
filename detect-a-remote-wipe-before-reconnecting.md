---
stack: [sync, local-first, powersync, zod, typescript]
kind: pattern
last_verified: 2026-09-24
---

# A device that was closed during a cloud wipe must find out before it reconnects, or sync mirrors the empty cloud onto it

**One-liner:** in local-first sync, a user who wipes their cloud data from one device expects the other devices' local data to survive. A device that was *running* during the wipe can hear it and freeze. A device that was *closed* reconnects on its next boot and faithfully reshapes its replica to the now-empty cloud, deleting everything locally. The fix is a monotonic server stamp (`cloud_wiped_at`), written inside the wipe's own transaction, that every client compares **before** sync is allowed to connect. It also turned out one client couldn't see the stamp at all, because its schema silently stripped the field.

*Verified live 2026-09-24: the user wiped from the phone while the desktop was closed; on boot the desktop logged `[cloud-wipe] cloud wiped while this PC wasn't listening (…) — sync paused` and kept its data.*

## The mechanism

- **The server** stamps `users.cloud_wiped_at` inside the wipe transaction and sends it on every entitlement or snapshot read the client already makes at boot.
- **The client** keeps the last stamp it saw, **per account** (so signing into a different account never reads as a wipe of the first).
- **The check runs as a gate on the snapshot, before it is published**, because publishing is what lets sync connect. A check after the connect is a check after the drain.

The rules, first written for the Android client and then mirrored on desktop:

1. **Record the stamp before deciding.** A freeze the user resumes out of can't be re-triggered by the same wipe.
2. **First sight is never news.** A fresh install signing into an account wiped long ago opens working, not frozen.
3. **A wipe this device ordered is recorded, not announced.**
4. **On a newer stamp:** set the "sync paused" flag first (so every reconnect path stays down), then `disconnect()`, never `disconnectAndClear()`, so the local replica and the outbox survive. Tell the user in words.
5. **Resuming** accepts the cloud as it now is and forgets the remembered stamp, so the next sighting is a first sight.

Boot, wake and sign-in all connect only after the gated refresh, time-boxed (10 s). Review caught two races in the first build: sign-in could connect before the gate ran, and resume didn't record the current stamp.

**Accepted residual:** if the snapshot read fails or times out (offline), sync connects unchecked. A failed read proves nothing either way, and blocking sync on it would strand an offline-first app.

## The second bug: one client couldn't see the signal

The server had shipped the stamp, and Android read it. The desktop's snapshot schema was a plain Zod object, and **Zod strips unknown keys by default**. `cloudWipedAt` arrived and was silently dropped before any code could look at it. A safety signal added on the server is only live on the clients whose schema was updated to carry it. Audit every client when you add one.

## Related

- `tombstone-vs-hide-for-mirrored-data.md`: what a deletion should mean in a mirrored set.
- `monorepo-stale-dist-zod-strip.md`: the other way Zod's strip made a field vanish silently.
- `strict-schema-at-a-sync-boundary.md`: the strict-schema opposite, where an unknown field blocks the whole queue.
- `local-first-sync-with-d1.md`: the base sync patterns.
