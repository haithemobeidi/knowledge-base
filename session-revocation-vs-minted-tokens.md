---
stack: [auth, sessions, jwt, powersync, s3, presigned-urls, local-first]
kind: gotcha
last_verified: 2026-07-23
---

# "Sign out everywhere" doesn't reach the short-lived tokens you minted from the session

## Symptom

You build opaque, server-side sessions (a random token, hashed in a `sessions`
table, revocable by setting `revoked_at`). Revocation works: hit
`/auth/signout-all`, run one `UPDATE ... WHERE user_id = $1`, and the next
request carrying that session gets a 401. You ship "sign out everywhere" as a
lost-/stolen-device kill switch and call it done.

Then you notice a device whose session you just revoked can KEEP SYNCING for a
few more minutes — or keep pulling attachments. The takeover kill switch has a
hole you didn't design for.

## Cause

Your revocable session is not the only credential in play. Anything you MINT
from that session — and hand to a subsystem that verifies it WITHOUT calling
back to your session store — outlives the revocation by its own TTL:

- **Sync-service JWTs (PowerSync / Firebase-style).** The client exchanges its
  session for a short-lived RS256 JWT that the sync service verifies against
  your JWKS. JWKS verification is stateless by design — the service never phones
  home — so a JWT already in the client's hand stays valid until it expires.
  There is no revocation list in the JWKS model.
- **S3 / R2 presigned URLs.** Signed with a TTL; the object store honors the
  signature until it expires, with zero knowledge of your session state.
- **Any bearer access token** in an access+refresh scheme: the access token is
  self-contained and valid till expiry; only the refresh is gated.

So "revoke all sessions" instantly kills every path that RE-CHECKS the session
per request, but leaves a tail equal to the longest-lived minted token.

## Fix

Two parts: make the part that MATTERS have no tail, and make the unavoidable
tail as short as the design allows.

1. **Route high-value actions through the revocable session, not a minted
   token.** In our app, WRITES (CRUD upload) and MINTING NEW tokens both
   authenticate with the session token and do a live store lookup per request.
   So the instant you revoke: writes 401, and no new sync/presign tokens can be
   minted. The account-takeover vector (modifying data) closes with NO window —
   only read-via-already-minted-token has a tail.
2. **Keep minted-token TTLs short — that TTL _is_ your revocation latency.**
   PowerSync's recommended floor for asymmetric keys is ~5 min; keep presigned
   URLs similar. That number is the max time a revoked device keeps read access.
3. **Don't reach for a real-time "force logout" push unless the tail sits on a
   high-value action.** We considered a server→device push and rejected it: it
   would only shave the read-only sync tail (on a device that already holds the
   local-first copy anyway), while the write/account vector is already instant.
   Per-request server checks beat a push for the thing that matters.
4. **Name what you can't reach as accepted, not a bug.** A local-first app's
   data already on the physical stolen device is unreachable — no server action
   remote-wipes a device you don't hold. Put that in the threat model explicitly.

## Notes

- The load-bearing mental model: **"signed out" is enforced per-request
  server-side, not a client state.** A stolen client can still DISPLAY "signed
  in" and be completely inert, because every action re-checks. That's the
  reassuring half — UI lag on the victim's other device doesn't mean the
  attacker kept capability.
- The client "sign out everywhere" should clear locally ONLY on a confirmed
  server revoke; on a failed/uncertain call, keep the local session and warn +
  offer retry. Silently clearing only the local device while the others stay
  live inverts the entire point of the feature.
- Related: [[db-backed-auth-503-not-401]] (the same opaque-session store must
  answer 503, not 401, on an outage) and [[r2-presigned-put-size-limits]].
- Verified 2026-07-23: cross-device revoke confirmed — writes 401 instantly, the
  sync stream stopped within the ~5-min JWT TTL.
