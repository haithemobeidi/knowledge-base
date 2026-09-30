---
stack: [android, kotlin, oauth, auth, custom-tabs]
kind: gotcha
last_verified: 2026-09-26
---

# Android sign-in in a Custom Tab / Auth Tab: the provider's own app can hijack the login page, the tab closes, and "tab closed" is not "user cancelled"

**One-liner:** signing in with Steam through an Auth Tab worked for the developer and failed for a real user: Steam's page said "Incorrect login", Steam's server had verified him four times, and the app created no session. The Steam app holds a **verified App Link** for `steamcommunity.com`, so an **unpinned** tab launch is an implicit intent Android can hand to the Steam app. The tab closes, the Steam app approves and sends the answer back later through the app's `playmoir://signin` deep link, but the closed tab's non-OK result had already deleted the pending attempt. Fix: **pin the tab to the browser package**, and **keep the pending attempt when the tab closes** until it expires.

*Playmoir Android, 2026-09-23 (M-91), hotfix 1.1.1. Proof: on 2026-09-26 the affected user signed in on the fixed build and the server recorded his session and library a second later. (An earlier "fixed" verdict on 09-23 was wrong: he was still on the old build. Check the client version in the logs before closing.)*

## The sequence (Pixel Fold logcat)

1. The Auth Tab loads `steamcommunity.com`'s login page.
2. Chrome hands the link to the **installed Steam app** (verified App Link), and **the tab closes**.
3. The Steam app approves the login and opens the callback in plain Chrome, which fires `playmoir://signin` into the app.
4. But the closed tab's result had run `cancelSignIn()`, deleting the persisted attempt, so the real answer found nothing to finish.
5. A second attempt stays in the tab and works. Why the hop happens only on the first try is **not known**.

## The fix, two layers

```kotlin
// 1. Pin: an intent that names the browser package stays in the browser,
//    "even through redirects" (Chromium's external_intents README).
authTabIntent.intent.setPackage(browserPackage)
customTabsIntent.intent.setPackage(browserPackage)   // the Custom Tab fallback too
```

2. **A closed tab is not proof of cancel.** The tab's result resets the screen but **keeps the attempt on disk until it expires**. Only the user's own Cancel or a new attempt drops it, so a late deep-link answer still completes.

AppAuth-Android does the same pin (`intent.setPackage(mBrowser.packageName)`). The research also found that AppAuth decides "cancelled" in `onResume` with no grace period, and drops a late redirect with "No stored state - unable to handle response" (several open issues). An unrelated Steam-on-Android project hit the same Steam-app hijack. Auth Tab hardens the *return* leg, not the outbound login page, so switching to Auth Tab alone doesn't fix this.

Verified: 3/3 fresh-install first-try sign-ins, zero Steam-app launches, 4 sign-ins = 4 sessions server-side.

## Related lessons from the same sign-in move (loopback → Auth Tab + custom scheme + PKCE)

- **Persist the pending attempt to disk, encrypted.** The OS may relaunch the app for the deep link, but not its memory of what it was waiting for.
- **PKCE must be required, not optional, in app mode.** The first deploy let a request without a challenge mint an unbound code, a PKCE downgrade. Closed by requiring the challenge.
- **Probe the real chain.** The same deploy broke *desktop* sign-in, because the callback was tested with a hand-built URL instead of the one `/start` actually produces.
- **Check the premise.** "Google deprecated loopback on Android" was about Google's own OAuth clients. RFC 8252 names a custom scheme or claimed https for Android, and loopback for desktop.

## Related

- `tauri-desktop-oauth.md`: the desktop loopback half.
- `negative-control-before-trusting-a-probe.md`: probe the real chain.
