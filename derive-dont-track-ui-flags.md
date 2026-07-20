---
stack: [react, frontend, state-management]
kind: pattern
last_verified: 2026-07-08
---

# A UI flag with N reset paths WILL get stuck — derive it instead

**One-liner:** if a boolean UI flag has to be explicitly cleared on more than a couple of exit paths (back button, Escape, outside-click, nav-away, a cancel button, a race with another action...), it will eventually get stuck true on whichever path someone forgets to wire up. The fix isn't "find and patch the missing path" — it's eliminating the reset action entirely by **deriving** the flag from state that's already correctly maintained elsewhere.

## The failure shape

A flag like `modalObscuringBackground` or `detailViewBlockingLibrary` starts as its own `useState`, set `true` on open and expected to be set `false` on close. Fine, until close turns out to have more than one door:

- Back button
- Escape key
- Clicking outside
- A sidebar navigation that jumps away without going through the normal close handler
- Browser/router `popstate`
- A "quit" or "cancel" ritual with its own code path
- A race: the user triggers a new open while an old close is still mid-animation

Every one of these needs to remember to clear the flag. Miss any single one and the UI gets stuck in the blocked/obscured/locked state — usually intermittently, usually only on the path nobody tested last, and usually patched 3-5 times across separate sessions because each fix addresses the ONE path that was just discovered broken, not the shape of the bug.

## The fix: derive, don't track

Ask: is there already OTHER state in the component that's true exactly when this flag should be true, and false exactly when it shouldn't? If yes, delete the flag and compute it:

```ts
// BEFORE — an independent boolean every exit path must remember to clear
const [obscured, setObscured] = useState(false);
// ...open path: setObscured(true)
// ...close path A: setObscured(false)
// ...close path B: (forgot!) — obscured stays stuck true forever

// AFTER — derived from state that's already correctly set/cleared elsewhere
const obscured = selectedItemId !== null && !isClosing;
```

`selectedItemId` and `isClosing` both already have to be correct for the rest of the feature to work (the detail view can't render without `selectedItemId`; the close animation can't run without `isClosing`). Riding on state that already has to be right means there's no THIRD piece of state that can independently drift out of sync — the "forgot to clear it on path N" bug class is structurally impossible, because there's no clear-action left to forget.

## When this applies

- The flag is a pure function of state you already track for other reasons (existence of a selection, an in-progress-transition marker, a count being zero/non-zero).
- You've already found yourself patching "flag stuck true" bugs more than once for the same flag — that's the signal the tracked-boolean approach has structurally too many exit paths, not that you haven't found the last one yet.

## When it doesn't apply

- The flag genuinely carries information no other state has — e.g. "the user explicitly dismissed this warning" isn't derivable from anything else; it has to be its own tracked fact (and in that case, the number of paths that can SET it is usually small and well-defined, unlike close/exit paths which tend to multiply over a project's life).
- Deriving from multiple fast-changing pieces of state can occasionally introduce a one-render flicker if they don't update atomically — verify the derived value is correct across a render, not just eventually-consistent.

## How to spot candidates in an existing codebase

Grep for `useState` booleans whose setter appears in more than 2-3 distinct call sites/handlers within the same feature. That fan-out is the tell — a flag set/cleared from many places is a flag one of those places will eventually mis-handle. Check whether the same true/false shape already exists as a computable expression over other state before adding yet another explicit clear call to the newest exit path.

---
*Generalized from a real recurring bug (5+ patches across sessions before the structural fix) — the tracked flag was a "library view is obscured/blurred behind an open detail panel" boolean with 8 separate paths that could close the detail. Replaced with `selectedId !== null && !closing`.*
