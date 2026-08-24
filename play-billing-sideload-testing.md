---
stack: [android, google-play, play-billing, payments]
kind: gotcha
last_verified: 2026-08-23
---

# Play Billing on sideloaded builds: queries work, purchases fail — until the account installs the app from a Play track ONCE

**One-liner:** `queryProductDetailsAsync` happily returns live localized prices on a sideloaded debug build, but `launchBillingFlow` dies with "the item you were attempting to purchase could not be found" — because purchases are checked against the Google *account's* Play library, which a sideload never writes to; one install from any test track (internal is fine) stamps the account permanently, and after that sideloaded dev builds can purchase for the rest of the project.

## The symptom

A dev build installed over ADB, package name identical to the Play Console app, subscription product ACTIVE, the Google account on the device registered as a license tester. The subscribe screen renders Google's real localized prices — so the store clearly sees the app and the product. Tap buy, Google's sheet opens, and immediately: **"the item you were attempting to purchase could not be found."**

Everything you can check says it should work, and half of it *does* work, which is what makes this a dead end: the price query succeeding convinces you the wiring is fine and sends you off auditing product IDs, offer tokens, and signing configs. None of those are the problem.

## The cause

Catalog reads and purchases go through different doors. `ProductDetails` is public catalog data, keyed by package name — any build can read it. A purchase is authorized against the **Google account's Play library**: "does this account have this app, via Play?" A sideloaded install never creates that record, so the purchase backend answers "you don't own this app" — surfaced as item-not-found, not as anything that names the actual problem.

## The fix (one-time, per account)

1. Put a build on any test track — **internal testing is fine** and has no review delay.
2. Opt the device's Google account into the track (the opt-in URL) and **install the app from Play once**.
3. That's it, forever: the library record is account-side and permanent. You can uninstall the Play copy immediately; sideloaded debug builds purchase fine from then on.

The wrinkle: the Play-delivered build and your debug builds carry different signatures, so neither installs *over* the other — full uninstall between them, both directions. Plan for the local-data loss (a cloud-synced app just rebuilds after sign-in; a local-only app should export first).

The Play-track build can be weeks stale — it only exists to write the library record. Measured: our track carried a build with **no billing code at all**, and the sideloaded dev build purchased fine afterwards.

## What license-tester mode then gives you (all measured)

- **Compressed periods**: a monthly plan renews about every **5 minutes**, an annual about every **30** (the sheet literally prints "$5.00/5 min"). The sub renews a few times and then expires on its own within the hour. This is a free, fast test of the entire renewal → expiry pipeline: our server's RTDN receiver got the ACTIVE push within seconds of purchase, renewal events on the compressed clock, and the expiry closed the entitlement window ~30 minutes in — the app's UI visibly flipped states without anyone faking anything.
- **Trust `expiryTime`, don't compute it**: with compressed periods, any client or server code that derives "one month from now" is instantly wrong. Grant exactly the window Google's verify response reports and the compression is invisible to your logic.
- **Test card, no money**: the sheet shows "Test card, always approves"; nothing is charged, and Google auto-refunds any purchase you never acknowledge after 3 days (which doubles as the backstop while your server-ack road is under construction).

## Related traps in the same session, one line each

- **Device-side price caching**: after changing a price in Play Console, the purchase *sheet* shows the new price immediately but `ProductDetails` can serve the old one for minutes-to-hours. The sheet is the truth; don't debug your query code.
- **Play Console price entry nudges to .99**: enter "$5" and what saves may be $4.99 (the suggested-price pattern). If you want flat pricing, check what the base plan actually holds. The bulk "Set prices" dialog also ignored programmatically-set input in our automation — the inline per-country row edit is the road that reliably sticks.
