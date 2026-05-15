---
stack: [mobile, ios, android, capacitor, react]
kind: decision-record
last_verified: 2026-05-14
---

# Mobile shell strategy — Capacitor vs native, and how we got it wrong twice

> A decision record for any project that's primarily a React/web app on desktop and needs a mobile presence later. We picked Capacitor, built around the assumption, then reversed to native — at non-trivial cost. This is what we learned.

## The question

You're building a product whose desktop client is React + Tauri (or similar webview shell). You want it on mobile eventually. Three plausible paths:

1. **Capacitor / Tauri Mobile / Tauri-equivalent webview wrapper.** Reuse the React codebase. One UI, three shells.
2. **React Native.** Rewrite the UI in RN's idioms. Share business logic.
3. **Native per platform.** SwiftUI for iOS, Compose for Android. Rebuild the UI twice. Share only data contracts.

Choice (1) seems obviously right for a small team. Choice (3) seems indulgent. We picked (1) initially, then reversed to (3). Here's why.

## The trap: webview parity is "good enough" until your product depends on feel

Choice (1) genuinely works if your mobile UX is informational. A reader app, a settings dashboard, a CRUD form — Capacitor gives you the iOS/Android shell, your existing React renders inside it, push notifications and biometrics work via plugins, you ship.

The trap is what "good enough" hides:

- **Native gestures don't work.** Swipe-to-go-back on iOS doesn't exist in your webview. You can fake it with touch event listeners but the inertia is wrong and users notice within minutes.
- **Native animation timing doesn't match.** iOS Spring physics are tuned to platform conventions; CSS `transition: transform` produces "similar" motion that feels off. If your product has any animation language (morphs, hero flights, spring-based UI), webview can approximate but never match.
- **Native typography rendering differs.** iOS uses SF Pro with subpixel positioning tuned to native frameworks. Webview text rendering is the WebKit/Blink pipeline — close but visibly different, especially for animated text.
- **Scroll inertia and rubber-banding.** iOS's overscroll behavior is non-trivially different from web `overflow: auto`. You can css-trick parts of it. The full behavior takes native APIs.
- **Keyboard handling.** Native keyboards animate in/out with platform-specific timing curves and offsets. Web `viewport` resizes are bolted-on and produce layout jumps.
- **Memory pressure.** Webview shells carry their entire JS runtime in memory per app. Native apps don't. On 4GB iOS devices (still supported), a webview app gets killed in the background more aggressively.

None of these matter for a CRUD app. ALL of them matter for an animation-heavy product where motion is part of the product identity.

## The reversal we made (and the cost)

**Decision 1, 2026-04-07:** "We're shipping desktop v1 first. Mobile lands via Capacitor — we'll wrap the React app. iOS bundle, Android bundle, same codebase."

We built an `apps/mobile` Capacitor shell scaffold and an `apps/web` PWA. Both shared 100% of the React UI from `packages/frontend`. Maybe a month of part-time work scoping plugins, build configs, and signing.

**Decision 2, 2026-05-04:** "Reverse. iOS will be SwiftUI native. Android will be Compose native. React stays desktop-only."

What forced the reversal: by April 2026 the desktop app's animation system was the product's main differentiator. Library-to-detail morphs, hero crossfades, "recalling a memory" UX timing. None of it could be faithfully reproduced through a webview wrapper — and the entire product pitch depended on it feeling like *this product* and not "a generic React app with a mobile chrome."

The cost of the reversal:
- ~~`apps/mobile` (Capacitor)~~ — deleted (-1 high-severity npm vuln from the xmldom dependency chain, +66 packages dropped from lockfile)
- ~~`apps/web` (PWA)~~ — deleted, was being kept current with mobile and dependent on the same flawed shared-UI assumption
- ~1 month of bookkeeping work that didn't move the v1 ship forward
- New constraint: mobile lands strictly post-desktop-v1 because the native builds are real work

What we kept:
- **`packages/core`** — Zod schemas and Worker API contract. Shared verbatim between React-on-desktop, SwiftUI-on-iOS (re-implemented as Swift types), Compose-on-Android (Kotlin types).
- The general product design — flows, screens, copy. The IA transfers; the implementation doesn't.

