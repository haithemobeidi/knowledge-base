---
stack: [android, kotlin, compose, gestures, ux]
kind: gotcha
last_verified: 2026-09-20
---

# A custom press-and-hold on top of `detectTapGestures`: you now own two thresholds, and each one fails differently

**One-liner:** Compose's `detectTapGestures` knows one boundary, the platform long-press timeout (~400 ms). An app that starts its own hold visual earlier (so a held cover "lifts" at 100 ms) creates a gap between its threshold and the platform's. **Failure 1:** a release inside that gap shows the hold, then still fires `onTap`, so the game opens. **Failure 2:** once that's fixed ("a release after the hold took is never a tap"), a hold threshold that's too short turns ordinary deliberate taps into dead holds that open nothing. Two guards fix the first; a threshold above a normal tap (250 ms) fixes the second.

*Playmoir Android library wall, 2026-09-19 → 09-20 (M-35, M-37). Both failures found by the user on the device; the final timings tester-verified on the Pixel Fold (taps of 0/150/220 ms open, holds of 350/600 ms don't); user: "that's better".*

## Failure 1: the gap between your threshold and the platform's

The app's hold begins from `onPress` after its own delay (Playmoir's `HoldToRecall.kt`, verbatim apart from comments):

```kotlin
pointerInput(Unit) {
    var recalled = false   // set the moment the hold takes, long before any release
    detectTapGestures(
        onPress = {
            recalled = false
            // A release or a scroll's cancel inside the window returns a value;
            // only the timeout comes back null.
            val ended = withTimeoutOrNull(PmMotion.HoldDelayMs.toLong()) { tryAwaitRelease() }
            if (ended == null) {
                recalled = true
                haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                held(true)
                tryAwaitRelease()
                held(false)
            }
        },
        onLongPress = {},                       // guard 1: swallows the click past the PLATFORM timeout
        onTap = { if (!recalled) tap() },       // guard 2: a release after OUR hold is never a tap
    )
}
```

Without the `recalled` guard, a press released at ~300 ms had shown the full hold visual and then opened the game ("sometimes i open up a game"). **Two guards, because the platform only knows one boundary:** the empty `onLongPress` swallows the click past ~400 ms, and `recalled` swallows releases between your delay and that.

## Failure 2: your threshold is below a normal tap

With `HoldDelayMs = 100` plus the new rule, any tap longer than 100 ms, which is an ordinary deliberate tap, became a hold that opened nothing. The user: "cards aren't always opening right away, tapping them and nothing happens". Ruled: **250 ms**, above a deliberate tap and under the platform's long-press. The alternatives were declined: 400 ms (holds feel sluggish) and "releases under 300 ms still open" (the gap comes back).

## The rules

- Your hold threshold must sit **above the longest normal tap (~200–250 ms)** and **below the platform long-press (~400 ms)**.
- Once your hold has visibly taken, **the release must never count as a tap.** Track it in a flag reset at each press.
- Keep an empty `onLongPress` so the platform's own long-press doesn't fall through to a click.
- The delay is also what lets a scroll that *starts* on a cover not lift it. Don't start the hold on touch-down.
- Time it on the real device with a tester at fixed durations (0, 150, 220, 350, 600 ms) instead of feel alone.

## Related

- `layout-shift-mid-press-eats-the-click.md`: the web's press/click boundary trap.
- `motion-design-token-system.md`: where the hold delay constant lives with the other tempos.
