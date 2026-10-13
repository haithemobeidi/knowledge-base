---
stack: [javascript, dom, react, web]
kind: gotcha
last_verified: 2026-10-02
---

# `stopPropagation` can't stop a second listener on the same target: layered Escape handlers need the capture phase

**One-liner:** two `window` keydown listeners in the same phase both run, whatever the first one does with `stopPropagation()`, because propagation is between steps of the event's path, not between listeners at one step. One Escape closed a lightbox AND the page under it. A "topmost layer wins" key handler listens in the **capture** phase and calls `stopPropagation()` there.

*Playmoir desktop, 2026-10-02.*

## Why

`stopPropagation()` stops the event travelling to the *next node*. Listeners on the node it is already at still run, in registration order. Both the page and the lightbox had added `window.addEventListener('keydown', …)`, so both saw the same Escape. `stopImmediatePropagation()` stops later listeners on the same node, but only if yours registered first, which in a component tree depends on mount order.

## The fix

`window` sits on the event's path twice: first in the capture phase (going down), last in the bubble phase (coming back up). Those are separate steps, so stopping propagation at the capture step cancels everything after it, including `window`'s own bubble listeners. The lightbox (`packages/frontend/src/components/Lightbox.tsx`) does exactly that:

```js
useEffect(() => {
  if (!url) return;
  function onKey(e) {
    if (e.key === 'Escape') { e.stopPropagation(); onClose(); }
  }
  window.addEventListener('keydown', onKey, true);   // capture
  return () => window.removeEventListener('keydown', onKey, true);
}, [url, onClose]);
```

The page's ordinary (bubble) handler never sees that Escape. Removal needs the same capture flag, or the listener leaks. If two overlays can stack, both capturing on `window`, the trap returns one level up: same-step listeners run in registration order, so the one mounted first (the lower overlay) runs first and the topmost can't stop it. Past one overlay, route keys through a single layer stack that hands each key to the topmost entry.
