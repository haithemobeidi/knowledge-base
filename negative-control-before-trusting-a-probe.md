---
stack: [any, verification, http, spa, debugging, process]
kind: gotcha
last_verified: 2026-08-08
---

# A 200 is not an existence check — run the negative control before trusting any probe

**One-liner:** you check whether something exists by probing it, the probe comes back green, you report it verified. But a probe only carries information if it can come back *red* — and a startling number of them can't: a single-page app returns HTTP 200 for a resource that does not exist, because the route is client-rendered and the 404 lives inside JavaScript you never executed. Measured: `curl` of a VirusTotal report for an **all-zeros SHA-256** returns `200 OK`, exactly like a real one. The habit that costs ten seconds and prevents a false "verified": **before trusting a positive result, run the same probe against input you KNOW is bad, and confirm it fails.**

## The shape

You need to confirm a fact about a remote system:

- does this file/report/page exist?
- is my change actually live?
- did the deploy pick up the new asset?

You reach for the cheapest probe — `curl -o /dev/null -w "%{http_code}"`, a `grep` over a fetched page, a HEAD request. It returns success. You write "verified."

**The question you skipped: what would this probe have done if the answer were no?**

## Why SPAs break existence checks specifically

A server-rendered site 404s at the server. A client-rendered one usually cannot:

```
GET /gui/file/<any 64 hex chars>/detection
  -> 200 OK
  -> <html><div id="app"></div><script src="/bundle.js">
```

The server's job is to hand back the shell for *every* path so the router can boot. Whether the resource exists is decided later, in the browser, by a fetch your `curl` never made. The status code is a fact about the shell, not about the thing.

This is not exotic. It is the default for React Router / Vue Router / Next in SPA mode, most static hosts with a SPA fallback rewrite, and essentially every "check my dashboard link works" scenario.

## The rule

**Every probe gets a negative control before its result is believed.**

```bash
# the claim
curl -s -o /dev/null -w "%{http_code}\n" "https://host/gui/file/$REAL_SHA256/detection"
# -> 200        looks like proof

# the control: input that CANNOT exist
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://host/gui/file/0000000000000000000000000000000000000000000000000000000000000000/detection"
# -> 200        the probe is blind; discard the result above
```

Two outcomes, both valuable:

- **Control fails (404/error):** your probe discriminates. The green result means something.
- **Control passes:** your probe is blind. You have learned nothing about the real input, and — this is the point — you were *about to report that you had*.

## Where else this bites

- **`grep` over a fetched page.** If the fetch 302s, is challenged, or returns an error body, `grep -q` reports "not found" — indistinguishable from "found the page, string genuinely absent." Control: grep for a string you know IS on the page. Check the byte count too; a suspiciously small body is an error page.
- **APIs that return 200 with an error payload.** Very common in GraphQL and in older REST designs. Status-code checks pass forever.
- **Boolean pipelines in shell.** `curl ... | grep -q X && echo present || echo missing` collapses *three* states (present / absent / fetch failed) into two, and assigns the failure to "missing." Prefer downloading to a file, asserting the size, then grepping the file.
- **"Is my deploy live?"** The old asset is often still served for a short window. A check run immediately after deploy tests the *previous* deployment and reads as a routing fault. Control: confirm the response carries something unique to the new build, and re-check after a delay before concluding anything.

## When the probe cannot be made honest

Sometimes the endpoint that *would* answer truthfully is unavailable to you. In the case this came from, the JSON backend behind the SPA returns the real answer — and is gated by reCAPTCHA:

```
GET /ui/files/<sha256>
-> 429  {"error": {"code": "RecaptchaRequiredError"}}
```

So: no discriminating automated probe exists.

**The correct move is to say so and hand the check to a human**, not to fall back on the blind probe and phrase the result carefully. "I confirmed it returns 200" is technically true and functionally a lie, because the reader hears "it exists." A ten-second human click is cheap; a published badge pointing at a 404 is not.

## Relationship to nearby rules

This is a sharper, narrower cousin of [suspect-the-statistic-before-the-threshold.md](./suspect-the-statistic-before-the-threshold.md). That one says: when your measure misclassifies, doubt the measure rather than the cut point. This one says: **doubt whether your measure has any resolution at all** — not "is the threshold right" but "can this instrument produce a negative?" A statistic that returns the same value for both populations is the degenerate case of the same disease.

It is also the verification-side twin of [instrument-before-patching.md](./instrument-before-patching.md): that rule is about making failures visible before patching, this one is about making sure the thing you built to see with can actually see.

## The one-line version

**An instrument that cannot fail is not measuring anything.** Prove it can fail, then believe it.
