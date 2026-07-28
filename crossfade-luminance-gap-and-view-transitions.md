---
stack: [css, react, animation, web-platform]
kind: gotcha
last_verified: 2026-07-28
---

# A cross-fade "flash" is a luminance gap, not a visibility problem

**One-liner:** two transparent layers cross-fading at the same rate never sum to full coverage, so your page background shows through the middle of every screen transition and reads as a flash — speeding up the outgoing layer doesn't fix it, making both layers opaque does but trades the flash for apparent input latency, and the View Transitions API removes the trade entirely because it composites opaque snapshots instead of live layers.

## The setup that produces it

The standard SPA screen-switcher: every screen is an absolutely-positioned sibling, all mounted (so state and scroll survive), the active one at `opacity: 1` and the rest at `0`, all sharing one transition.

```jsx
<div className={`absolute inset-0 transition-all duration-280 ease-out
                 ${active ? 'opacity-100' : 'opacity-0 translate-y-1'}`}>
```

This looks correct and is what almost everyone writes.

## The math

The containers are **transparent**, so the page background is a third participant. Compositing top-to-bottom:

```
result = C_in·α_in  +  (1 − α_in)·[ C_out·α_out  +  (1 − α_out)·C_bg ]
```

With both layers on the same curve, at the midpoint `α_in ≈ 0.56`, `α_out ≈ 0.44`:

```
result = 0.56·C_in + 0.19·C_out + 0.25·C_bg
```

**A quarter of the page background is showing through the middle of every transition.** If your background is near-black and your screens have content brighter than it (they do), the composite dips darker and then recovers. That pulse is the "flash." It is a *luminance* artifact, not a visibility one.

## The diagnostic that separates the two defects

There are genuinely two things wrong with the naive cross-fade, and they need different fixes. Tell them apart by shortening **only the outgoing** layer:

- **Ghost clears sooner, pulse gone** → you only had the visibility problem.
- **Ghost clears sooner, pulse remains** → the luminance gap, which timing cannot fix.

Worth computing per frame rather than eyeballing. With both layers at `duration-280 ease-out`, the visible ghost of the outgoing screen — `(1 − α_in)·α_out` — runs 0.64 at frame 1, 0.19 at frame 4, 0.03 at frame 8, and is still nonzero at frame 10 (~167ms at 60fps).

**Where it becomes obvious:** when the destination doesn't occupy the same area as the source. A centred/narrow screen (a settings page, a modal-ish view) leaves margins where the outgoing full-width screen is completely unmasked, and the wider the display the larger those margins. The same transition is invisible on a laptop and glaring on an ultrawide — which is why it survives review for years.

## Fix A — asymmetric durations (partial)

Drop the outgoing layer to ~120ms, keep the incoming at 280ms:

```jsx
active ? 'duration-280 opacity-100' : 'duration-120 opacity-0'
```

Ghost clears by frame 5 instead of frame 10. Cheap, no structural change, and a real improvement. **It does not remove the flash**, because the gap is still there — it's just narrower.

## Fix B — opaque and stacked (fixes the flash, introduces latency)

Paint the containers opaque and put the incoming one on top, so the outgoing holds at full opacity underneath until it's covered:

```jsx
const base = 'absolute inset-0 bg-[var(--background)] transition-all ease-out';
active ? `${base} z-10 duration-280 opacity-100`
       : `${base} z-0 duration-0 delay-280 opacity-0`   // holds, then drops hidden
```

Total coverage is 1 at every instant. No background bleed, no dip, only one pair of layers ever blending. **The flash is genuinely gone.**

**And it feels broken.** Reported immediately in testing as: *"the transition takes too long to even start now, feels like latency — it's like I click and then a quarter second later it changes."*

