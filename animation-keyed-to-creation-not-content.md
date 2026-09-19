---
stack: [animation, react, web, images]
kind: gotcha
last_verified: 2026-09-18
---

# An animation keyed to element creation, not content readiness, degrades to nothing

**One-liner:** you start the animation when the element exists. The content arrives later — a decode, a fetch, a stream, a font swap — so the animation plays out over an empty box and finishes just as the content appears. The user sees **nothing, and then the thing**, which is precisely the experience the animation was added to prevent. No error, no warning, and it looks perfect in every mock, because in a mock the asset is always already loaded.

## The failure shape

```tsx
// Fires the moment the element mounts with a src.
<motion.img
  src={coverUrl}
  initial={{ opacity: 0, scale: 0.94 }}
  animate={{ opacity: 1, scale: 1 }}
  transition={{ duration: 0.45 }}
/>
```

Mount and paint are not the same event. The element exists at frame 0; the pixels exist whenever the decode finishes. On a warm cache those are the same instant and the animation is beautiful. On a cold cache, a slow disk, a large image, or a throttled CPU, the bloom runs from frame 0 to frame 27 against an empty rectangle, and the picture lands at frame 30 at full opacity with no entrance at all.

The same shape, without images: a card that animates in while its text is still streaming from a model; a list row that slides in before its query resolves; a hero whose title animates before the webfont swaps, so the motion happens in the fallback face.

## Why it survives every review

**The mock is always warm.** Design prototypes, Storybook, a dev server you have hit forty times — the asset is in cache, decode is instant, mount and paint coincide. The bug requires a cold path to exist at all, and the people who look hardest at the animation are the people with the warmest caches. It reaches users first.

And when it does, it does not read as *broken*. It reads as "the app is a bit janky," which nobody files.

## The fix: key on readiness, not existence

Wait for the content to be *displayable*, then animate:

```tsx
const [ready, setReady] = useState(false);
const imgRef = useRef<HTMLImageElement>(null);

useEffect(() => {
  const img = imgRef.current;
  if (!img) return;
  // A cached image may already be complete before React ever attaches a
  // load handler — check first, THEN subscribe, or a warm load never fires.
  if (img.complete && img.naturalWidth > 0) { setReady(true); return; }
  const onLoad = () => setReady(true);
  img.addEventListener('load', onLoad, { once: true });
  return () => img.removeEventListener('load', onLoad);
}, [coverUrl]);
```

and gate the animation on `ready`. Note the ordering requirement in the comment: checking `complete` *after* subscribing is a race you will lose on exactly the warm path you test with.

Where the platform offers an explicit decode, prefer it — `await img.decode()` resolves when the bitmap is ready to paint, which is stricter and more useful than `load`. [webview2-react-render-traps.md](./webview2-react-render-traps.md) (Trap 7) documents the image-decode case concretely: a flight ghost mounted at frame 0 renders blank for the first dozen frames while the decode runs, and pre-warming with `decode()` is what fixes it.

**Always give readiness a deadline.** If the content never arrives, the animation must still happen — a race between `load` and a timeout, with the timeout winning gracefully, beats an element that is invisible forever because one request hung.

## How to confirm it in 30 seconds

Throttle the network to something slow, hard-reload with cache disabled, and watch the first paint. Or, faster and more reliable: temporarily delay the content by a fixed amount (`setTimeout` before setting the src, or a deliberate 2s delay in the resolver) and see whether the entrance animation still lands *with* the content or finishes before it arrives. If your animation is content-keyed, the delay simply postpones a correct animation; if it is creation-keyed, the animation happens in the gap and you watch it play to an empty box.

## The general rule

**Every entrance animation has two clocks — when the element exists and when the element is worth looking at — and they are only the same clock in development.** Ask of any entrance: *what, exactly, is the user supposed to see moving?* If the answer is content that arrives asynchronously, the animation must be keyed to that arrival. If the answer is a container, a skeleton, or a shape you draw yourself, mount is fine.

This is also why "it looks right in the prototype" is weak evidence for motion work specifically. Prototypes hold their assets locally and their data inline; they systematically remove the asynchrony that entrance animations exist to smooth over.

## What NOT to do

- Don't paper over it with a delay before starting the animation. It is a guess about someone else's latency, it is wrong on both fast and slow machines, and it adds dead time to the fast path to hide a bug on the slow one.
- Don't animate a skeleton and then swap in the real content with no transition — you have then built two entrances and shown the user the wrong one.
- Don't trust `onLoad` alone for cached content without the `complete` pre-check; the handler can attach after the event has already fired.

## Related

- [webview2-react-render-traps.md](./webview2-react-render-traps.md) — Trap 7 is this bug in its concrete image-decode form, with the `decode()` pre-warm fix.
- [object-position-percent-is-container-relative.md](./object-position-percent-is-container-relative.md) — the same readiness dependency one layer up: you cannot compute a crop from a natural size that has not decoded yet.
- [screen-recordings-lie-about-luminance.md](./screen-recordings-lie-about-luminance.md) — the other reason motion work resists casual verification.
