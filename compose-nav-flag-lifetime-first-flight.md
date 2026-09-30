---
stack: [android, kotlin, compose, navigation, animation]
kind: gotcha
last_verified: 2026-09-22
---

# The first shared-element flight after every cold start was a teleport: a flag written during composition, then a fix that ended it too early

**One-liner:** a Compose nav host gated its shared-transition scope on a `flightActive` flag that was *assigned inside* the `enterTransition`/`exitTransition` lambdas and *read in the same composition* by each screen. On a cold process start the flag was still false when the screen being left composed, so its tile never registered as one end of the flight, and the cover just appeared at its destination. After that the flag was stuck true, so every later navigation worked. The first fix derived the flag from the route and broke the **return** flight; the second derived it from `NavController.visibleEntries`, which lives exactly as long as the transition.

*Playmoir Android, 2026-09-22 (M-81). Both rounds filmed on a cold start; the user found round 1's regression.*

## Symptom

"The FIRST animation ... is pretty much always broken, like 'not started up' like a cold boot" (the user, with two videos). Frame timings looked fine: 22.7 ms cold against 19.9 ms warm. **A timing instrument can't see a missing animation;** only a recording showed it. Three hours of instrumentation had also missed it for a second reason: every repro went Home → game page, and Home already shows the banner in nearly the same place.

## Round 0: state written during composition

```kotlin
var flightActive by remember { mutableStateOf(false) }
// assigned inside enterTransition / exitTransition, read by each screen's
// LocalNavAnimatedScope provider in the SAME composition pass
```

A shared element needs **both** ends inside the scope. On the first navigation, the leaving screen composed before the flag flipped.

## Round 1: derived from the route, with the wrong lifetime

`route == DETAIL || prevRoute == DETAIL`, with `prevRoute` written in a `SideEffect`. That fixed the outbound flight. On the **return**, the route becomes `library` immediately while the flight is still flying, and the remembered previous route updates a beat later, so the flag went false **mid-animation** and tore the scope down. The user: "return animation to the library looks borked now".

## Round 2: derived from what the navigator itself holds for the transition

```kotlin
val flightActive = route in BannerRoutes ||
    visibleEntries.any { it.destination.route in BannerRoutes }
```

`navController.visibleEntries` contains both ends of a transition for exactly as long as it runs, so the flag's lifetime is owned by the thing that knows. The route test stays in front of it so a frame of lag in the flow can't cost the outbound flight its first frame.

**Why fly between two pages that show the same banner at all:** without a flight, the two pages crossfade two identical pictures, and two partial alphas composite to *less* than one, so the banner visibly dims mid-transition ("memoir -> entry and back is the worst offender"). A flight draws **one** copy in the overlay above both pages, which can't dim (see `crossfade-luminance-gap-and-view-transitions.md` for the same effect on the web).

## The rules

1. **Never write state inside composition or a transition-builder lambda that a sibling reads in the same pass.** The reader sees the old value on the first frame.
2. **Derive a transition gate from state whose lifetime matches the transition** (`visibleEntries`, `Transition.isRunning`), not from "current plus previous route" bookkeeping.
3. **Always test the first navigation after a cold process start**, in both directions, on film. Warm repros and frame-time metrics hide this class.

## Related

- `derive-dont-track-ui-flags.md`: the same "derive, don't track" principle for React UI flags.
- `lifted-composable-captures-state-value.md`: the same `flightActive` flag, earlier, captured by value at graph build.
- `compose-shared-element-overlay-covers-your-button.md`, `film-it-adb-screenrecord.md`.
