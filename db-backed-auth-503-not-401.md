---
stack: [node, postgres, http-api, auth, local-first]
kind: gotcha
last_verified: 2026-07-23
---

# DB-backed session auth: a store outage must not answer 401, or every client "gets signed out" at once

## Symptom

You migrate session verification from something stateless (a signed JWT checked
in-process) to something stateful (an opaque token looked up in a sessions
table — the Lucia / Copenhagen-Book model). Everything works in testing. Then
the database has a blip — a failover, a connection-pool exhaustion, a deploy
hiccup — and **every signed-in client simultaneously reports "session expired,
please sign in again."** Users re-authenticate (or worse, can't, because the
store is still down), support lights up, and the incident reads like a mass
credential wipe when nothing about the sessions actually changed.

## Cause

Stateless verification has a one-dimensional error space: the token is either
valid or it isn't. A signature check cannot *transiently* fail, so mapping
"verify threw" → `401 Unauthorized` is safe, and most codebases write exactly
that:

```js
try {
  ctx.userId = await verifySession(token);
} catch {
  return unauthorized(); // fine for a JWT — fatal once verify can FAIL TRANSIENTLY
}
```

The moment verification involves I/O, the error space gains a second axis:
**"this credential is bad" vs "I currently cannot know."** The catch-all keeps
compiling and keeps passing every test you're likely to write (nobody unit-tests
"Postgres is down"), but it now converts infrastructure weather into an
authentication verdict. Clients dutifully do what a 401 means: they discard the
session state and flip to signed-out UX.

The blast radius is worst in local-first apps, where the client deliberately
treats a stored session as durable truth: one bogus 401 doesn't just show a
banner, it tears down sync state the user then has to rebuild by re-authing.

## Fix

Split the two failure axes at the lowest layer and preserve the split through
every caller:

1. **In the verifier**, tag store failures so callers can distinguish them:

```js
export async function verifySession(token) {
  let rows;
  try {
    ({ rows } = await pool.query(SELECT_LIVE_SESSION, [hash(token)]));
  } catch (e) {
    const err = new Error(`session store unavailable: ${e.message}`);
    err.transient = true; // infrastructure, not a verdict
    throw err;
  }
  if (rows.length === 0) throw new Error('unknown, expired, or revoked session');
  return rows[0].user_id;
}
```

2. **In every HTTP-facing caller** (middleware, per-route guards, write-path
   authenticators), map the tag: transient → `503` (or let it bubble to the
   generic `500`), everything else → `401`. Audit ALL of them — the copy-pasted
   inline guard someone wrote before the middleware existed is the one that
   will keep collapsing both cases.

3. **In the client**, make session validity a tri-state, not a boolean:
   `valid | invalid | unreachable`. Only a literal `401` means the session is
   dead; network errors and 5xx mean "keep trusting the stored session and try
   again later." A local-first app should stay quiet and fully functional
   through `unreachable`.

```ts
if (res.ok) return 'valid';
if (res.status === 401) return 'invalid';   // the ONLY signed-out signal
return 'unreachable';                        // 5xx/network: trust the stored session
```

The server and client halves are one contract: the server promising "401 is a
verdict, never weather" is what makes the client's `invalid` branch safe to act
on destructively.

## Notes

- This failure mode is invisible until the first real DB blip in production —
  which is exactly when you least want a novel incident. It was caught at
  design time here only because the client tri-state already existed (a prior
  bug fix) and the server migration had to answer "which status keeps the
  tri-state honest?"
- Same reasoning applies to any auth dependency that can transiently fail:
  Redis session caches, OIDC introspection endpoints, entitlement lookups that
  gate requests. If the check does I/O, "check failed" has two meanings and
  needs two status codes.
- Corollary for the migration itself: when you cut over from JWTs to the store,
  old tokens missing the lookup SHOULD 401 (that's a real verdict — the
  credential is dead by design). The one-time forced re-sign-in is the honest
  path; keeping a legacy-accept branch "to be gentle" leaves two verifiers
  alive indefinitely.
