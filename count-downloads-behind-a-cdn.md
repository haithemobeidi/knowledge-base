---
stack: [cloudflare, r2, s3, cdn, analytics, release-engineering]
kind: pattern
last_verified: 2026-08-06
---

# Counting downloads of a file behind a CDN or object store

**One-liner:** you shipped a desktop app, the download link points straight at your object store, and months later "how many people downloaded it" has no answer — because object stores report **bucket-wide** operation counts with no per-object breakdown, and the CDN analytics that *could* break down by path is plan-gated and retention-limited, so it can never accumulate a total. The fix is a redirect counter you own, and the one non-obvious trap is that it must be a **302**: a 301 gets cached by browsers and intermediaries, routes every future download around your handler, and silently freezes the counter at day one — which looks exactly like "nobody is downloading."

## The shape

Any setup where a public file is served by something other than your application:

- Installer / binary in R2, S3, GCS, or a release CDN
- Download link on a marketing page pointing directly at that URL
- Optionally an auto-updater polling a manifest from the *same* bucket

The direct link is correct engineering. It is fast, it is cheap, it survives your server being down, and it needs no code. It also means **your application never observes the download**, so the only record lives in whatever telemetry the storage layer offers.

That telemetry is worse than people assume.

## Why the storage metrics can't answer it

Measured against Cloudflare R2 on 2026-08-06, and the shape generalises:

| what the dashboard offers | what it actually tells you |
|---|---|
| Class A operations (writes) | your own uploads, mostly |
| Class B operations (reads) | **every read of every object, pooled** |
| Data Retrieved | `0 B` — see below |
| Request distribution by region | where, not what |

**There is no per-object breakdown.** Cloudflare's own docs are explicit that storage metrics are bucket-level and operations metrics aggregate by action type, not by key. So installer GETs and updater manifest polls land in one number.

That pooling is not a rounding error, it is a *majority*. Real numbers from the case below: 5 installs, each polling an update manifest every 4 hours, generate ~30 reads/day on their own. The observed 24-hour Class B count was **47**. The installer downloads were somewhere in the remaining handful. The metric is dominated by the thing you did not want to measure.

### The `0 B` trap that looks like a contradiction

"Data Retrieved" read **0 B** over 30 days while Class B operations read **1.28k**. That looks like broken telemetry or a miracle of caching. It is neither: on R2, *Data Retrieved is the Infrequent Access retrieval-fee meter*. Standard-class objects report zero there by definition, because there is no retrieval fee to meter.

> **Do not read "Data Retrieved: 0 B" as "no bytes were served."** It is a billing meter for one storage class, not an egress counter. Egress is free on R2 and therefore not metered here at all.

### And the CDN analytics that could do it, won't

Zone-level analytics is the other reflex. It has a path dimension in principle, but it is plan-gated, and on the free tier the retention window is a rolling few days rather than history. Verify your own plan through the analytics settings-discovery endpoint rather than assuming a number — but the structural point holds regardless of what you find: **a rolling window cannot accumulate a launch-to-date total.** Even a generous retention only ever tells you about recent traffic.

So: no per-object breakdown, and no history. Both roads are closed.

## The fix: a redirect counter you own

Point the *website's* download link at your own endpoint. It records the click and redirects to the real file.

```js
// GET /download?src=landing|beta
downloads.get('/', async (c) => {
  const source = sourceSchema.parse(c.req.query('src'));   // enum + .catch(default)
  const withinLimit = checkRateLimit(`download:${ip}`, 10, 60);

  // HEAD is a link-checker or a prefetch, not a person getting the app.
  if (c.req.method === 'GET' && withinLimit) {
    try {
      await pool.query(
        `insert into download_clicks (source, count) values ($1, 1)
         on conflict (occurred_on, source)
         do update set count = download_clicks.count + 1`, [source]);
    } catch (err) {
      reportError(err);   // bookkeeping failed; the download must not
    }
  }

  c.header('Cache-Control', 'no-store');
  return c.redirect(INSTALLER_URL, 302);   // 302. NEVER 301. See below.
});
```

Four properties do the work, and each one is a decision:

**1. 302, never 301.** This is the trap. A permanent redirect is cacheable by default and browsers honour it aggressively — often for the life of the profile. Cache it once and every subsequent download from that browser goes straight to the file, never touching your handler again. Your counter then reports early adopters forever and flatlines, which is indistinguishable from genuine failure and will be believed, because a flat line is what you feared. Add `Cache-Control: no-store` too, for anything that caches by header rather than by status code.

> Note on evidence: the 301-caching hazard is standard HTTP caching semantics and was **designed against**, not observed breaking. The R2 metric limitations above *were* measured.

**2. Bookkeeping failure must never break the download.** Unknown `src`, tripped rate limit, database unreachable — every path still ends in the redirect. Counting is best-effort; the download is the product. Note the schema uses a `.catch(default)` rather than throwing on a bad value, for the same reason.

