---
stack: [any, analytics, privacy, product, postgres]
kind: pattern
last_verified: 2026-08-06
---

# Usage analytics that can't become a behavioural log

**One-liner:** "is anyone actually using this?" is the one question a local-first / privacy-respecting app most needs and least wants to instrument, because the obvious implementation — an event row per action with a timestamp, a user id, and an IP — is a behavioural log nobody asked for and which you will then own for years. The pattern is to pick a **grain and a key that make the invasive query structurally impossible to write**, rather than promising not to write it. Plus the drift trap that bit hardest: a stale comment describing your *privacy posture* is far worse than a stale comment describing a function, because the next reader makes a policy decision from it.

## The setup

You shipped. You have no idea if anyone uses it. The honest state of knowledge is usually:

> "Nobody downloaded it" was an inference from an absence of support emails, not a measurement.

So you reach for analytics, and every off-the-shelf option and every naive hand-roll lands in the same place: an events table with `user_id`, `event_name`, `occurred_at timestamptz`, `ip`, `user_agent`. That schema can answer your question. It can also answer *when this person plays games, how often, and for how long*, which is a question you never wanted and now have to defend, secure, and honour deletion requests against.

The instinct that follows is to not instrument at all. That is how you get to launch with zero signal, which is the actual failure.

## The pattern: design the grain so the bad query has no data to run on

Two tiers, depending on whether the event has continuity worth tracking.

### Tier 1 — a random install key, day grain (for "who is still using this, on what version")

```sql
create table app_opens (
  id          bigint generated always as identity primary key,
  install_id  uuid not null,
  app_version text not null,
  opened_on   date not null default (now() at time zone 'utc')::date,
  unique (install_id, opened_on)          -- the whole design is this line
);
```

```sql
insert into app_opens (install_id, app_version) values ($1, $2)
on conflict (install_id, opened_on) do nothing;
```

Every decision here is load-bearing:

**Day grain, not a timestamp.** Opening the app nine times on a Tuesday writes **one row**. That yields daily-active-installs, which is the metric you actually wanted, while making it *structurally impossible* to reconstruct when in the day someone uses the product or how often. A `timestamptz` column would have handed you a behavioural log for free, and you would not have noticed you had accepted it.

**A random client-generated UUID, derived from nothing.** Not the account id, not hardware, not a hash of either. It joins to no person. It also does **not survive a reinstall**, so reinstalls read as new installs. That is an accepted inaccuracy, and accepting it is the point: the only way to survive a reinstall is a durable device fingerprint, which is precisely the thing this must not be.

**No IP column.** The handler rate-limits on IP and then discards it. There is nowhere for it to land. "We don't store it" is a promise; "there is no column" is a property.

**Unauthenticated on purpose.** Most installs are signed out, and the question is "did anyone open the app," not "did any *subscriber* open the app." Requiring a session would both narrow the question and tie the ping to an identity — the opposite of the goal.

**Fire-and-forget.** Never blocks startup, never retries into a storm, never surfaces a failure to the user. The server dedupes per day, so a missed ping costs nothing; the next launch covers it.

### Tier 2 — no key at all (for anonymous one-shot events)

Some events have no continuity worth tracking. A download click is one: there is no session to follow, no retention to compute. Give it *less* than tier 1 — a pure tally:

```sql
create table download_clicks (
  occurred_on date   not null default (now() at time zone 'utc')::date,
  source      text   not null,          -- which link, a bounded enum
  count       bigint not null default 0,
  primary key (occurred_on, source)
);
```

No identifier of any kind. Not even a random one. A row is a number, and no query against this table can distinguish one person's download from another's, because the information was never captured. (See [count-downloads-behind-a-cdn.md](./count-downloads-behind-a-cdn.md) for why a counter like this is necessary at all.)

**The general move: ask what the weakest schema is that still answers your question, then build exactly that.** Most instrumentation is over-specified because nobody asked.

## Cut the fields you can't justify, and write down why

An `os` column was drafted into the app-open ping and cut before shipping. The reasoning is worth copying:

- The product is Windows-only at v1, so the value would be near-constant.
- The one case that genuinely needs it ("this bug only reproduces on Windows 10") is already covered by the crash reporter, which captures OS on every report.
- Collecting it here would be a second copy of data already held, for no question anyone actually had.

> **Rule:** every field must name a question it answers that no existing system answers. "It might be useful later" is how a privacy-shaped schema becomes an events table over three releases. Add it later, *with* the reason, if the question appears.

## The default-on decision, argued honestly

Off-by-default was drafted for the app-open ping and rejected. The reasoning, stated plainly because it is the uncomfortable part:

**Opt-in telemetry that nobody opts into answers nothing, while still costing a settings row.** You get the appearance of respecting users and none of the information, which is the worst of both.

What was shipped instead: **default on, disclosed at first run with a one-click opt-out**, plus a permanent toggle in settings next to the crash-reporting one. That is defensible *only because* of everything above — the payload is two fields, there is no identifier tied to a person, and there is no way to reconstruct behaviour from it. The same default on the naive events schema would not be defensible.

