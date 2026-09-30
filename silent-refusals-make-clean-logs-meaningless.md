---
stack: [node, http, sync, observability, android, any]
kind: gotcha
last_verified: 2026-09-26
---

# A refusal nobody logs or shows: clean server logs are not evidence that anything succeeded

**One-liner:** three separate failures in one app had the same shape. Something upstream said no (a rate limiter's 429, Steam's 403, a client timeout shorter than the route), and the refusal was either never logged or swallowed "by design". Each time the user saw a vague or empty result and the logs looked clean, so the first hypotheses were wrong. Log or count every refusal where it happens, tell the user the one-sentence reason when there is one, and never read an absence of log lines as success.

## 1. The rate limiter that returns 429 without a word (Playmoir, 2026-09-21 → 09-24)

- **Symptom:** a demo seeder pushing ~275 screenshots, and later a copy-up after a cloud wipe (~240), each lost about half. The client said "some uploads didn't finish" with no cause; the server logs showed nothing.
- **Why nothing:** the presign route answered `429 {error: 'rate limited'}` past 120/min per account **without logging**, while the neighbouring quota refusal *did* log. The uploads themselves go straight from the client to object storage (R2), so they never touch the app server. The only server-visible step failed silently.
- **Fix, two rounds:** round 1 paced only the seeder (one upload per 600 ms, under the cap). Round 2, after the wipe copy-up hit the same wall, gave **every caller one shared pace** plus a 429 retry at 20/40/60 s (the server window is 60 s), then counted the row failed. The pace slot is reserved synchronously: `claim-before-the-first-await.md`.
- **Still open when written:** the server's 429 is still unlogged, and the shared pace was reasoned about but not yet watched on a real 200+ burst.

## 2. The 403 swallowed by design (2026-09-26)

A new user's trophies never arrived and nothing said why. Steam answers `403 {"error":"Profile is not public"}` for achievements while happily returning the library. The seed step swallowed errors "by design", stamped itself done, and the server only logged failures on other paths. A plausible code hypothesis was wrong; probing Steam from the server machine found it in minutes. Fix: remember the refusal and show it in plain words where the trophies would be.

## 3. The client timeout shorter than the route (2026-09-21)

The phone could never finish an achievement sync: its shared 20 s read timeout sat under a route that legitimately takes ~10 s per 20-game page, and with no cursor saved, every retry re-walked the same pages. The desktop never saw it because its fetch had no timeout at all. Fix: a dedicated 60 s client for that one route (the second route to need an exception), after timing the route on the server. Verified: 537 → 3,227 unlocks synced.

## The rules

1. **Every refusal path logs or counts**: 429, 403, quota, validation. A limiter that refuses silently makes the log useless as a success signal.
2. **Before concluding "it worked" from clean logs, ask which steps would log at all.** Direct-to-storage uploads and third-party calls often never touch your server.
3. **Pace under a known cap on the client, with one shared pacer**, instead of letting each feature burst and retry on its own.
4. **Never swallow a refusal you can explain to the user in one sentence** ("your Steam profile is private").
5. **Time the slow dependency on the server before touching client timeouts**, and give known-slow routes their own budget.

## Related

- `local-first-sync-with-d1.md` Pattern 8: honouring 429 / Retry-After with backoff (the client half).
- `negative-control-before-trusting-a-probe.md`: a check that can't come back red proves nothing, the same epistemic trap.
- `db-backed-auth-503-not-401.md`: choosing the status code so the client can tell failures apart.
