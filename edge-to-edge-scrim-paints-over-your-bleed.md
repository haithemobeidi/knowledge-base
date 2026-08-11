---
stack: [android, kotlin, jetpack-compose]
kind: gotcha
last_verified: 2026-08-11
---

# Edge-to-edge that never shows — the window IS drawing under the bar, and your own scrim is painting over it

**One-liner:** `enableEdgeToEdge()` with a coloured `SystemBarStyle` (or a theme `android:statusBarColor`) makes both of these true at once: your content genuinely renders under the status bar, AND an opaque paint layer covers the bar zone so you can never see it. Every geometry-level debugging step reads as sane — insets report correctly, layout math checks out — because the failure is not layout. It is paint.

## The symptom

"Make the hero image bleed under the status bar" appears to do nothing, repeatedly. The band gets taller by exactly the inset, insets report the right values, the wordmark centres in the right zone — and the bar area stays a flat app-coloured strip. Because every measurable geometry fact is correct, each attempt gets diagnosed as a *crop* problem, a *height* problem, an *anchor* problem. Ours burned attempts across **two separate sessions**, each ending in "the bleed isn't worth the crop" reasoning about an effect that was never visible in the first place.

## The mechanism

Two independent paint sources can cover the bar zone, and both look like "the app's background" in a screenshot:

1. `enableEdgeToEdge(statusBarStyle = SystemBarStyle.dark(someOpaqueColor))` — the scrim argument is not an icon-style hint; it is a colour the system paints behind the bar icons and **over your window content**. Passing your background colour there (a very natural reading of "pin the bars to my dark theme") re-creates a non-edge-to-edge look on top of a genuinely edge-to-edge window.
2. The platform theme's `<item name="android:statusBarColor">` — same effect, applied before Compose even starts, so it also covers the cold-start frame.

The trap is that `enableEdgeToEdge` did its job: the window extends, `WindowInsets.statusBars` reports the real inset, `statusBarsPadding()` works. Everything an engineer would probe to verify "am I edge-to-edge?" answers **yes**. The only wrong thing is a paint layer no layout query can see.

## The fix

Both sources go transparent; legibility over art becomes your content's job (a top gradient under the clock):

```kotlin
enableEdgeToEdge(
    statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT), // dark() = light icons
    navigationBarStyle = SystemBarStyle.dark(barColor), // each bar decided separately
)
```

```xml
<item name="android:statusBarColor">@android:color/transparent</item>
```

Screens that should NOT bleed simply keep their own `statusBarsPadding()` and show the window background there — a transparent bar costs them nothing.

## The ten-second identification

When a "draw under the bar" change appears to do nothing: **screenshot, then ask what the bar zone shows.** Cropped content = geometry problem, debug layout. A flat colour that matches your theme = paint problem, and no amount of height/crop/anchor work can ever fix it. Do this check FIRST — it is the difference between one minute and two sessions.

## The general rule

**A layout probe cannot detect a paint occlusion.** When an effect that "should be visible" isn't, verify the pixels before the geometry: something above your content in z-order may be honestly painting exactly what it was told to. Sibling of the LocalContentColor lesson — same platform, same family ("presents as one class of bug, is actually paint"), different layer.

## Related

- [[compose-invisible-text-localcontentcolor]] — the same "debugged as X, was actually paint" family: there the paint was black-on-black text; here it is a scrim over a bleed. In both, every structural probe answered "correct."
- [[negative-control-before-trusting-a-probe]] — the epistemics of why the geometry checks kept passing: they were probing a layer that was never the broken one.
