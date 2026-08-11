---
stack: [cloudflare, tauri, rust, release-engineering, reliability]
kind: gotcha
last_verified: 2026-08-10
---

# Your CDN's bot challenge blocks library user-agents, and an auto-updater is a library user-agent

**One-liner:** put your update manifest behind Cloudflare (or any WAF with bot management) and the endpoint will serve browsers perfectly while 403-ing `reqwest`, `python-requests`, curl's default and empty user-agents — so your auto-updater can be dead for every user while the download page works fine, and because updater check-failures are deliberately silent, nobody will ever report it. Worse, the classifier reads your TLS/HTTP fingerprint as well as your user-agent, so curl and Node's fetch sending the IDENTICAL updater UA get 200 and 403 respectively — meaning no client your build script can call is able to prove OTA works, and every obvious way to test it gives you a confidently wrong answer.

## The setup that produces it

Any desktop app that self-updates from a static manifest:

```
https://releases.example.com/latest.json      <- updater polls this
https://releases.example.com/App_1.2.3.msi    <- updater then downloads this
```

Served from object storage (R2/S3) behind a CDN, on a subdomain of a zone with bot management enabled. Nothing about this is unusual, and nothing about it looks risky — it's a static JSON file.

The CDN doesn't know the difference between "a bot scraping my release artifacts" and "my own product asking whether it should update." It classifies on request signature, and the loudest signal is the `User-Agent` header.

## Why it fails silently, which is the actual problem

Update clients almost universally swallow check failures on purpose. Tauri's plugin, Sparkle, Squirrel — none of them surface "I couldn't reach the update server" to the user, and they're right not to: a modal every launch because someone's coffee-shop wifi is flaky would be worse than the bug.

So the failure mode is:

- Users keep running an old version.
- No error dialog, no crash, no support ticket.
- Your download page works, so manual installs succeed and *look* like proof the endpoint is fine.
- Your own dev machine updates fine if you ever tested from a browser.

There is no signal. You find this by going looking for it.

## Both obvious tests lie to you

This is the part worth internalising.

```bash
# Test 1: "let me just curl it"
curl -s https://releases.example.com/latest.json
# -> HTML: "Just a moment..." / 403
```

Conclusion you'll draw: **the endpoint is broken.** Wrong. curl's default UA (`curl/8.x`) is itself a blocked signature. You've reproduced a block that your app never hits.

```bash
# Test 2: "ok, let me use a real browser UA"
curl -s -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/140.0" \
  https://releases.example.com/latest.json
# -> {"version":"1.2.3",...}
```

Conclusion you'll draw: **the endpoint is fine, curl was just being weird.** Also wrong. You've now proven browsers work, which was never in question.

Neither test touched the thing you actually ship. So the obvious correction is "test with the exact UA string my client sends" — and that is better, but it is **still not sufficient**, for a reason worth its own section.

## The UA is not the whole classifier — and this invalidates the fix you just reached for

Measured on the same live endpoint, same day, sending the **identical** `tauri-plugin-updater/2.10.1` user-agent:

| Client | Result |
|---|---|
| curl | **200** |
| Node `fetch` (undici) | **403** |

Same header, opposite outcomes. And Node's fetch is challenged **even when it sends a full Chrome user-agent**. So the WAF is fingerprinting the client's TLS handshake and HTTP/2 behaviour (JA3/JA4-style), not just reading a header.

The consequence is uncomfortable and worth stating plainly: **no HTTP client available to your build script can faithfully impersonate the one inside your app.** curl passing proves curl passes. Node failing proves Node fails. Neither is `reqwest`-in-Tauri.

Which means:

- A script-based "OTA works" check is **not achievable**. You can verify the artifact is published, correct and reachable; you cannot verify your updater can read it.
- If you build that check anyway and call it verification, you've built the same trap as the guard that watches the wrong path — a green signal that means less than it claims.
- **The only conclusive test is behavioural:** install an older build and confirm it offers the update.

This is also why the fix below is "exempt the path," not "allowlist the UA." An exemption is a property of the endpoint and holds for every client. A UA allowlist still leaves you at the mercy of a fingerprint you don't control and can't test.

## Find the real user-agent, don't guess it

