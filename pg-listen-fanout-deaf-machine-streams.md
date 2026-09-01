---
stack: [postgres, node, sse, fly.io, any-autoscaling-host]
kind: gotcha
last_verified: 2026-09-01
---

# pg LISTEN/NOTIFY fan-out behind an autoscaling proxy — a deaf machine serves streams that look alive

**One-liner:** when each app machine holds one Postgres `LISTEN` connection and fans notifications out to its locally-parked SSE/WebSocket clients, a machine whose LISTEN is down keeps serving streams that look perfectly healthy — app-level keepalive pings don't touch the DB — so pub/sub delivery fails **silently and per-machine**, and nothing in either the client or the server logs says so.

## Symptom

- A client holds an open event stream: connects fine (200), receives the hello, receives keepalive pings on schedule, reconnects properly after drops. By every observable measure the stream is healthy.
- Events published via `pg_notify` never arrive on that client — while an identical client (same account, same endpoint, connected seconds apart) receives them instantly.
- No errors anywhere: the publisher's `NOTIFY` succeeds, the subscriber's stream is live, the app logs are clean.

Measured live (2026-09-01): two desktop streams received pings for 7+ minutes, never a payload event; a reference client opened from a script got the same event in <100ms. Same user, same URL, same event.

## Cause

The fan-out design couples two independent lifetimes on each machine:

1. the **stream-serving loop** (pure app code — pings come from a timer, no DB involvement), and
2. the **one LISTEN connection** that wakes local subscribers when `pg_notify` fires.

An autoscaling host (Fly auto-start/stop, any LB spreading connections) can park a client's stream on any machine. If that machine's LISTEN connection failed to establish (session-mode pooler connection cap, network blip at boot, wrong pooler port — `LISTEN` cannot ride a transaction-mode pooler at all) or died quietly, the machine is **deaf but not dead**: streams keep pinging, subscribers map keeps filling, notifications wake nobody. Machines that boot on demand are the worst case — their LISTEN failure happens at the exact moment traffic arrives, and platform log aggregation frequently loses boot-time lines, so the failure is invisible even in hindsight.

If clients have a polling fallback (a heartbeat pull every N minutes), the loss is masked as "push is a bit slow sometimes." The moment a feature depends on *timely* push with no fallback (ours: a "your cloud data was wiped from another device" courtesy-pause), the silent loss becomes silent feature breakage.

## Fix

Two halves — make deafness loud, and make delivery attributable:

1. **Alarm on a listener-failure streak.** The LISTEN reconnect loop already retries with backoff; add a counter and page (Sentry/alert) once N consecutive attempts fail (we used 3). Reset on success. One report per streak, not per retry — bounded noise. A machine that cannot listen should page someone, because from the outside it is indistinguishable from working.
2. **Log stream parking and event fan-out.** One line per stream open (`stream open <userKey> (<ua-prefix>)`) and one per high-value notification (`<event> for <userKey>: waking N stream(s)`). These two lines turn "which machine is this device parked on, and did the notify wake anyone there?" from a redeploy-and-hope question into a log query. Keep the per-change chatter out — log only the rare, load-bearing event kinds.

Stronger variants if the stakes rise: have the stream loop refuse or close streams while the machine's listener is down (clients reconnect and land elsewhere), or run keepalive *through* the notify path (a periodic self-notify per machine) so deafness breaks the pings too and becomes client-visible.

## The diagnostic pattern that localized it (reusable)

Three vantage points, no guessing:

1. **Synthetic publish** — fire `pg_notify` by hand (bypasses the whole business path; proves/indicts the transport alone).
2. **Reference subscriber** — a ~40-line script holding the same stream with the same auth and the same parsing as the real client, logging every frame with timestamps. Splits client-bug from server-bug in one observation.
3. **On-device breadcrumbs** — when the real client's console is unreachable (a WebView), write its stream-lifecycle decisions into local SQLite and read the file from outside. (See [instrument-before-patching](./instrument-before-patching.md) — this is that rule applied to a stream consumer.)

When the reference subscriber receives an event the real client doesn't — same second, same account — the fault is provably in stream *parking*, not in either codebase. That single observation is what pointed at the per-machine fan-out.

## Related traps caught in the same debug

- **React StrictMode leaks a zombie stream:** a mount→cleanup→mount cycle where cleanup runs while the connect routine is `await`ing something (session load) before it has created its AbortController — the aborted instance then connects anyway and nothing can reach it. Re-check the `stopped` flag after every await that precedes the connect.
- **`LISTEN` needs a session-mode connection.** Transaction-mode poolers (pgbouncer/Supavisor on the transaction port) cannot deliver notifications; derive a session-mode URL for the listener and keep an env override for when the derivation is wrong.
