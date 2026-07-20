---
stack: [tauri, desktop, rust, api-integration, monetization]
kind: pattern
last_verified: 2026-07-20
---

# BYO API key as a free tier: call the third-party API from native code, never from webview JS

**One-liner:** when a paid feature calls a metered third-party API (an LLM, a rate-limited web API) through your own server, you can offer a genuine free tier by letting the user paste their OWN key and calling the third-party API directly from the app instead of through your server. But "client-direct" should mean **from native code** (Rust/Tauri command, Electron main process, native mobile networking), never a `fetch()` in the web/renderer layer — and the routing, entitlement, and error-handling design has several non-obvious traps beyond "just add an if-statement."

## The core routing pattern: fork at ONE low branch point, not per-caller
Branch as close to the network boundary as possible. Concretely: the function that generates an AI summary reads "is there a saved personal key?" **once**, and forks only the network call itself — everything before (read local data) and after (write the result, using the identical column set either way) is the same code regardless of path. This is deliberately the lowest place you could branch. The alternative — checking "which mode am I in" at every call site that might invoke the feature — means every caller duplicates the routing logic. With the branch pushed down to one place, existing callers (a forward-summary trigger, a narrative-weave feature, a bulk backfill job) gained the free path with **zero changes to their own code**.

## Do the client-direct call from native code — two independent reasons, not one
1. **Key custody.** A key that only ever exists in OS-encrypted native storage (DPAPI/Keychain) and a native HTTP client is never exposed to the DOM/JS execution context at all — immune to any XSS or supply-chain compromise of the web layer. That's a materially different trust model than "key sits in a JS variable, sent via `fetch()`."
2. **CORS.** Third-party APIs are not guaranteed to set permissive CORS headers for arbitrary origins. A webview `fetch()` straight to a vendor's REST endpoint can simply be blocked by the browser's CORS enforcement depending on their headers and your webview's origin — a failure mode that doesn't exist for a native HTTP client (reqwest, etc.), which has no same-origin concept at all.

## Entitlement design: one predicate per CAPABILITY, composed with OR — never widen a shared "isPremium" boolean
The natural bug: BYO key unlocks feature X, so it gets OR'd into a general "is this user premium" check, which then accidentally also unlocks feature Y (e.g. cloud sync) that BYO was never meant to grant. What held up under repeated gating additions: keep every capability behind its **own named predicate** (`canUseAi()`, `hasUnlimitedAi()`, `isSyncEntitled()`), each composed explicitly — `isSubscribed() || hasByoKey()` for the AI ones, `isSubscribed()` alone (deliberately **not** OR'd with the BYO check) for the sync one. Comment WHY a predicate excludes BYO right at its definition ("BYO never unlocks sync") — the omission looks like a bug to someone who doesn't know it's deliberate, and will get "fixed" wrong otherwise.

Model tiers *within* a capability precisely, too: distinguish "some free generations via a trial counter" from "unlimited via subscription OR BYO key" as two different predicates. A trial-limited state can't actually complete a bulk operation (a full-history backfill) the way unlimited access can — reusing the wrong predicate for a bulk operation silently strands the user partway through with no explanation.

## Reuse the SAME server-side persistence path regardless of which route fetched the data
Client-direct doesn't have to mean client-only. Fetch the source data via the free/native path, then hand the *result* to the exact same downstream write logic the paid/server-key path already uses (extract it into one shared function if it wasn't already). Don't duplicate the persistence/multi-device-sync implementation per source — fork only the narrow "how did we obtain this data" step, converge everything after that onto one path.

## Free tiers carry REAL, LOWER rate limits than your paid path — tune both separately
A free BYO key usually has the vendor's own free-tier rate limit, materially tighter than whatever pooled/paid capacity your server-side key gets (e.g. a free LLM key capped at ~10 requests/minute vs. a paid server key with much more headroom). Reusing your paid path's concurrency/retry tuning against a free key doesn't just run slower — it can make the feature look **stuck** ("progress climbs but nothing completes"), because a retry-burst built to smooth over paid-infrastructure blips keeps re-saturating the free key's tiny per-minute window before anything clears it. Fixes that generalize:
- Give the free/BYO path its **own concurrency + pacing profile** (one paced worker near the key's known limit) instead of sharing tuning constants with the paid path (several concurrent workers).
- Cut retries to a single attempt on the free path. A burst-retry designed for transient paid-infra blips is actively harmful against a hard per-minute cap — let the failed unit resume on the next run instead of retrying immediately and eating more of the budget.
- Surface the real upstream error text (the literal 429 message) in the UI instead of a generic "failed." Free-tier throttling is expected and self-resolving; a user staring at a silently stalled progress bar will assume the feature is broken instead of "wait a minute, rerun."

## Cross-language prompt/logic duplication is an accepted cost — guard it with pointer comments, not tooling
When "client-direct" crosses a LANGUAGE boundary (native Rust calling an LLM directly vs. your JS server doing the same), there's no shared-source mechanism available — unlike same-language duplication, which should get an automated drift-guard script (see `n-copies-of-truth-drift-guard.md`). Port the prompt/logic **verbatim** and accept the duplication deliberately, but leave an explicit pointer comment at **both** copies naming the sibling file and stating "keep in sync." This is weaker than a script — nothing fails a build if they drift — but it's the correct minimum for a boundary a script genuinely can't reach cheaply. Record the acceptance as a locked decision, not an open TODO, so a later DRY audit doesn't flag it as an unaddressed finding.

## Related
- [`n-copies-of-truth-drift-guard.md`](./n-copies-of-truth-drift-guard.md) — the general "must stay in lockstep" problem; this lesson's cross-language duplication is the one case where the guard-script fix isn't available and a documented exception is the right call.
- [`steam-library-integration.md`](./steam-library-integration.md) — the three-tier Steam import model (local scan / OpenID identity / user's-own-key) this pattern extends into tier 3; read it first for the ToS/rate-limit reasoning that justifies a "bring your own key" tier at all.
- `tauri-desktop-security-hardening.md` — assumes you already have a secure local secret store (DPAPI/Keychain); this lesson doesn't re-derive that part.

---
*Captured from Playmoir's Steam Tier 3 (2026-07-16/17, personal Steam Web API key) and BYO AI key (2026-07-17, personal Gemini key) features — both shipped, both live-verified end-to-end.*
