---
stack: [chrome-extension, manifest-v3, typescript]
kind: pattern
last_verified: 2026-08-11
---

# MV3 fetch bridge: run privileged fetches in the service worker, ride the user's session cookies — and know the four traps in the plumbing

Extracted from the Muck Rack Support Assistant extension, where a side panel
scrapes an authenticated Django admin the user is already logged into. There
is no API and no token to store: the session cookie in the browser's jar IS
the auth. A reusable implementation lives in the sibling `mv3-fetch-bridge`
project (same Vibe Projects folder; path is environment-specific).

## The inversion worth naming: extensions are the one place cookies ARE your auth

Three lessons in this KB ([tauri-desktop-oauth](./tauri-desktop-oauth.md),
[cloudflare-worker-setup](./cloudflare-worker-setup.md),
[local-first-sync-with-d1](./local-first-sync-with-d1.md)) say "don't rely on
cookies from a native app — separate cookie jar, use bearer tokens." A Chrome
extension service worker is the exact inverse: it runs INSIDE the browser
that owns the jar. `fetch(url, { credentials: 'include' })` from the service
worker, with a matching `host_permissions` entry, sends the user's live
session cookies — no stored credentials, no OAuth dance, no token refresh. If
the user is logged in in a tab, your extension is logged in. Both rules are
the same rule: make the request from the context that already holds the
credential.

Manifest notes that took real digging: `host_permissions` is what grants BOTH
the CORS exemption and cookie attachment for extension-page fetches. The
`cookies` permission is unrelated — that gates the `chrome.cookies` API only.
And don't bother with cookie-filtering middleware in front of the fetch; we
had one and deleted it as security theater. The extension context is already
privileged; the real controls are the URL allowlist and rate limiting.

## Route every caller through ONE service-worker handler

Content scripts are CORS-bound to their page's origin — a cross-origin fetch
from one simply fails, so they need the bridge. Extension pages (side panel,
popup) technically could fetch directly with host permissions, but routing
them through the same handler puts URL policy, rate limiting, cancellation,
and security telemetry at one choke point instead of N call sites. Same shape
as [byo-api-key-client-direct-tier](./byo-api-key-client-direct-tier.md)'s
rule: fork at one low branch point, never per-caller.

The protocol is a request/response pair over `chrome.runtime` messaging:

```ts
// Caller (side panel / content script)
const response = await chrome.runtime.sendMessage({
  action: 'fetch',
  requestId: crypto.randomUUID(),  // unique — keys the worker's abort map
  url,
  options: { method: 'GET', credentials: 'include', timeout: 20000 },
});

// Service worker
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action !== 'fetch') return;      // let other listeners run
  void handleFetch(message, sendResponse);
  return true;  // ← MANDATORY: keeps the sendResponse channel open async
});
```

Forget the `return true` and the caller gets "The message port closed before
a response was received" — the classic MV3 messaging bug. Give responses a
discriminant (`ok: true/false`) and a typed `errorType`
(`security | rateLimit | timeout | abort | auth | network`) so callers switch
on a field instead of sniffing an untyped object for `.error`.

## Trap 1: you will never see a 302 — detect auth redirects from `redirected` + final URL

Our bridge had an auth branch on `response.status === 302 || 301` that looked
right in review and was dead code in production. `fetch` defaults to
`redirect: 'follow'`, so the service worker never observes a 3xx: a
302-to-login resolves transparently and arrives as a **200 from the login
page**. (`redirect: 'manual'` is no help — extension fetches get an
`opaqueredirect` with status 0 and no Location.) The caller had already
grown a workaround comment: "A 302 to the login page can resolve
transparently, so confirm the final URL still points at the object we asked
for."

The honest detection:

```ts
if (response.redirected && isAuthRedirect(new URL(response.url))) {
  sendResponse({ ok: false, errorType: 'auth', finalUrl: response.url });
  return;
}
// isAuthRedirect is site-specific config, e.g.
// (u) => u.pathname.startsWith('/accounts/login')
```

Always return `finalUrl` to callers regardless — belt-and-suspenders checks
like "does the final URL still contain `/<id>/`?" catch redirect flavors the
predicate doesn't know about.

And per [db-backed-auth-503-not-401](./db-backed-auth-503-not-401.md): only
`errorType: 'auth'` may drive "session expired" UI or teardown. `network` and
`timeout` mean *could not find out* — treat them as auth and a flaky request
signs your user out.

