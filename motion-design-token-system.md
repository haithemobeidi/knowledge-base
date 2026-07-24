---
stack: [react, css, framer-motion, tailwind]
kind: pattern
last_verified: 2026-07-21
---

# A motion design-token system that reduced-motion actually reaches

**One-liner:** centralize animation curves + durations into a small named-preset module (mirrored as CSS custom properties), and treat "respect reduced motion" as a problem with THREE independent surfaces to wire — CSS transitions, your JS animation library's own engine, and the inevitable hardcoded utility classes that bypass both — not one media query.

## Part 1 — the token system

Three layers, in one small module (framework-agnostic; this example uses Framer/Motion-shaped presets, but the shape applies to GSAP, native Web Animations, or CSS-only projects):

```ts
export const easings = {
  ethereal: [0.22, 1, 0.36, 1],   // soft settle, mild overshoot — default curve
  snap:     [0, 0, 0.2, 1],       // fast out — dismissals
  suck:     [0.4, 0, 0.6, 1],     // accelerate-in/decelerate-out — "retreat" motions
  material: [0.4, 0, 0.2, 1],     // neutral/unopinionated
  decel:    [0.16, 1, 0.3, 1],    // pronounced decel — long settle tail
} as const;

export const durations = {
  instant: 0.15, quick: 0.25, medium: 0.4, slow: 0.6, lush: 0.8, // seconds
} as const;

// Named presets compose curve + duration for a SEMANTIC behavior.
// Call sites use the name, never a raw tuple.
export const motions = {
  stateChange: { duration: durations.quick, ease: easings.ethereal }, // hover/select feedback
  reveal:      { duration: durations.slow,  ease: easings.ethereal }, // content entering
  dismiss:     { duration: durations.quick, ease: easings.snap },     // content leaving, fast
  settle:      { duration: 0.7,             ease: easings.decel },    // multi-layer close sequence
} as const;
```

**Why named presets over raw numbers:** `transition={motions.reveal}` at a call site tells the next reader the *intent* ("this is a content-entering animation"), not just a number. It also means changing what "reveal" feels like across the whole app is a one-line edit instead of a grep-and-replace across every component that happened to use `{ duration: 0.6, ease: [0.22,1,0.36,1] }` inline.

**The CSS mirror, and its risk:** the same values get hand-published as CSS custom properties (`--ease-ethereal: cubic-bezier(0.22, 1, 0.36, 1)`, `--duration-slow: 600ms`, `--motion-reveal: 600ms var(--ease-ethereal)`) so pure-CSS transitions and JS-driven animations read the *same* numbers instead of two authors independently guessing "does 600ms feel like 0.6s?" This is itself a two-copies-of-one-fact problem (see [`n-copies-of-truth-drift-guard.md`](./n-copies-of-truth-drift-guard.md)) — nothing enforces the JS module and the CSS file stay in sync except a code comment saying "keep in sync with that file." For a small token set (5 easings × 5 durations) manual sync is a reasonable tradeoff; if your token count grows, generate the CSS block from the JS module at build time instead of hand-mirroring it.

