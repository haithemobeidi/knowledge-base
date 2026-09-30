---
stack: [android, kotlin, compose, animation]
kind: gotcha
last_verified: 2026-09-22
---

# Compose shared-element transitions: the flying art is drawn above both screens, so a button inside its frame sits under it

**One-liner:** during a Compose shared-element navigation, every shared element is drawn in the **overlay above both pages** for the whole transition. A control that is *not* shared but sits inside the flying element's frame (a "Game page ›" button on a banner) is left in the page, so the arriving art covers it: it looks dim, dims further as the art fades in, then pops to full when the overlay lets go. Six fixes that tuned the button's own animation couldn't change anything. The fix is one modifier that lifts the control into the overlay while its page is arriving: `renderInSharedTransitionScopeOverlay(zIndexInOverlay = 1f)`. The same screen held two more transition traps, covered at the end.

*Found and fixed in Playmoir's Android app, 2026-09-22 (M-75); filmed on the device before and after; user-verified "fixed".*

## Symptom

The user: "it is rendering for a moment then unrendering, then rerendering when the page settles - there is an extra render in between." The door button on the Memoir day band flickered when navigating from a game page. The art and the game's wordmark beside it never blinked.

## The six attempts that could never have worked

All measured, all reverted:

| Attempt | What it assumed |
|---|---|
| give the door its own `sharedBounds` flight | the door needed to fly too |
| `sharedElement` instead of `sharedBounds` | the wrong kind of flight |
| gate the overlay on having a partner | an unmatched flight was the problem |
| stop inheriting the band's landing entrance | the entrance animation was fighting it |
| let the door ride the overlay with enter/exit `None` | a different overlay setup |
| no parent clip (`NoOverlayClip`) | the overlay was being clipped |

Two research passes backed a plausible theory: remeasure-to-bounds on the band plus parent clipping across *nested* `SharedTransitionLayout`s, which is undocumented territory. It was wrong. **The proof that ended it:** with the door's own shared-element flight switched **off**, the film was identical (the door's brightness sat at 12–22 through the transition against 155 settled, with a one-frame step at the end). None of the tuning touched the cause.

The clue had been there from the start: the wordmark beside the door used the same band and the same entrance modifier and never blinked. **The only difference was that the art above it flies.**

## Cause

A shared-element flight draws the art in the `SharedTransitionScope` overlay, above both pages, for the length of the navigation. The door stayed in the page, inside the art's frame, so for the whole flight it sat *under* the arriving art.

## Fix

```kotlin
fun Modifier.aboveFlight(): Modifier = /* inside the shared-transition + animated-visibility scopes */
    renderInSharedTransitionScopeOverlay(
        zIndexInOverlay = 1f,
        // only while ITS page is arriving; a leaving page's door stays in the page
        renderInOverlay = { isTransitionActive &&
            animated.transition.targetState == EnterExitState.Visible },
    )
```

`renderInSharedTransitionScopeOverlay` is the documented way to keep a non-shared element on top during a shared transition. Verified on film: full brightness from the first frame, steady in both directions.

## Two more traps from the same screen

**1. Staggered child entrances lengthen the parent transition.** Each row under an opened day used `animateEnterExit` with a delay of index × stagger. In an `AnimatedContent`, the transition counts as running until its **longest child** finishes, so a hundred rows kept it "entering" for ~5 s. A row composed inside that window by a fast fling waited out its whole delay, invisible ("if I scroll down fast, the page never loads; slower, it loads"). **Fix:** cap the stagger at about one screen (`index.coerceAtMost(12)`); rows past the cap drop in together.

**2. A partner that appears in the same state change isn't registered yet.** Switching from one open day to another, the tapped strip should fly into the new band. But the strip only *became* a flight end through the same state change that started the switch, so the new band looked for its match before the strip had registered, and entered alone. **Fix:** set the flight id first, wait two frames (`withFrameNanos {}` twice), then change the state that starts the transition. User: "perfect".

**Also:** lazy lists that prefetch a viewport ahead (`LazyLayoutCacheWindow`) run a row's `LaunchedEffect`/`DisposableEffect` **before it's visible**, so never use an effect as a visibility signal.

## The method that found it

Film the transition (`film-it-adb-screenrecord.md`), measure the thing the user describes, and **switch the suspect off to see whether the film changes**. That's a negative control (`negative-control-before-trusting-a-probe.md`). A one-number metric ("how long is the door absent?") can't see a three-state bug; four fixes moved that number while the user saw no change.

## Related

- `clip-path-shared-element-morph.md`: the web version of shared-element motion.
- `compose-nav-flag-lifetime-first-flight.md`: another shared-element failure, the first flight after a cold start.
