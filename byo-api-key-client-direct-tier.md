---
stack: [tauri, desktop, rust, api-integration, monetization]
kind: pattern
last_verified: 2026-08-01
---

# BYO API key as a free tier: call the third-party API from native code, never from webview JS

**One-liner:** when a paid feature calls a metered third-party API (an LLM, a rate-limited web API) through your own server, you can offer a genuine free tier by letting the user paste their OWN key and calling the third-party API directly from the app instead of through your server. But "client-direct" should mean **from native code** (Rust/Tauri command, Electron main process, native mobile networking), never a `fetch()` in the web/renderer layer — and the routing, entitlement, and error-handling design has several non-obvious traps beyond "just add an if-statement."

## The core routing pattern: fork at ONE low branch point, not per-caller
Branch as close to the network boundary as possible. Concretely: the function that generates an AI summary reads "is there a saved personal key?" **once**, and forks only the network call itself — everything before (read local data) and after (write the result, using the identical column set either way) is the same code regardless of path. This is deliberately the lowest place you could branch. The alternative — checking "which mode am I in" at every call site that might invoke the feature — means every caller duplicates the routing logic. With the branch pushed down to one place, existing callers (a forward-summary trigger, a narrative-weave feature, a bulk backfill job) gained the free path with **zero changes to their own code**.

## Do the client-direct call from native code — two independent reasons, not one
1. **Key custody.** A key that only ever exists in OS-encrypted native storage (DPAPI/Keychain) and a native HTTP client is never exposed to the DOM/JS execution context at all — immune to any XSS or supply-chain compromise of the web layer. That's a materially different trust model than "key sits in a JS variable, sent via `fetch()`."
2. **CORS.** Third-party APIs are not guaranteed to set permissive CORS headers for arbitrary origins. A webview `fetch()` straight to a vendor's REST endpoint can simply be blocked by the browser's CORS enforcement depending on their headers and your webview's origin — a failure mode that doesn't exist for a native HTTP client (reqwest, etc.), which has no same-origin concept at all.

**Concrete storage shape that reused cleanly across two unrelated keys (Steam + Gemini):** split the concern into a **crypto module** (encrypt/decrypt only — e.g. `protect_secret(plaintext) -> "dpapi:v1:<base64>"`, `reveal_secret(marker) -> plaintext`, `is_protected(value)`) and a separate **KV-accessor module** that layers `put_secret`/`load_secret`/`clear_secret` on top of a generic local key-value table. Two details worth stealing directly:
- **Marker-prefix the ciphertext** (`dpapi:v1:...`) instead of assuming every value in that column is encrypted. It lets `is_protected()` distinguish "encrypted" from "not yet migrated" from "explicitly cleared," and lets you version the scheme later without a migration that touches every row.
- **An empty string is the "no secret" sentinel**, not a NULL/missing-row check — simplifies every call site to one falsy check instead of an existence check plus a value check.
- Because the crypto and the accessor are separate modules, adding the SECOND key (Gemini, after Steam already existed) took **zero new crypto code** — pure reuse of the KV+encryption split, only a new accessor call site. That reuse is the actual payoff of splitting these two concerns instead of writing one bespoke "store this key" function per feature.

## Entitlement design: one predicate per CAPABILITY, composed with OR — never widen a shared "isPremium" boolean
The natural bug: BYO key unlocks feature X, so it gets OR'd into a general "is this user premium" check, which then accidentally also unlocks feature Y (e.g. cloud sync) that BYO was never meant to grant. What held up under repeated gating additions: keep every capability behind its **own named predicate** (`canUseAi()`, `hasUnlimitedAi()`, `isSyncEntitled()`), each composed explicitly — `isSubscribed() || hasByoKey()` for the AI ones, `isSubscribed()` alone (deliberately **not** OR'd with the BYO check) for the sync one. Comment WHY a predicate excludes BYO right at its definition ("BYO never unlocks sync") — the omission looks like a bug to someone who doesn't know it's deliberate, and will get "fixed" wrong otherwise.

Model tiers *within* a capability precisely, too: distinguish "some free generations via a trial counter" from "unlimited via subscription OR BYO key" as two different predicates. A trial-limited state can't actually complete a bulk operation (a full-history backfill) the way unlimited access can — reusing the wrong predicate for a bulk operation silently strands the user partway through with no explanation.

### Getting the predicates right is only half of it — audit the OFFERS too

Named per-capability predicates fix *who can do the thing*. They do nothing about **who gets told the thing exists**, and those are separate code paths that drift apart silently.

The failure (Playmoir, 2026-08-01): the bulk-backfill capability was correctly gated on `hasUnlimitedAi()` (subscription **or** BYO key). But the modal that *offers* the backfill — the "you're in, want to catch up your history?" moment — fired on a `isSubscribed()` false→true edge, because it was written when subscription was the only way to get there. Net result: a BYO-key user had the capability the entire time and was **never told**. Nothing was broken, nothing threw, and the feature was reachable if you went looking in settings. It was simply invisible to a whole tier of users, indefinitely.

