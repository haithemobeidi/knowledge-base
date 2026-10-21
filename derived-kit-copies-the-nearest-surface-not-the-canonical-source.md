---
stack: [any, branding, design-systems, llm-agents]
kind: gotcha
last_verified: 2026-10-21
---

# A derived kit copies the nearest surface, not the canonical source — check every surface before writing a brand rule

**One-liner:** When you build a new kit (a social-media agent, a slide template, a press pack) you take the brand from whatever surface is open in front of you, usually the website. If that surface has drifted from the product, the kit freezes the drift into a *rule*, and the rule then reads as authority. Before writing any brand rule into a derived kit, read the canonical source and list every surface that draws the thing, then write down which one wins.

## The shape

A product has a canonical brand source (here `docs/design/brand/playmoir-mark.svg`, the mark only) and several surfaces that each draw the full logo by hand: three app clients, a website, a social banner. One surface (the website, rebuilt last) drew the wordmark differently from all the others. A new marketing kit was written from the website's CSS, and its brand guide said "the wordmark is lowercase. **Never uppercase.**"

Weeks later the kit's own app-feature videos showed "PLAYMOIR" in capitals, and the brand guide flagged them as the violation. They weren't: the videos matched the three apps and the banner. The website was the outlier, and the kit had copied it.

The tell: a rule in a derived document that is *stricter* than anything in the source it claims to follow. Nobody wrote "never uppercase" against the apps; the kit invented it from one sample.

## What to do

1. **Find the canonical source first** (a `brand/` folder, a design-token file, a decision log entry). If it only covers part of the thing (the mark but not the wordmark), say so: the gap is exactly where drift lives.
2. **Grep every surface that draws it** before writing the rule. For a wordmark: the app clients' launch and sign-in screens, the site nav, banners, store art, existing exports. Count which version each uses.
3. **Write the census into the rule**, not just the conclusion: "the apps and banner use X, the site uses Y, X wins because …". A future reader can then tell a real violation from the outlier.
4. **Make the logo one file.** A wordmark retyped in CSS, Compose, SwiftUI and an HTML template will drift again. An outlined master (SVG with the text converted to paths) is the only form every surface can use without re-deriving it.
5. **Separate the logo from the type around it.** "One logo everywhere" and "one font everywhere" are different decisions; the first is cheap and high-value, the second has no objective backing (one recognition study concerns altering the logo itself; the "+23% revenue from consistency" figure is a vendor survey of marketers' estimates).

## Case (Playmoir, 2026-10-21)

Census taken only when the contradiction surfaced: desktop `BootGate.tsx` (Orbitron, `uppercase`), Android `OnboardingSteps.kt` and iOS `SignInScreen.swift` (Orbitron Black PLAY/MOIR), the X banner (the same) versus the site nav (Inter Tight, lowercase). The kit's agent had been told the outlier was the rule. Ten variants were mocked side by side and the owner picked a third option (title case "Playmoir" in the app's text font), so the census also showed that neither existing version was obviously right: the drift had hidden a real, open brand decision.

Related: [[news-graphics-from-research-and-official-art-not-an-image-model]].