The trade in one line: **the weaker the data, the stronger the case for collecting it by default.** If you find yourself wanting default-on for a rich schema, you have the trade backwards.

Whatever you choose, the disclosure has to be real: named at first run, reversible in one click, and described accurately in the privacy policy — including retention ("we keep these for 12 months, then delete them").

## The drift trap, which is the part that actually bit

Three months after shipping this, a routine read of the code found:

- The **migration's header comment** described the ping as *"Opt-IN and OFF by default."* The client shipped **default on with an opt-out**. The comment described a design that was explicitly considered and rejected.
- The **codebase index** described a payload of `{installId, appVersion, os}` and a table with an `os` column. There is no `os` anywhere — it was the field that got cut.

Nothing was broken in production. The code was right and the privacy policy matched the code. But this class of staleness is uniquely dangerous:

> A stale comment about a function makes someone write a bug. **A stale comment about a privacy posture makes someone make a policy decision** — answer a user's question wrongly, write a privacy policy that doesn't match, or "fix" the code to match the comment and silently flip a default that was chosen deliberately.

The `os` variant is worse than it looks in the other direction: it documents data you do not collect, so a reader auditing your data footprint concludes you hold more than you do. Both directions of drift produce a wrong answer to "what do you collect."

**Mitigations, cheapest first:**

1. **Name the authority in the comment.** `appOpenPing.ts is the authority on this behaviour — do not re-read this file as "opt-in."` A comment that points at its own source of truth degrades gracefully.
2. **Record the rejected alternative and why**, not just the decision. "Off-by-default was drafted and rejected because nobody would enable it" survives contact with a future reader who thinks off-by-default is obviously correct. A bare "default on" invites a well-meaning fix.
3. **When you touch one surface, audit all of them.** The claim lived in four places: migration, server entry point, index, privacy policy. Three were wrong. Grep the *claim*, not the file.
4. Related, and worth reading if you have several copies of any schema: [n-copies-of-truth-drift-guard.md](./n-copies-of-truth-drift-guard.md).

## What it bought

Three days after the ping shipped, from a standing start of "no idea":

| | |
|---|---|
| distinct installs opening the app | **5** |
| version breakdown | all on the current release, so OTA is working |
| daily pattern | 1 / 3 / 1 across three days |

Small numbers, but they are the difference between knowing and guessing, and they cost one table and one endpoint. The version breakdown was an unplanned bonus: it confirms auto-update is actually reaching people, which is otherwise near-impossible to verify because updater failures are silent.

**The retroactive limit applies here too:** this can only ever tell you about the future. Two weeks of post-launch usage were unrecoverable.

## Checklist

1. **Write the question first**, in one sentence. "How many distinct installs opened the app on day X, by version." The schema falls out of it.
2. **Pick the coarsest grain that answers it.** Day, not timestamp, unless you can name why you need the hour.
3. **Pick the weakest key that answers it.** No key > random key > account id. Never a fingerprint.
4. **Give sensitive fields no column.** Rate-limit on IP, then drop it.
5. **Justify every field** against a question no existing system answers. Cut the rest and write down that you cut them.
6. **Match the default to the payload's weakness**, and disclose it at first run with a one-click exit.
7. **Name the code as authority in the schema comment**, and record the rejected alternative.
8. **Do it before launch.** It only knows the future.

## Anti-patterns

- ❌ **A generic events table** with `event_name` + `timestamptz` + `user_id`. It answers your question and forty you never wanted.
- ❌ **Opt-in on a genuinely anonymous ping.** Nobody enables it; you get a settings row and no data.
- ❌ **Default-on with a rich payload.** The trade only works one way round.
- ❌ **A field "for later."** Add it with a reason when the question appears.
- ❌ **An id derived from an account or hardware**, including "just a hash of it." A hash of an identifier is an identifier.
- ❌ **"We don't store IPs" as a policy rather than a schema.** Delete the column.
- ❌ **Letting a bookkeeping failure reach the user.** It is not a feature; it must never modal, retry-storm, or block startup.
- ❌ **Trusting a comment about what you collect.** Read the schema and the payload; comments about privacy drift like any other comment, and cost more when they do.

## Related

- [count-downloads-behind-a-cdn.md](./count-downloads-behind-a-cdn.md) — the other half of the funnel, and where the tier-2 tally shape comes from.
- [n-copies-of-truth-drift-guard.md](./n-copies-of-truth-drift-guard.md) — when the same fact lives in several schema copies, drift is guaranteed without a guard.
- [supabase-rls-with-own-backend.md](./supabase-rls-with-own-backend.md) — remember to enable deny-all RLS on these tables too; a bookkeeping table is still a table an auto-exposed REST API will happily serve.
- [instrument-before-patching.md](./instrument-before-patching.md) — the same instinct pointed at debugging rather than product.
