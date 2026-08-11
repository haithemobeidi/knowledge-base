---
stack: [any, verification, testing, http, spa, debugging, process]
kind: gotcha
last_verified: 2026-08-11
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

## The same disease in your test suite: the vacuous assertion

A probe that cannot return red has a twin that is easier to write and harder to spot: **an assertion over a collection that turned out to be empty.**

Every test of the form *"no element of S violates P"* passes when `S` is empty. Not by accident of the framework — that is what "for all" means. So the assertion is only doing work if `S` is non-empty, and **the size of `S` is part of what must be asserted.**

Measured instance. A guard was written to prove no framework-default colour had leaked into an app's theme. It enumerated the theme's colour slots by reflection, filtered method names on a language-specific mangling suffix (Kotlin appends a hash like `-0d7_KjU` to getters returning an inline value class), and asserted that none of them matched the framework's baseline:

```kotlin
val inherited = ours.filter { (name, value) -> baseline[name] == value }.keys
assertTrue("still inherited: $inherited", inherited.isEmpty())   // PASSED
```

The suffix did not match at runtime. The filter returned **zero slots**. `emptySet().isEmpty()` is true, so the test passed — green, fast, and examining nothing. It was caught only because a second test had been written alongside it:

```kotlin
@Test fun `the reflection actually finds the slots`() {
    val found = slots(AppColors)
    assertTrue("found only ${found.size} — the filter has broken: ${found.keys}", found.size >= 40)
    assertTrue(found.containsKey("primary"))
}
```

That is the negative control, in test form. The fix to the guard itself was also the same lesson one level down — stop keying off an incidental naming detail and key off something contractual (the getter's return type), so a re-mangling cannot silently empty the set again.

**Where empty-set vacuity hides:**

- **Reflection and annotation scanning** — a package filter, a name pattern, a classpath scan that finds nothing.
- **Linters and formatters with a glob** — `lint 'src/**/*.ts'` on a repo that moved to `app/` reports zero problems, forever, cheerfully.
- **Parameterised tests** whose data provider returns an empty list. Most runners report this as passing, not skipped.
- **`grep`-based CI gates** — "assert the forbidden string does not appear" passes when the file path is wrong.
- **Migrations and bulk updates** — `UPDATE … WHERE …` matching zero rows is a success exit code.
- **Contract tests that parse another repo's source** to derive expectations: if the anchor text moves, the extracted set is empty and both sides "agree."

**The habit, stated once:** any check whose success condition is *the absence of something* must be paired with proof that it was looking at something. Assert the count, assert one known-present member, or deliberately break the thing and watch it go red before you trust it green.

That last one is the cheapest and most under-used version: **make the test fail on purpose, once.** Rename a colour, add a forbidden string, point at a file you know is bad. A test you have never seen fail is a test you have never seen work.

## The mirror image: a believed NEGATIVE needs a POSITIVE control

Everything above guards believed *positives* — the probe said yes, prove it could have said no. The census case is the mirror, and it bites harder because agreement between probes feels like corroboration.

Live example (2026-08-10): a census of 728 Steam games probed the flat CDN for each game's `logo.png` and cross-checked every miss against Steam's `GetItems` asset API. Both sources agreed, unanimously: 86 games have no logo. The user was **staring at one of those logos**, rendered by the desktop app, while being told it didn't exist. Both probes were honest — and both were blind to the same thing: Steam serves library assets through a second, hash-addressed pipeline that neither the flat CDN nor the store API covers (mechanics in [[steam-library-integration]]). The census surveyed one population and reported on a different, larger one.

The control for a believed negative is **positive**: run the probe on an instance where the answer is KNOWN to be yes. Here that was trivial and skipped — probe a game whose logo is visibly rendering; the census answers "no logo"; the instrument is proven blind and every "no" it produced is void. Note what unanimity was actually worth: two probes that share a blind spot agree for free. Corroboration only counts across probes with *different* failure modes.

Two rules of thumb fall out:

- **A user staring at the screen outranks a unanimous probe census.** "I'm looking at it" is a positive instance handed to you for free — treat it as the control, not as noise to argue with. The correct response is "my instrument must be blind — where's the pipeline it can't see," never "the API says otherwise."
- **Before publishing a negative ("X doesn't exist", "none are affected"), name the population your probe can actually see** and check it matches the population your claim is about. "No logo in the store pipeline" was always true; "no logo exists" never followed from it.

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

## Related

- [[steam-library-integration]] — the census incident's mechanics: the two disjoint asset pipelines that made two honest probes unanimously wrong.

- [[compose-invisible-text-localcontentcolor]] — where the vacuous-assertion case above came from, and the framework-default bug the broken guard was written to catch.
- [[resolve-versions-from-the-registry-not-a-search-index]] — same family, different instrument: the endpoint that answered you was not the one that knows.
