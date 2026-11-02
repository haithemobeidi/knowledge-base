---
stack: [tauri, rust, csp, security, images]
kind: gotcha
last_verified: 2026-11-01
---

# A new image host has to clear every allowlist, not just the one you can see working

**One-liner:** In a Tauri app the webview's Content-Security-Policy (`img-src`) and any Rust-side fetch allowlist are two separate gates. Move images to a new host, and the CSP can already allow it (a wildcard), so the pictures appear and everything looks done, while the native code that downloads the same bytes for another job (colour extraction, thumbnails, caching) refuses the host and skips it without an error. When an app changes asset hosts, grep for every allowlist instead of trusting the one that visibly works.

## The shape

Playmoir moved its cover art from Steam's flat CDN (`cdn.cloudflare.steamstatic.com/...`) to Steam's hash-addressed URLs on `shared.steamstatic.com`. The CSP's `img-src` already allowed `https://*.steamstatic.com`, so the webview loaded the new URLs at once. Covers showed. By eye the change was complete.

The app also picks an accent colour per game from its cover. That runs in Rust: `game_accents.rs` downloads the image bytes itself and checks the URL's host against `ALLOWED_REMOTE_HOSTS`, an exact-match list. The list named two hosts, and `shared.steamstatic.com` wasn't one of them. Every hashed URL would have been refused. Extraction treats a failed source as "try the next one", so the result would have been accents quietly falling back to defaults, with no error, no log worth noticing, and nothing for a tester to see except "the colours feel off".

It was found by reading the code before the change shipped, and fixed by adding the host to the Rust list.

## Why it hides

- The two gates guard different things. The CSP limits what the webview may load; the native allowlist limits what your own process may fetch (usually there so a URL handed over by the frontend can't make the app fetch anything it likes). Neither knows about the other.
- One is a wildcard and one is exact, so they diverge exactly when a new subdomain appears.
- The visible consumer (the `<img>`) passes, and the consumer that fails is a background job built to degrade quietly.

## The rule

When an asset moves to a new host, search for every place a host is named before calling it done:

- the CSP in `tauri.conf.json` (`img-src`, `connect-src`, `media-src`);
- native fetch allowlists in Rust (`ALLOWED_*`, `allowed_hosts`, URL parsing followed by a host match);
- any HTTP-scope permissions (`http:default` scopes in capability files);
- service-worker or cache routes, and server-side proxies.

Then test the consumer that can't be seen, not just the one that can: here, confirm an accent actually changes for a game whose art is only on the new host.

Related hardening, from the same review and not yet applied there: a host allowlist checked only on the first URL can be walked around by a redirect. Set the native client to follow no redirects (reqwest: `redirect::Policy::none()`), or re-check the host on every hop.

## Related

- [[tauri-desktop-security-hardening]]: the CSP and scope checklist this sits beside.
- [[dev-path-fallback-hides-missing-bundled-asset]]: another quiet fallback that made a broken path look fine.
