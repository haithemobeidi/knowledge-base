---
stack: [cloudflare, tauri, rust, release-engineering, reliability]
kind: gotcha
last_verified: 2026-07-29
---

# Your CDN's bot challenge blocks library user-agents, and an auto-updater is a library user-agent

**One-liner:** put your update manifest behind Cloudflare (or any WAF with bot management) and the endpoint will serve browsers perfectly while 403-ing `reqwest`, `python-requests`, curl's default and empty user-agents — so your auto-updater can be dead for every user while the download page works fine, and because updater check-failures are deliberately silent, nobody will ever report it. Worse, the two obvious ways to test it both give you the wrong answer.

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

Neither test touched the thing you actually ship. The only test that means anything uses **the exact UA string your client sends**.

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

Measured on a live Cloudflare zone with default bot settings (2026-07-29):

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

1. **Test with the shipped UA in CI, not by hand.** One curl per release, asserting `200` on both manifest and artifact. It's a two-line check that catches a silent total failure.
2. **Exempt the release path explicitly** rather than relying on a lucky UA — a WAF skip rule or Bot Management exception scoped to `releases.example.com/*`. These are static public artifacts; there is nothing to protect, and the download link is public anyway.
3. **If you must pass by UA, pin it.** Set an explicit user-agent you control (`MyApp-Updater/1.2.3`) so a dependency bump can't change it underneath you, and allowlist that string.
4. **Log update-check failures somewhere you'll see them**, even while staying silent in the UI. Silent-to-the-user should not mean silent-to-you — a counter in your error reporter turns a permanently invisible bug into a graph that goes flat.

## Generalises beyond updaters

Anything non-browser fetching from a WAF-protected origin has this shape: crash-symbol uploads, license checks, telemetry, package managers pulling from your CDN, a mobile app hitting a marketing-site JSON endpoint, webhook receivers. The common thread is that **the browser path is the one you test and the library path is the one you ship**, and a WAF is specifically built to tell those apart.

## Related

- [signed-but-flagged-download-reputation.md](./signed-but-flagged-download-reputation.md) — the sibling problem on the same artifact: it's signed, it's clean, and SmartScreen warns anyway.
- [instrument-before-patching.md](./instrument-before-patching.md) — the discipline that turns "OTA seems broken?" into a measured table instead of a guess.