**Property-first CSS transitions, not `all`:** `transition: opacity var(--motion-reveal), transform var(--motion-reveal);` — naming the properties avoids the `transition: all` anti-pattern, which animates every property that happens to change (including ones you didn't intend, like a color inherited from a parent hover state) and fights the intent of a "these two things move together" design.

## Part 2 — reduced motion has to reach three separate places

Most apps wire `@media (prefers-reduced-motion: reduce)` into their CSS and consider it done. That only covers CSS-driven transitions. Two more surfaces silently keep animating at full speed unless you deliberately bridge them:

### A four-state preference, not a binary toggle

```
'full'    → animate at full duration, even if the OS says reduce
'auto'    → follow the OS prefers-reduced-motion media query
'reduced' → an explicit middle tier: durations halved, motion still visible
'off'     → zero duration, instant snap
```

`reduced` matters as its own state — some users want *less* motion without the jarring flatness of everything snapping instantly. Store it (localStorage or equivalent), reflect it onto `<html data-motion-pref="...">` at module load (before first paint, so CSS sees the right state immediately), and dispatch a custom event on change so any already-mounted consumers resync without a reload:

```ts
function syncAttribute(): void {
  document.documentElement.setAttribute('data-motion-pref', readPreference());
}
export function setMotionPreference(pref: MotionPreference): void {
  localStorage.setItem(STORAGE_KEY, pref);
  syncAttribute();
  window.dispatchEvent(new CustomEvent('motion-preference-change'));
}
syncAttribute(); // module-load: CSS sees correct state before first render
```

CSS resolves layered overrides via specificity: `:root` sets full-duration defaults, an `@media (prefers-reduced-motion: reduce)` block flattens them, and `html[data-motion-pref="..."]` attribute selectors — which beat both `:root` and the media query on specificity — apply the in-app override on top. `auto` simply has no attribute-selector rule, so it falls through to the media query. (This same attribute-beats-media-query layering technique is the standard way to implement "OS default with an in-app override" for ANY preference — dark mode included, not just motion.)

### Bridge the preference into your JS animation library's own config

This is the step that's easy to skip and produces a "the Off toggle does nothing" bug: your JS animation library doesn't read your CSS custom properties or your `data-motion-pref` attribute — it has its own separate reduced-motion handling that you have to wire explicitly.

```tsx
// Framer/Motion example — MotionConfig has its OWN reducedMotion prop:
// 'never' (ignore OS), 'user' (follow OS media query), 'always' (force zero)
function prefToMotionMode(pref: MotionPreference): 'never' | 'user' | 'always' {
  switch (pref) {
    case 'full': return 'never';
    case 'off':  return 'always';
    default:     return 'user'; // 'auto' and 'reduced' both defer to the OS query here
  }
}

export function MotionProvider({ children }) {
  const [pref, setPref] = useState(() => getMotionPreference());
  useEffect(() => {
    const handler = () => setPref(getMotionPreference());
    window.addEventListener('motion-preference-change', handler);
    return () => window.removeEventListener('motion-preference-change', handler);
  }, []);
  return <MotionConfig reducedMotion={prefToMotionMode(pref)}>{children}</MotionConfig>;
}
```

Without this provider, changing the in-app setting only affects elements whose animation is driven by CSS transitions reading the `--duration-*` vars. Anything animated via the JS library's own `animate`/`transition` props keeps its hardcoded values regardless of the setting — which reads to a user as "I turned this off and it's still moving."

### The universal kill-switch — because token coverage is never 100%

In any real codebase, some components WILL use a hardcoded Tailwind duration class (`duration-150`) or an inline `transition: ...300ms...` that bypasses the token vars entirely — refactoring every last one isn't worth blocking a ship on. The fix is a blanket CSS safety net scoped to the "no motion wanted" states:

```css
html[data-motion-pref='off'] *,
html[data-motion-pref='off'] *::before,
html[data-motion-pref='off'] *::after {
  animation-duration: 0.001ms !important;
  animation-delay: 0ms !important;
  transition-duration: 0.001ms !important;
  transition-delay: 0ms !important;
}
```

**Use `0.001ms`, not `0ms`.** Some browsers/engines skip firing `transitionend`/`animationend` entirely for a strictly-zero-duration transition or animation. If any of your code waits on that event (e.g. to trigger a follow-up state change), a literal `0ms` can silently hang that logic forever. A near-zero duration keeps the event contract intact while being visually instant.

This kill-switch doesn't cover the JS-library-driven layer (that's `MotionProvider`'s job above) — it's specifically the backstop for CSS you don't control or haven't migrated to the token system yet.

### The trap inside the kill-switch: near-zero duration *freezes* a loop, it doesn't neutralize it

`animation-duration: 0.001ms !important` reads like "turn the animation off." It doesn't. It leaves the animation *running*, just so fast the element renders at a single fixed point in the keyframe timeline — and for an **infinite/looping** animation, which point that is comes out effectively arbitrary. In practice engines pin it to the `0%` keyframe. That's harmless for a pulse that rests at its neutral value at 0% — but it's a real bug when the state the animation expresses is *carried by* the animated property.

Concrete failure we hit: a "syncing" indicator was a bright band sweeping through the mark — `@keyframes { 0%,100% { opacity: .22 } 45% { opacity: 1 } }`. Under reduced motion the kill-switch froze it at the `0%` frame, i.e. its **dimmest** value (`.22`). Result: the "busy" state rendered *fainter than the idle resting state* — the exact opposite of the signal. Nobody notices in review because you don't test every looping animation with reduce-motion on; it surfaces as "why does active look more off than idle?"

**The fix — give continuously-animated states a *designed* static form.** Where an animation communicates state (not just decoration), add an explicit reduced-motion rule that (a) sets `animation: none` — needed so the frozen keyframe value can't override your static value from the animation cascade origin, which outranks normal declarations — and (b) sets the property to a chosen held value that still reads as that state:

```css
/* Match the kill-switch's own conditions exactly, so behavior is consistent */
html[data-motion-pref='off'] .mark[data-state='syncing'] .echo,
@media (prefers-reduced-motion: reduce) {
  html:not([data-motion-pref='full']) .mark[data-state='syncing'] .echo {
    animation: none;      /* stop the loop so the value below actually applies */
    opacity: .85;         /* a bright, HELD "busy" — not the frozen .22 */
  }
}
```

Decorative loops (a glow pulse that rests neutral at 0%) can keep riding the blanket kill-switch — they freeze to a fine value. It's only the loops whose *meaning lives in the animated property* that need the explicit held state. Audit rule: for every `infinite` keyframe, ask "what does its 0% frame look like, and is that an acceptable static picture of this state?" If no, it needs a designed reduced-motion hold.

## What NOT to do

- **Don't assume CSS media-query coverage means you're done.** Test with your JS animation library's most commonly used component with the OS "reduce motion" setting on — if it still animates at full speed, you're missing the provider bridge.
- **Don't use exactly `0ms` in a universal kill-switch** — use a near-zero value so `transitionend`/`animationend` still fire.
- **Don't skip the "reduced" middle tier** if your users are diverse — accessibility guidance increasingly recognizes that "some motion, less of it" and "zero motion" are different needs, not the same request at different intensities.
- **Don't assume the near-zero-duration kill-switch "turns off" a looping animation** — it freezes it at an arbitrary keyframe (usually `0%`). Any `infinite` animation whose meaning is carried by the animated property needs an explicit reduced-motion `animation: none` + a designed held value, or the state renders as whatever its 0% frame happens to be (which can be its *dimmest/emptiest* — the opposite of the intended read).
