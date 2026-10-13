---
stack: [swiftui, ios, swift, animation]
kind: gotcha
last_verified: 2026-10-13
---

# Three SwiftUI traps that break shared-element flights: self-measuring loops, already-finished insertions, and fill images that size their parent

**One-liner:** (a) a view that sizes its children from its own measured width loops forever; measure the space *offered* instead. (b) a view inserted in the same transaction its animation starts appears already finished; start on the next tick and drive geometry through an `Animatable` modifier. (c) a `scaledToFill` image laid out directly in a stack sets the stack's size, silently widening pages and moving art; lay art in an `.overlay` on a fixed frame.

*Playmoir iOS, 2026-10-13: (a) and (b) in the reviewed sketch, (c) twice in the real build.*

## (a) Measuring yourself loops

Reading your own width with `onGeometryChange` and sizing children from it feeds back: children change the width, which re-measures. Measure the offered space instead: put `.frame(maxWidth: .infinity)` *before* `onGeometryChange`, so the measured box is the parent's offer, not the content.

## (b) Insert, then animate on the next tick

```swift
flight.game = game        // the flying layer is inserted at progress 0
Task { @MainActor in      // next tick: it now exists at 0
    withAnimation(.timingCurve(0.22, 1, 0.36, 1, duration: 0.52)) { flight.progress = 1 }
}
```

Animating in the same transaction as the insert renders the inserted view at its end state. And interpolate the frame yourself with an `Animatable` modifier (`animatableData = progress`, `lerp(from, to, progress)`): SwiftUI tweening two layouts bends the path and can skip the start. Under Swift 6 with MainActor default isolation, the modifier must be `nonisolated`.

## (c) Fill images size their parent

`image.resizable().scaledToFill()` reports the *filled* size (a 3840×1240 banner in a 402×161 slot reports ~498 wide). Placed directly in a `VStack`/`ZStack`, that size wins: the page grew wider than the screen (its pills ran off the right edge), and the flying copy and the page's copy of the same banner landed ~45 pt apart, so the art jumped sideways the instant the page took over. The fix, everywhere art is drawn:

```swift
Color.clear                         // takes exactly the offered size
    .frame(height: bandHeight)
    .overlay(alignment: .top) { image.resizable().scaledToFill() }
    .clipped()
```

An overlay never contributes to its host's size, so the same art lands identically in every container. Found by recording the flight and stepping through frames (see `verify-motion-frame-by-frame.md`), not by eye at full speed.

## Related

- `clip-path-shared-element-morph.md`, `compose-shared-element-overlay-covers-your-button.md` (the Compose versions of shared-element pitfalls).