## Trap 2: a per-URL rate limiter cannot pace a batch — limit by host, pace in the caller

The bridge rate-limited 60/min **per exact URL string**. Then a bulk-lookup
feature arrived that resolves N admin object IDs — N *distinct* URLs on one
host — and the limiter provided zero throttle by construction. The fix is
two-sided:

- **Worker:** bucket the sliding window by *hostname*, not URL.
- **Caller:** the limiter *refuses* excess requests, it does not queue them —
  so a batch caller that fires 250 lookups gets ~60 results and ~190
  `rateLimit` errors. Batch features own their pacing: a small concurrency
  pool (we use 4 in-flight against production admin) plus a hard batch cap
  (250) so a careless paste can't hose the target site.

## Trap 3: `chrome.runtime` messages are JSON — an ArrayBuffer arrives as `{}`

Chrome JSON-serializes runtime messages. The bridge's binary branch
(`data = await response.arrayBuffer()`) type-checked, ran, and delivered `{}`
to the caller — silently. Base64-encode binary bodies and flag them
(`dataEncoding: 'base64'`); encode in chunks, because
`String.fromCharCode(...allBytes)` overflows the call stack on large bodies.
Messages also have a hard size cap (tens of MB) — the bridge is for pages and
API payloads, not file downloads.

## Trap 4: half your browser-cosplay headers are silently dropped

The bridge shipped a lovingly forged header set: `Sec-Fetch-Site`,
`Sec-Fetch-Mode`, `Accept-Encoding`, `Upgrade-Insecure-Requests`, the lot.
`Sec-*` and `Accept-Encoding` are forbidden header names — fetch drops them
without an error, so most of that block was decoration. The headers that
actually changed server behavior:

- `Accept: text/html,...` — ask for full pages.
- `X-Requested-With: XMLHttpRequest` — Django-style backends return
  *different HTML* (AJAX partial vs full page) based on it. We send it for
  admin lookups and must OMIT it for article searches, which need the full
  page. The header set is part of your scraping contract with the site, per
  endpoint — not global fetch config.

## Validate hostnames structurally; `includes()` is an allowlist hole

`parsedUrl.hostname.includes('muckrack.com')` matches
`muckrack.com.evil.net`. Compare the parsed hostname for exact equality
against the allowlist, use **anchored** patterns (`/^[a-z0-9-]+\.example\.com$/i`)
for dynamic subdomains, and run private-infrastructure checks on the parsed
hostname — not regexes over the whole URL string (`/10\./` happily matches a
path segment like `/v10.2/`). Deny by default; block loopback, RFC-1918,
link-local (which covers cloud metadata at 169.254.169.254), CGNAT, IP
literals, and internal TLDs (`.local`, `.internal`, `.lan`, `.corp`) even for
allowlisted requests — defense in depth against a sloppy pattern.

## Arbitrary-host probe mode is only safe because it never returns a body

One feature (an HSTS header checker) must fetch domains the *user types in* —
a fixed allowlist can't work. The safe shape couples two decisions into one
mode: validation loosens to "any named public HTTPS host" (no IP literals, no
localhost, no bare names, no internal TLDs), AND the response body is never
read — only status + headers come back, and a non-2xx still returns them (a
site can 403 bots and still send `Strict-Transport-Security`). DNS rebinding
is deliberately not defended: a public name resolving to a private IP would
yield an attacker three header booleans. If you ever return the body in this
mode, you've built an SSRF proxy.

## When NOT to use this

- **The site has a real API you can hold a token for.** Session-cookie
  scraping is for sites that don't (internal admin panels, your own SaaS
  backoffice). Slack and Linear have proper APIs; use them.
- **Outside the user's browser** (server-side jobs, CLI) — there's no jar to
  ride; that's the Tauri lessons' territory.
- **Bulk binary transfer** — message size cap; use `chrome.downloads` or
  direct navigation.
- HTML scraping breaks when the site's markup changes; keep extraction
  functions pure and unit-tested so the break is loud and local.

## Related

- [db-backed-auth-503-not-401.md](./db-backed-auth-503-not-401.md) — the
  "can't know ≠ not authorized" rule the error taxonomy encodes.
- [byo-api-key-client-direct-tier.md](./byo-api-key-client-direct-tier.md) —
  same structural argument (privileged context + one branch point), token
  flavor.
- [tauri-desktop-oauth.md](./tauri-desktop-oauth.md) — the cookie-jar rule
  this pattern inverts.