## When choice (1) is right anyway

We aren't saying "never Capacitor." We're saying it has a specific failure mode that's invisible until late.

Capacitor / Tauri Mobile is the right call when:
- Your product is **informational-first** (read-heavy, CRUD-heavy). Reader, dashboard, settings, project tracker.
- You have **zero custom motion/animation** as core product identity. Material/iOS defaults are fine.
- Your team is **1-3 people** and you genuinely can't afford to triple-build the UI.
- You **expect to migrate** to native if/when the product succeeds, and you're treating the webview shell as MVP infrastructure rather than the long-term answer.
- You're shipping **enterprise/B2B**, where users tolerate "different from native" if the data is right.

Capacitor is wrong when:
- Your product has a **distinct motion language** — animations, transitions, gestures — that's part of why users like it.
- Your product is **consumer**, especially on iOS, where users compare you to native apps daily.
- You're building **anything with creative tooling** — drawing, music, video, AR — where input latency and native APIs matter.
- You have **complex offline-first sync** with frequent local writes. Webview SQLite via plugins is slower than native CoreData/Room and the bridge tax adds up.

## The decision framework we'd use next time

Ask: **"If a beta user said 'this feels exactly like the desktop app — same animations, same motion, same polish' — is that the *product winning*, or is that a *bug*?"**

- If "the product winning" → webview shell is too risky. Plan native from day 1, even if you defer building it.
- If "a bug" → webview shell is fine. Ship Capacitor, focus on data/feature parity.

We assumed cross-platform parity was "the product winning." It was the opposite. The desktop app's motion was specifically tuned to feel desktop-native (fast, dense, hover-driven); mobile needed its own motion language (touch-first, vertical, gestural). Trying to share UI between platforms would have produced something that felt like neither.

## What to share between native mobile and React desktop

Once you commit to native mobile, the shared layer becomes much thinner. We share:

| Shared | Not shared |
|---|---|
| Zod schemas (`packages/core`) | UI components |
| Worker API contracts | Routing / navigation |
| Type definitions (re-implemented per-platform) | State management |
| Color palette names + values | Animation timing |
| Copy strings (eventually, via i18n) | Screen layouts |

That's it. Trying to share more (e.g. business logic via WASM) usually fails — the call-site idioms are too different. SwiftUI's `@State` and Compose's `mutableStateOf` don't compose with a JS state machine bridged via FFI. Just rewrite.

## What NOT to do

- **Don't lock yourself into Capacitor by building infrastructure that ONLY makes sense in a webview shell.** Native bridges, web-style routing, web SQLite plugins — these are all replaceable, but if you've shipped six features that depend on them, the rebuild cost is real.
- **Don't promise mobile users "same experience as desktop" if your desktop is animation-heavy.** Either build native and deliver it, or scope mobile to a different (simpler) experience and don't try to fake parity.
- **Don't reuse the React Native or Capacitor "I have a senior React dev" argument** if your senior React dev has never shipped a native iOS or Android app. The frameworks claim cross-platform but the production bugs are platform-specific, and a senior React dev doesn't have the muscle memory to fix them.
- **Don't underestimate the SwiftUI / Compose learning curve** for a team coming from React. Compose is closer to React-mental-model than SwiftUI is. Budget 4-6 weeks per platform for a senior to reach productive output from scratch.

## When to re-evaluate

Revisit the decision when:
- You hit 80% feature parity on desktop and start scoping mobile in earnest.
- The mobile platforms ship a major SwiftUI/Compose release that changes the curve (e.g. SwiftUI on visionOS opened new APIs that aren't bridgeable through webview).
- Your team grows by 1-2 people who specifically have native experience.

Don't revisit when:
- A blog post says "Capacitor X.Y is great now." Capacitor is always "great now." The trap isn't Capacitor's quality — it's the fit to motion-heavy product identity.

## References

- This decision record is grounded in a real reversal logged in `DECISIONS.md` of one project. The general framing transfers to any team picking webview-shell vs native for an animation-heavy product.
- Companion lesson: if you DO go native and need to share schemas + API contracts between platforms, see `local-first-sync-with-d1.md` for the wire-format pattern that survived native re-implementation.