The cause is inherent, not a tuning miss: with the outgoing layer held at `opacity: 1`, the first frames are ~80% old screen (the incoming is only at 0.20 by frame 1 on a 280ms ease-out), so **nothing appears to happen for ~4 frames**. The transparent version changed the frame immediately precisely *because* the old layer was already dropping — the same property that caused the flash was also what made it feel responsive.

### The trade, stated plainly

| Approach | Flash | Perceived start |
|---|---|---|
| Transparent cross-fade | ✗ background gap | ✓ instant |
| Opaque cover-up | ✓ none | ✗ dead first beat |

**Untried middle worth trying before reaching for Fix C:** keep opaque + stacked (which kills the gap structurally) but drop the *incoming* duration to ~140–160ms so the change registers within 2–3 frames. The failed attempt above kept 280ms in, and that is what made it feel slow.

## Fix C — View Transitions API (removes the trade)

```js
document.startViewTransition(() => updateTheDOM());
```

The browser snapshots the old and new states as **opaque full-frame images** and cross-fades *those* above the live DOM. That gives both properties at once:

- **No background gap** — the old snapshot is an opaque picture of the entire viewport, so there's nothing to punch through. (Fix B's goal.)
- **Immediate perceived start** — the old snapshot begins fading at frame 1. (Fix B's casualty.)

It's also compositor-work on textures rather than two animating DOM trees, which matters on low-end integrated graphics.

**Same-document, not cross-document.** These are different features and the names mislead. *Cross-document* (`@view-transition { navigation: auto }`) fires only on real URL navigation between two documents — irrelevant to an SPA, and completely irrelevant to a desktop shell with no URLs at all. *Same-document* is `document.startViewTransition()`, and that's the one for a state-driven screen switcher.

**Caveats worth knowing before you commit:**

1. **The DOM update must be synchronous inside the callback.** Frameworks that batch state updates need an escape hatch — in React before 19 that's `flushSync(() => setScreen(s))`. React 19 ships a `<ViewTransition>` component that removes the workaround, so this feature is a real argument in an upgrade discussion rather than a nice-to-have.
2. **Remove your existing CSS transitions on those containers**, or both animations run and fight.
3. **Reduced motion needs explicit wiring.** The default cross-fade is animation; if your app has its own motion-preference system (not just the media query), bridge it — see `motion-design-token-system.md`, which covers why a media query alone under-covers.
4. Availability: same-document view transitions reached **Baseline "Newly available" on 2025-10-14**. Chromium (Chrome/Edge) from 111, WebKit from Safari 18, Gecko later still — sources disagree on the exact Firefox version, so check before relying on it there. Chromium-based webviews (Electron, Tauri's WebView2) inherit it, so desktop shells have had it since well before the web-at-large baseline. Note Firefox's initial implementation omitted view-transition *types*.

## The meta-lesson

The instinct on a transition artifact is to reach for timing — make it faster, change the curve, add a delay. Both of the first two fixes here are timing fixes and neither solves the actual problem, because **the problem is compositing**. When an animation artifact survives every duration you try, stop tuning and write down what is actually on screen at the midpoint, layer by layer, with alphas. The arithmetic usually names the bug in one line.

And it's worth asking early whether the platform already does this, because for the "swap one full-screen view for another" case it now does, natively and better.

## What NOT to do

- **Don't fix a cross-fade flash with timing.** If shortening the outgoing layer clears the ghost but leaves the pulse, no duration will help — the gap is structural.
- **Don't hold the outgoing layer at full opacity to close the gap** without checking perceived responsiveness. It works, and it converts your flash into apparent input lag, which is worse.
- **Don't test screen transitions only on the display you develop on.** A centred destination on a wide monitor unmasks the outgoing screen in the margins; the identical code looks fine on a laptop.
- **Don't reach for cross-document view transitions in an SPA.** They require real URL navigation between documents. Same-document is the SPA feature.
- **Don't assume `startViewTransition` composes with your existing CSS transitions.** Take yours out, or you'll be debugging two animation systems arguing about one property.