For `tauri-plugin-updater` it's built from the crate's own Cargo metadata:

```rust
// tauri-plugin-updater/src/updater.rs
const UPDATER_USER_AGENT: &str = concat!(env!("CARGO_PKG_NAME"), "/", env!("CARGO_PKG_VERSION"));
// => "tauri-plugin-updater/2.10.1"
```

So read it out of the dependency source rather than assuming:

```bash
grep -rn "user_agent\|USER_AGENT" ~/.cargo/registry/src/*/tauri-plugin-updater-*/src/*.rs
```

Then test with it — **and test the artifact download too, not just the manifest.** They're two separate requests and can be matched by different rules:

```bash
UA="tauri-plugin-updater/2.10.1"
curl -s  -A "$UA" -o /dev/null -w "manifest %{http_code}\n" https://releases.example.com/latest.json
curl -sI -A "$UA"                -w "artifact %{http_code}\n" https://releases.example.com/App_1.2.3.msi
```

Measured on a live Cloudflare zone with default bot settings (2026-07-29), **all via curl** — remember from the section above that a different client sending these same strings can get different answers, so read this as "which UAs curl gets away with," not as your app's fate:

| User-Agent | Result |
|---|---|
| `curl/8.x` (curl default) | **403** + challenge HTML |
| *(empty / no UA header)* | **403** |
| `reqwest` / `reqwest/0.12` | **403** |
| `Mozilla/5.0 … Chrome/140.0` | 200 |
| `tauri-plugin-updater/2.10.1` | 200 |

## The uncomfortable part: you're passing by accident

Note what that table actually says. `reqwest` is blocked. `tauri-plugin-updater` is not. The updater **is** a reqwest client — it just overrides the UA with its own crate name, and "tauri-plugin-updater" happens not to match any bot signature.

That is not a design decision anyone made on your behalf. It is a coincidence you are depending on. Which means:

- A plugin release that dropped the custom UA would fall back to reqwest's default and **break OTA for everyone, silently**, on a dependency bump that looked routine.
- Swapping to your own HTTP client for the update check does the same thing.
- Cloudflare tightening a managed ruleset does the same thing, with no change on your side at all.

## Two failure shapes, and the second one is nastier

**403 + HTML.** Clean-ish: the client sees an HTTP error and gives up.

**200 + HTML.** Some challenge configurations return `200` with an interstitial body. Now your updater gets a successful response containing `<!DOCTYPE html>` where it expected JSON, and fails in the parser instead of the transport. If your error handling distinguishes "network error" (retry later, stay quiet) from "malformed manifest" (something is badly wrong), this lands in the wrong bucket and stays quiet too.

## What to actually do

1. **Exempt the release path.** A WAF / Bot Management skip rule scoped to `releases.example.com/*`. This is the only fix that is a property of the *endpoint* rather than of a client you can't test, and it's the one that makes every other check meaningful. These are static public artifacts; the download link is public anyway, so there is nothing being protected.
2. **Log update-check failures somewhere you'll see them**, even while staying silent in the UI. Silent-to-the-user must not mean silent-to-you — a counter in your error reporter turns a permanently invisible bug into a graph that goes flat. Given you cannot test the client from a script, this is your real detector.
3. **Assert what you actually can at release time:** that the manifest is published, parses, names the version you just shipped, and points at an artifact that returns 200. Useful, and *not* the same claim as "the updater can read it" — label it accordingly so a green run doesn't get quoted as proof later.
4. **If you can't get an exemption, pin the UA** (`MyApp-Updater/1.2.3`) so at least a dependency bump can't change it underneath you — while remembering the fingerprint half is still outside your control.

## Update 2026-08-10: three corrections from living with this

### 1. On Cloudflare's free plan, the recommended fix does not exist

"Exempt the release path" assumes you can write a WAF custom rule with a **Skip** action. Skip cannot bypass **Bot Fight Mode**, the free-plan feature. It can only bypass **Super Bot Fight Mode**, which is Pro and up. The names differ by one word and the capability differs completely, and the dashboard does not tell you this at the point of decision — you find out from the docs after building the rule.

So on a free zone your options collapse to three, none of them the scoped exemption:

1. **Turn Bot Fight Mode off**, which is zone-wide. Often fine, because the zone in question is usually a marketing site plus a bucket of deliberately-public installers: no login, no forms, no origin server, no egress billing. Worth checking what it is actually protecting before assuming it is protecting something.
2. **Upgrade** to get the scopeable version.
3. **Move the update feed to a host without bot filtering** — your own API server, which the app already talks to. This fixes every *future* update permanently, but **cannot rescue installed copies**, because the endpoint is compiled into the binaries already in the field. One manual reinstall is unavoidable, so if you are going to do it, do it *before* the release that people will be reinstalling anyway.

Note also what Bot Fight Mode actually tests: it hands the client a **JavaScript challenge**. A desktop app has no JS engine, so it cannot pass — not "looks suspicious and gets flagged", but *structurally incapable of passing*. There is no header, UA, or good behaviour that fixes it from the client side.

### 2. The symmetry: a probe that FAILS is no more trustworthy than one that passes

The section above establishes that curl passing proves nothing about your app. The inverse is equally true and much easier to fall for, because a failure feels like discovering a bug rather than making a claim.

I built what should have been the perfect probe: a `#[test]` **inside the application's own crate**, using the app's own `reqwest` at the app's own version with feature unification identical to the shipped binary, replicating `tauri-plugin-updater`'s exact request — its UA read out of the dependency source, with and without its default `Accept: application/json`.

```
[ota] updater-shaped request: 403 Forbidden
[ota] same UA, no Accept:     403 Forbidden
```

Conclusion drawn: OTA is dead for every user. Consequence: an hour spent on stranded-user mitigation, a security-settings decision pushed at the product owner, and a ledger entry announcing an outage.

Then a real installed build self-updated, first try.

**A same-language, same-crate, same-version imitation of your client is still not your client.** Something differed — TLS backend selected at link time, connection reuse, IP reputation, per-path rules, request timing — and finding out which was never worth the effort, because the behavioural test is cheap and definitive. The rule to carry: **a probe result is evidence about the probe.** In both directions. State probe findings as "my imitation was refused", never as "the updater is broken", and let the behavioural test settle it before anyone changes their infrastructure.

### 3. If you add a runtime asset download, it will be blocked even when the updater is not

This is the corollary that bit us. The updater passes this host. Our own downloader, fetching an ML model from **the same host, the same day**, was refused — and users saw it, because unlike an update check, a user-initiated download fails loudly:

```
The download server returned 403 Forbidden for the voice model.
```

So "OTA works" tells you nothing about the next thing you host there. Any in-app fetch you add (model, dictionary, data pack, asset bundle) is a fresh client the classifier has never seen.

**The cheap insurance is a source chain with a pinned hash:**

```rust
const MODEL_SOURCES: [&str; 2] = [
    "https://releases.example.com/models/model.bin",   // ours, preferred
    "https://huggingface.co/org/repo/resolve/main/model.bin",  // upstream
];
// try in order; verify sha256 before installing whatever arrives
```

Your host first, so you are not dependent on a third party and so first-party service resumes automatically if the rule is ever relaxed. Upstream second, so a bot policy cannot take the feature down. **The pinned checksum is what makes the second source safe** — whoever serves the bytes, only the bytes you pinned are ever installed, so a fallback host is a delivery choice rather than a trust decision.

## Generalises beyond updaters

Anything non-browser fetching from a WAF-protected origin has this shape: crash-symbol uploads, license checks, telemetry, package managers pulling from your CDN, a mobile app hitting a marketing-site JSON endpoint, webhook receivers. The common thread is that **the browser path is the one you test and the library path is the one you ship**, and a WAF is specifically built to tell those apart.

## Related

- [signed-but-flagged-download-reputation.md](./signed-but-flagged-download-reputation.md) — the sibling problem on the same artifact: it's signed, it's clean, and SmartScreen warns anyway.
- [instrument-before-patching.md](./instrument-before-patching.md) — the discipline that turns "OTA seems broken?" into a measured table instead of a guess.
- [verify-the-artifact-your-user-receives.md](./verify-the-artifact-your-user-receives.md) — how to sidestep this challenge entirely when a human is in the loop: if they download from the real link and scan *that*, matching its digest against your local build proves the served bytes without any programmatic fetch of the CDN.