**3. The source parameter is an enum, not free text.** It lands in a column. An open string from a query string is how a query string becomes a storage-injection surface.

**4. It is an `<a href>` navigation, not a `fetch`.** So it is not a CORS request, needs no allowlist entry, and keeps the browser's native download handling. Resist "improving" it into a fetch: you would gain a CORS requirement and lose the download.

## What NOT to route through it

**Leave your auto-updater on the direct URL.** This is the judgement call that matters most, and the instinct to "count everything" is wrong here.

An updater fetching a manifest and a versioned binary is a library user-agent hitting a CDN, which is already a fragile path — see [bot-challenge-blocks-your-auto-updater.md](./bot-challenge-blocks-your-auto-updater.md), where the same host 403s `reqwest` and curl while serving browsers fine, and OTA survives by coincidence of user-agent rather than by configuration. Inserting a redirect into that path risks breaking every install's ability to update, **silently** (updater check-failures are deliberately quiet), in exchange for a number you can get better elsewhere.

The clean split:

- **Downloads are website traffic.** Count them at the link.
- **Updates and active use are app traffic.** Count them with an in-app ping, which tells you what versions are actually live — see [privacy-shaped-usage-analytics.md](./privacy-shaped-usage-analytics.md).

Those answer different questions anyway. Downloads measure *intent*; opens measure *use*. Conflating them is how you end up proud of a download count that never became a user.

## Store a tally, not an event log

The table is three columns:

```sql
create table download_clicks (
  occurred_on date   not null default (now() at time zone 'utc')::date,
  source      text   not null,
  count       bigint not null default 0,
  primary key (occurred_on, source)
);
```

One row per day per link, incremented. Not one row per click with a timestamp and an IP.

This is not premature optimisation, it is scope control. A per-click log with timestamps is a behavioural record of when people discover your product, and it will sit in your database for years being a liability nobody chose. The tally answers "how many downloads on day X, from which link" and is *structurally incapable* of answering anything else. Rate-limit on IP, then discard the IP; give it no column to land in.

## The measured case

A Windows desktop app, launched with the download link pointing straight at R2, no instrumentation of any kind. Two weeks later the state of knowledge was:

| question | answer available |
|---|---|
| How many downloads? | **none** — pooled into bucket-wide reads dominated by update polls |
| How many people opened it? | 5 installs (an in-app ping added later) |
| Which version are they on? | all on the current release |
| Did the website work? | 280 visits / 290 page views, all Core Web Vitals green |

The funnel that emerged once both counters existed: **280 site visits → 6 sign-ins → 5 installs opening the app → 1 outside person who created anything.** Every one of those numbers is cheap to collect and none of them existed at launch.

**The retroactive part is the cost.** The counter starts at zero on the day you deploy it. Two weeks of downloads were unrecoverable, because the data needed to reconstruct them was never retained by anything. This is the entire argument for wiring it before launch rather than after.

## Checklist

1. **Before launch**, point the public download link at your own endpoint, not the bucket.
2. **302 + `Cache-Control: no-store`.** Grep your codebase for `301` near any redirect you intend to count.
3. **Every failure path still redirects.** Write the test that pulls the database down and confirms the file still downloads.
4. **Bounded enum for the source param**, defaulted rather than thrown.
5. **Leave the updater on the direct URL** and count active installs in-app instead.
6. **Tally, not log.** Day grain, no identifier, no IP column.
7. **Confirm what your storage metrics actually mean** before trusting a zero. Retrieval-fee meters, egress counters, and request counts are three different things.

## Anti-patterns

- ❌ **Reading bucket-wide request counts as download counts.** They are dominated by whatever polls most often, which is usually your own updater.
- ❌ **301 on a counted redirect.** Cached, invisible, and it fails in the direction you will believe.
- ❌ **Routing the auto-updater through the counter.** Risks silent OTA death to learn something an in-app ping answers better.
- ❌ **Proxying the file bytes through your server** to count them. You pay egress and add a failure point in front of your own installer, to increment an integer.
- ❌ **Waiting until you "have users" to add it.** The counter only ever knows the future. The cheapest day to add it is before the first release.
- ❌ **Believing a flat counter without checking the redirect status.** Flat is the expected symptom of both "no downloads" and "cached 301."

## Related

- [bot-challenge-blocks-your-auto-updater.md](./bot-challenge-blocks-your-auto-updater.md) — why the updater's path is fragile and must not be rerouted; same CDN, adjacent failure.
- [privacy-shaped-usage-analytics.md](./privacy-shaped-usage-analytics.md) — the other half of the funnel: counting *use* rather than *intent*, without building a behavioural log.
- [signed-but-flagged-download-reputation.md](./signed-but-flagged-download-reputation.md) — download *volume* under a stable signing identity is what clears SmartScreen/Chrome reputation warnings, which is another reason to actually know the number.
- [instrument-before-patching.md](./instrument-before-patching.md) — the debugging-side sibling: when a system's decisions are invisible, add the trail rather than another patch.