This is structurally invisible for a reason: the capability check and the discovery check are usually **far apart in the codebase** (a settings card vs. an app-root modal), written months apart, and neither is wrong on its own terms. A test that asks "can a BYO user run a backfill?" passes.

The audit that catches it: for each capability predicate, grep every reference and **sort the call sites into two piles — gates and offers** (banners, nudges, upgrade modals, empty-state CTAs, notification rows, onboarding steps). Every offer for capability X must use the *same predicate* as the gate for X, or be able to say why not in one sentence. Where an offer fires on a **transition** rather than a state, the predicate in the edge-detector is the one that matters — and it's the easiest to overlook, because it often sits inside a `useEffect` rather than next to any UI.

One migration trap when you fix one: an offer that fires on an edge usually persists an "already shown this" flag, baselined from the *old* predicate. Widening the predicate makes previously-ineligible users read as a fresh conversion, so the offer fires once for everyone who was silently excluded. That is usually the correct outcome — it's the offer they should have had — but decide it deliberately and say so in the release notes, rather than being surprised by a support ticket.

## Reuse the SAME server-side persistence path regardless of which route fetched the data
Client-direct doesn't have to mean client-only. Fetch the source data via the free/native path, then hand the *result* to the exact same downstream write logic the paid/server-key path already uses (extract it into one shared function if it wasn't already). Don't duplicate the persistence/multi-device-sync implementation per source — fork only the narrow "how did we obtain this data" step, converge everything after that onto one path.

## Free tiers carry REAL, LOWER rate limits than your paid path — tune both separately
A free BYO key usually has the vendor's own free-tier rate limit, materially tighter than whatever pooled/paid capacity your server-side key gets (e.g. a free LLM key capped at ~10 requests/minute vs. a paid server key with much more headroom). Reusing your paid path's concurrency/retry tuning against a free key doesn't just run slower — it can make the feature look **stuck** ("progress climbs but nothing completes"), because a retry-burst built to smooth over paid-infrastructure blips keeps re-saturating the free key's tiny per-minute window before anything clears it. Fixes that generalize:
- Give the free/BYO path its **own concurrency + pacing profile** (one paced worker near the key's known limit) instead of sharing tuning constants with the paid path (several concurrent workers).
- Cut retries to a single attempt on the free path. A burst-retry designed for transient paid-infra blips is actively harmful against a hard per-minute cap — let the failed unit resume on the next run instead of retrying immediately and eating more of the budget.
- Surface the real upstream error text (the literal 429 message) in the UI instead of a generic "failed." Free-tier throttling is expected and self-resolving; a user staring at a silently stalled progress bar will assume the feature is broken instead of "wait a minute, rerun."

## Cross-language prompt/logic duplication is an accepted cost — guard it with pointer comments, not tooling
When "client-direct" crosses a LANGUAGE boundary (native Rust calling an LLM directly vs. your JS server doing the same), there's no shared-source mechanism available — unlike same-language duplication, which should get an automated drift-guard script (see `n-copies-of-truth-drift-guard.md`). Port the prompt/logic **verbatim** and accept the duplication deliberately, but leave an explicit pointer comment at **both** copies naming the sibling file and stating "keep in sync." This is weaker than a script — nothing fails a build if they drift — but it's the correct minimum for a boundary a script genuinely can't reach cheaply. Record the acceptance as a locked decision, not an open TODO, so a later DRY audit doesn't flag it as an unaddressed finding.

**The pointer comments are necessary and still not sufficient, and this bit us.** They keep the copies matching *in the repo*. They say nothing about whether both copies are **live** — and a cross-language pair almost by definition ships through two different release mechanics (the native copy compiles into the app binary, the server copy needs a deploy). Patch both in one commit, follow the practice exactly, and production can still run one old copy for as long as nobody deploys. Worse, the split usually follows the entitlement fork described above, so the stale copy only affects *one tier* — and whichever tier your dev account is on decides whether you ever see it. See the "lockstep sub-variant" in [`n-copies-of-truth-drift-guard.md`](./n-copies-of-truth-drift-guard.md) for the incident and the timestamp check that catches it.

## Related
- [`n-copies-of-truth-drift-guard.md`](./n-copies-of-truth-drift-guard.md) — the general "must stay in lockstep" problem; this lesson's cross-language duplication is the one case where the guard-script fix isn't available and a documented exception is the right call.
- [`steam-library-integration.md`](./steam-library-integration.md) — the three-tier Steam import model (local scan / OpenID identity / user's-own-key) this pattern extends into tier 3; read it first for the ToS/rate-limit reasoning that justifies a "bring your own key" tier at all.
- `tauri-desktop-security-hardening.md` — assumes you already have a secure local secret store (DPAPI/Keychain); this lesson doesn't re-derive that part.

---
*Captured from Playmoir's Steam Tier 3 (2026-07-16/17, personal Steam Web API key) and BYO AI key (2026-07-17, personal Gemini key) features — both shipped, both live-verified end-to-end.*
