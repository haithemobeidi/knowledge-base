---
stack: [react, framer-motion, animation]
kind: gotcha
last_verified: 2026-07-26
---

# Exit-animation props are captured at unmount — a flag set in the same batch is too late

**One-liner:** `<AnimatePresence>` (and every API shaped like it) animates a removed child by re-rendering the element it captured from **the last render in which that child was present**. So any state your `exit` prop consults must already be committed *before* the render that removes the child. Setting the flag and triggering the removal in the same event handler batches them into one render — the child is gone in that render, so the captured `exit` still holds the OLD value, and the wrong exit variant plays. Nothing errors. It can sit wrong for months.

## The failure shape

You have one overlay with several ways out, and you want a different exit per route:

```tsx
<AnimatePresence>
  {isOpen && (
    <motion.div
      exit={
        navigatingAway
          ? { opacity: 0, transition: { duration: 0.4 } }   // flat fade, we're leaving
          : { opacity: 0, transition: { duration: 0, delay: 0.7 } } // hold, then snap
      }
    />
  )}
</AnimatePresence>
```

and a handler that picks the route:

```ts
function handleNavigateAway(screen) {
  setNavigatingAway(true);   // "use the flat fade"
  closeOverlay();            // ...this is what sets isOpen = false
}
```

This reads correctly and is wrong. React batches both setters into one render. In that render `isOpen` is already `false`, so the child isn't rendered at all — `AnimatePresence` falls back to the element it kept from the *previous* render, whose `exit` closed over `navigatingAway === false`. Every nav-away silently runs the **other** branch.

## Why it hides for so long

An exit animation that picks the wrong branch is still *an animation*. There's no error, no warning, no visual "missing" state — just the wrong choreography, which usually looks plausible enough that nobody questions it. In the case this was extracted from, the wrong branch was a 700ms opaque hold: the overlay simply sat there and then vanished, which reads as "the app went to the next page." The bug only became visible months later when an unrelated change made part of that overlay independently animated, and suddenly the wrong branch leaked the previous screen into view.

That's the tell for this whole class: **a transition bug that appears the moment you touch something adjacent, in code you didn't change.** The branch was always wrong; you just gave it a symptom.

## Fixes

**1. Commit the flag in its own render, while the child still exists.** Targeted and minimal:

```ts
import { flushSync } from 'react-dom';

function handleNavigateAway(screen) {
  setScreen(screen);
  // flushSync so this lands in a render where the overlay is STILL MOUNTED.
  // AnimatePresence captures exit props from the last render the child
  // appeared in; batching this with the close below means it captures the
  // stale value and picks the wrong exit.
  flushSync(() => setNavigatingAway(true));
  closeOverlay();
}
```

Note the ordering requirement: `flushSync` must come *before* whatever removes the child, and the removal must not be inside the same `flushSync` callback.

**2. Better where possible — don't branch on state set at close time.** If the exit variant is knowable from something already true while the overlay is open (how it was *opened*, which screen owns it), branch on that instead. State that was committed renders ago can't be stale. This is the same instinct as [derive-dont-track-ui-flags.md](./derive-dont-track-ui-flags.md): the most reliable flag is one nobody has to set at the right moment.

**3. Keep the child mounted one render longer.** Gate removal on a separate "exit armed" state so the flag lands first and the removal happens on the next render. More moving parts than `flushSync`; reach for it only if you already need a staged teardown.

## How to confirm it in 30 seconds

Give each branch a wildly different, obviously distinguishable transition — `duration: 3` on one, `duration: 0` on the other — and trigger the path. If the one that plays isn't the one you expect, the props are stale. This beats logging, because a `console.log` inside the render body fires on renders that aren't the captured one and will happily print the value you *want* to see.

## Failure mode 2: the exit's UNMOUNT can be dropped entirely (verified live, 2026-07-26)

The stale-capture bug plays the *wrong* exit. There's a worse cousin: the exit plays and the **removal never happens**. AnimatePresence keeps the leaving child mounted while it animates the captured snapshot, then unmounts it when the exit resolves — but that unmount is bookkeeping inside the library, and a heavy re-render storm landing mid-exit (a data-invalidation burst, a context flip re-rendering the app shell) can drop it. Diagnosed from live DOM dumps, not theory: a full-screen overlay stranded **mounted, laid out, `opacity: 0`, `pointer-events: auto`** — an invisible sheet eating every click, with zero running animations. The app looks frozen while rendering fine. Repeated three times with three different re-render triggers before the mechanism was captured.

Two mitigations work but leak (exit carries `pointerEvents: 'none'` + `transitionEnd: { visibility: 'hidden' }`, so a dropped unmount strands one *inert* subtree; per-open `key` so a poisoned exit entry can't swallow the next open). **The structural cure is to stop using exit-time bookkeeping for anything load-bearing:** render the overlay as a plain conditional, drive the exit visuals through `animate` props reading live state (a `closing` flag), and let your own close timeline clear the state — clearing it IS the unmount. A conditional render cannot strand: when state says closed, React unmounts; there is no library bookkeeping to lose. Bonus: every `flushSync` workaround from failure mode 1 becomes deletable, because live `animate` props never capture anything.

When to accept the trade: you lose AnimatePresence's convenience of "unmount whenever the exit happens to finish" and must own the timing constants yourself. For a surface where a stranded invisible sheet means "app unusable," that trade is obviously right; for a decorative toast, the mitigation pattern is enough.

## The general rule

Any API that animates something *on its way out* has to hold onto a snapshot of it, because the thing is by definition no longer in your tree. **Whatever that snapshot captured is what the exit will use.** React Transition Group, Vue's `<Transition>` with dynamic props, and hand-rolled "keep the last child around while it animates" wrappers all share the shape. When an exit is configurable, always ask: *at the instant this element left the tree, had my configuration already landed?*

## What NOT to do

- Don't "fix" it by adding a delay before the close call so the flag lands first. It works by accident, is timing-dependent, and breaks under load — this bug already lives in the gap between two schedulers, so don't add a third.
- Don't move the exit config into a ref to dodge the capture. Motion reads the prop from the captured element; a ref read at exit time is not a supported hook and will vary by version.
- Don't assume a branch is live because you can see it in the source. Any conditional inside an `exit` prop is a candidate for having never executed. When auditing exit choreography, verify *which branch actually runs*, not which branches exist.
