---
stack: [css, animation, web]
kind: pattern
last_verified: 2026-10-02
---

# Replaying an entrance animation by re-mounting blinks: replay with a loop that starts and ends at rest

**One-liner:** an entrance animation starts from nothing (opacity 0, off-position), so "play it again" by re-mounting or re-adding the class makes the element vanish for a frame and pop back. A replay has to be its own animation that **starts and ends on the resting state**, run with the Web Animations API over the finished CSS one; a second trigger while it runs lets it finish rather than restarting.

*Playmoir's website logo, 2026-10-02 (`apps/landing/src/sections/Mark.jsx`).*

## The pattern

- The page-load arrival stays a CSS animation (from nothing to rest).
- The replay (hover, tap) is a different motion: from rest, away, back to rest. For the logo, the two echo triangles fold forward into the solid one while it softens, then peel back out.
- Run it with `element.animate(keyframes, { duration })` on each piece; keep the returned `Animation` objects.
- Re-trigger while running: if an animation is in flight, do nothing (or queue one more), never cancel it mid-way, which jumps.

Because both ends are the resting frame, there is no instant where the element is absent, and nothing depends on the CSS animation's state.

## Related

- `animation-keyed-to-creation-not-content.md`, `exit-animation-props-captured-at-unmount.md`.
