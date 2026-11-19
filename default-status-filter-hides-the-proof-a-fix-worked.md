---
stack: [debugging, data-analysis, graphql, customer-support, verification]
kind: gotcha
last_verified: 2026-11-18
---

# A default "active" filter can hide the proof that a fix worked: test records get cancelled or deleted afterwards

**One-liner:** to check whether a fix took, you query for successful records created after it and find none. Before saying the fix didn't work, look at the filter. A list query copied from the app's own screen usually asks for active records only, and the first successes after a fix are often tests that someone cancelled or deleted once they'd seen them work. Query every status, sort by updated time, and read the result field on each record.

*Cove support work, 2026-11-18: a vendor fixed a tenant's visitor credentials; the active-only query showed no successes after the fix.*

## What happened

A tenant's visitor credentials had failed for months with the same error from the building's access system. The vendor said they had fixed the tenant's setup. The check was simple: list the tenant's visits created after the fix time and see whether any credential succeeded.

The query was the one the app's visitor list sends, filtered to `status: active` and sorted by created time. It showed failures from before the fix and nothing successful after it. That reads as "the fix didn't take".

It had taken. People had registered test visitors right after the fix, watched them succeed, and cancelled them. Cancelled and deleted visits fall out of the active filter. Asking for all three statuses and sorting by updated time showed the successes at the top.

## Why it's easy to miss

- **The filter came with the query.** A query captured from the app's own page carries the page's defaults. Nobody chose "active only"; it was already there.
- **Tests are the first records after any fix,** and tests are exactly what gets cleaned up.
- **An empty result looks like an answer.** "No successes" is a believed negative, and the probe was blind to the records that would have disproved it.

## The rule

Before reporting that something didn't happen:

1. List the filters on the query, including the ones you didn't add.
2. Widen the status filter to every state, soft-deleted included.
3. Sort by updated time, not created time, so recent activity on old records shows too.
4. Run a positive control: find one record you know exists in the state you're looking for, and confirm the query returns it.

Say in the report which statuses the query covered.

## Related

- [[negative-control-before-trusting-a-probe]]: a believed negative needs a positive control.
- [[capture-a-spas-own-api-calls-with-a-fetch-hook]]: where the query, and its defaults, came from.
- [[silent-refusals-make-clean-logs-meaningless]]
- [[suspect-the-statistic-before-the-threshold]]
