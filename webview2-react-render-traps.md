---
stack: [tauri, react, webview2]
kind: gotcha
last_verified: 2026-07-21
---

# WebView2 + React render traps — gotchas that don't exist in Chrome dev

> The Tauri/Electron promise is "you already know how to build web apps, just ship it as a desktop app." Mostly true, but WebView2 (Windows) and WKWebView (macOS) ship slightly different rendering and resource-management behavior than Chrome dev. Most surprises come from WebView2 being more aggressive about resource conservation. This is the surviving list of traps we hit.

## Trap 1: `loading="eager"` is mandatory for above-the-fold images

**Symptom:** images that are visible in the viewport at first paint render as blank/broken for 200-800ms before snapping in, only on Windows builds. Works perfectly in dev (which usually runs in Chrome).

**Cause:** Chrome implements a "Lazy Image Loading" intervention that defers all `<img>` requests by default, and WebView2 inherits it. The intervention is supposed to skip in-viewport images, but the heuristic isn't perfect — especially for images inside transformed/animated containers where layout isn't yet stable.

**Fix:** add `loading="eager"` to ALL `<img>` elements that should be visible at first paint.

```tsx
<img
  src={gameCoverUrl}
  loading="eager"     // ← required on Windows
  decoding="async"    // ← optional but recommended; non-blocking decode
  alt={game.name}
/>
```

**Where to add it:**
- Banner images on detail screens
- Above-the-fold cards in lists/grids
- Hero artwork during transition animations (the trap is worst here — the image isn't where the heuristic expected it yet)

**Where you can skip it:** images below the fold or only revealed on scroll. Native lazy-load is still a real perf win there.

We hit this on game detail screen hero banners. The first frame after navigating to a game detail had a 500ms blank-banner flash before the cover loaded. `loading="eager"` removed the flash entirely.

---

## Trap 2: `key={id}` on hero components to force fresh DOM/GPU per item

**Symptom:** navigating from detail-screen-for-game-A to detail-screen-for-game-B reuses the same React component but the new game's banner image renders as a gray rectangle for several hundred ms. Or, more subtly, a CSS animation that played for game A doesn't replay for game B.

**Cause:** React reuses the existing DOM node when the component type is identical. WebView2 then sometimes reuses the GPU compositor layer associated with that DOM node, including any cached image decode. When the `src` changes, the decoder has to flush the old bitmap and request the new one — and during that gap, the GPU shows the cached old frame OR a blank/transparent fallback depending on timing.

**Fix:** add `key={id}` (or `key={uuid}`) to the top-level component that should "reset" between items.

```tsx
function App() {
  return <GameDetailHero key={selectedGameId} game={selectedGame} />;
}
```

Adding the key forces React to unmount the old component and mount a fresh one for each new game. New DOM nodes → new GPU compositor layers → no stale bitmap caching.

**Trade-off:** you lose any state that was internal to the component (open accordions, scroll position) because it remounts. If you need to preserve some state across the morph, lift it to a parent that doesn't remount.

---

## Trap 3: `useLayoutEffect` is MANDATORY for measurement-driven styles in StrictMode

**Symptom:** flight/morph animations work perfectly in production but fail in dev. Element positions are off by a few pixels, or the animation snaps from origin to destination without the interpolation. Toggling StrictMode off in dev "fixes" it.

**Cause:** StrictMode double-invokes effects (development only) to catch impure side-effects. If you compute element positions in `useEffect` and then apply them to JSX style props on the same render, StrictMode's second invocation can run AFTER the browser has already painted the first invocation's frame. The animation starts from the WRONG position.

`useLayoutEffect` runs synchronously after DOM mutations but BEFORE the browser paints. Measurements taken here, and styles applied here, land on the same frame as the DOM mutation. Safe under StrictMode.

**The rule:** any dynamic CSS that depends on measuring real DOM (positions, sizes, computed filter offsets, transform origins) MUST be applied imperatively from `useLayoutEffect`, NEVER via JSX `style={...}` props that read the same measurement.

```tsx
// WRONG — JSX path, StrictMode breaks this
function FlightGhost({ from, to }) {
  const [transform, setTransform] = useState('');
  useEffect(() => {
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    setTransform(`translate(${dx}px, ${dy}px)`);
  }, [from, to]);
  return <div style={{ transform }}>...</div>;
}

// RIGHT — imperative path, survives StrictMode
function FlightGhost({ from, to }) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    node.style.transform = `translate(${dx}px, ${dy}px)`;
  }, [from, to]);
  return <div ref={ref}>...</div>;
}
```

This trap is brutal because the dev/prod divergence makes it look like a "StrictMode bug" rather than a real issue. It IS a real issue — your impure render path WAS depending on a single invocation. Move it to useLayoutEffect and it works everywhere.

---

## Trap 4: Tauri title-bar drag region eats clicks in the top ~32px

**Symptom:** clicks on buttons or interactive elements near the top of the window do nothing. Only on the desktop build, not the dev server in a normal browser.

**Cause:** Tauri's default window decoration / drag region behavior reserves an invisible "drag handle" strip at the top of the window. The strip exists so users can grab anywhere along the title bar area to drag the window, but it captures clicks before they reach your DOM.

The default height is 28-32px depending on the Tauri version and Windows version.

**Fix:** add top padding to every top-level screen so interactive content doesn't sit in the drag-eating zone.

```tsx
// Every top-level route / screen
<main className="pt-[44px] ...">  {/* ← clearance */}
  {/* screen content */}
</main>
```

44px is conservative (covers Windows 11 in dense-mode + a few px of safety margin). Adjust if your title bar is shorter on macOS/Linux.

**Where you can skip it:** the drag region is only at the top of the window. Side-pinned UI, modals, or anything `position: fixed; bottom: 0;` is unaffected.

**Don't try to "disable" the drag region** unless your app has its own custom title bar with explicit drag handles. Removing the drag region without replacing it makes the window un-draggable.

### The follow-up bite: persistent chrome isn't a "screen", and partial overlap hides for months

Added 2026-07-21 after this exact trap resurfaced in a shipped app, ~4 months after the `pt-[44px]` fix above was applied everywhere it was supposed to go.

**Two things make the second occurrence much harder to spot than the first.**

**1 · The advice says "every top-level screen," and persistent chrome is not a screen.** Sidebars, nav rails, floating toolbars, and brand marks are mounted *beside* the router, so a sweep that fixes routes misses them completely. In our case the sidebar had `pt-5` (20px) while every route had `pt-[44px]` — the one component nobody thought of as a screen was the one still straddling the boundary. **Audit by "what renders in the top 32px," not by "what is a page."**

**2 · Partial overlap presents as flakiness, not breakage.** An element taller than the remaining gap gets *bisected* by the drag region: our 25px-tall logo sat at y=20–45, so its top 12px were dead and its bottom 13px worked fine. It still lit up on hover (the hover fired from the live half), so it looked completely functional. The user's own words on discovering it: *"with the logo only the bottom half really works lol."* A fully-dead button gets reported on day one; a half-dead one survives indefinitely because every accidental success reinforces "it works."

**Do the arithmetic instead of clicking around.** `container padding-top` + `element offset` vs. the drag strip's height is a two-file check, and it's decisive. Clicking is unreliable precisely because you'll often hit the live half.

**Two fixes, and prefer the boring one.** You can raise the element above the drag layer (`z-index` above the strip's), or push it below the boundary with padding. Padding wins in almost every case: it reuses the clearance convention the codebase already has, it's self-explanatory to the next reader, and it leaves the drag strip intact — the `z-index` route silently punches a non-draggable hole in your title bar, and needs a comment explaining why a logo has a mysterious stacking context.

**Related affordance note, worth thirty seconds:** the same element had `cursor: default` set explicitly *and* a hover animation (scale + glow) — and users read it as a button anyway. **A hover transform outranks the cursor as an interactivity signal.** If an element animates on hover, people will click it regardless of what the cursor says; either give it a real action or remove the hover state. Do not rely on `cursor` to communicate "not clickable."

---

## Trap 5: Lightbox/modal portal MUST go to `document.body`

**Symptom:** a lightbox or modal `position: fixed; inset: 0;` anchors to the wrong element — it's clipped by a scrollable container or sits inside a transformed parent that messes up its positioning.

**Cause:** `position: fixed` anchors to the nearest **transformed** ancestor, not the viewport, if any ancestor has a `transform`, `filter`, `perspective`, `will-change: transform`, or `contain` property set. CSS spec, not a WebView2 quirk — but WebView2 makes it more common because animated parent components often have `transform: translate3d(0,0,0)` for GPU promotion.

**Fix:** render the modal/lightbox into a portal targeting `document.body` so it escapes the transformed ancestor chain entirely.

```tsx
import { createPortal } from 'react-dom';

function Lightbox({ src, onClose }) {
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80">
      <img src={src} className="max-h-full max-w-full" />
      <button onClick={onClose} className="absolute top-4 right-4">×</button>
    </div>,
    document.body
  );
}
```

**Watch for:** transformed ancestors are often invisible. A grid with `transition: transform` on hover, a parent with `will-change: opacity` for an entrance animation — any of these can break `fixed` positioning silently. If `inset: 0` ever produces a result that isn't full-viewport, suspect a transformed ancestor.

---

## Trap 6: `scrollbar-gutter: stable` to prevent layout jump

**Symptom:** when a scroll-locked modal opens, the page underneath shifts horizontally by ~15px. The scrollbar disappears, content reflows wider, then the modal animates in over the shifted layout.

**Cause:** Windows scrollbars overlay the content by default (modern Edge/Chrome do reserve gutter, but only for certain elements). When scroll is locked (e.g. via `body { overflow: hidden }`), the scrollbar vanishes, content gets the reclaimed horizontal space, reflow happens, jump.

**Fix:** reserve the gutter unconditionally on scrollable containers.

```css
.scrollable-pane {
  overflow-y: auto;
  scrollbar-gutter: stable;  /* always reserve scrollbar space */
}

/* Or globally on html element */
html {
  scrollbar-gutter: stable;
}
```

Now the gutter is always there. Hiding the scrollbar (via `overflow: hidden` on body for modal-open) doesn't reclaim space, so no shift.

---

## Trap 7: Image decode timing during morph/flight animations

**Symptom:** A "flight" animation that morphs a thumbnail from a list into a hero banner on the next screen shows a momentary blank frame in the middle of the transition. The thumbnail is visible at start, the hero is visible at end, but during the flight the image disappears.

**Cause:** when the flight ghost element first mounts, its `<img>` triggers a fresh decode. Until the decode finishes, the image renders blank. The flight animation runs on a 600ms timeline; the decode takes 50-200ms on cold cache. If the flight ghost was mounted at frame 0 of the animation, frames 0-12 show blank.

**Fix:** pre-warm the decode before the flight starts.

```tsx
// Before kicking off the morph animation
function startFlight(fromRect: DOMRect, toRect: DOMRect, imgUrl: string) {
  const preload = new Image();
  preload.decoding = 'async';
  preload.src = imgUrl;
  // Wait for decode before mounting the flight ghost
  preload.decode().then(() => {
    mountFlightGhost(fromRect, toRect, imgUrl);
  }).catch(() => {
    // Decode failed (CORS, 404, etc.) — mount anyway with onError fallback
    mountFlightGhost(fromRect, toRect, imgUrl);
  });
}
```

`HTMLImageElement.decode()` returns a Promise that resolves when the image is ready to paint synchronously. Combined with `loading="eager"` (Trap 1), this ensures the first frame of the flight is fully rendered.

---

## Trap 8: Don't measure during the same tick you mutate

**Symptom:** `getBoundingClientRect()` returns the wrong rect — usually the rect from BEFORE your DOM mutation, even though you just ran the mutation synchronously.

**Cause:** the browser batches layout calculations. Reading `getBoundingClientRect()` forces a synchronous layout. But if you mutate the DOM in the same render and then immediately measure, you may read the cached layout that didn't include your mutation yet.

**Fix:** separate mutation and measurement into two RAF ticks, OR use `useLayoutEffect` which guarantees the measurement runs after the React commit but before paint.

```tsx
// Two-RAF pattern for non-React mutation
node.classList.add('animating');
requestAnimationFrame(() => {
  requestAnimationFrame(() => {
    const rect = node.getBoundingClientRect();  // now reflects the class change
    // ...
  });
});
```

Single-RAF works most of the time but isn't reliable on WebView2 — the layout flush isn't always tied to the next animation frame the way it is in Chrome. Double-RAF is paranoid but robust.

---

## Trap 9: `setInterval` updates ONE piece of state but not the others derived from the same source

**Symptom:** a UI panel polls some backend status every N seconds and updates correctly — except one field that refuses to refresh. It stays frozen at whatever value loaded at mount. No error in console, no devtools warning, no failed fetch. The data is fresh server-side; the panel shows it in some places and stale in others.

**Cause:** a `setInterval` callback runs `setState(...)` for some derived values but forgets to also update others derived from the same source. Mount-time logic might initialize all of them via a single `checkStatus()` call, but the interval poll only refreshes the subset the original author remembered to wire up. The subset that's missing stays stuck at its mount-time value forever.

This is React state-management hygiene, not a WebView2 quirk — but it surfaces in this list because long-lived desktop apps have far more polling intervals than typical web apps (sync status, active-game watcher, network online/offline, OAuth token expiry). Each interval is a separate opportunity to miss a setter.

**The trap:**

```tsx
function StatusPanel() {
  const [state, setState] = useState<SyncState | null>(null);
  const [lastSync, setLastSync] = useState<number | null>(null);

  // Mount: both setters fire from one fetch
  useEffect(() => {
    checkStatus().then((r) => {
      setState(r.state);
      setLastSync(r.lastSyncedAt);  // ← runs at mount
    });

    // Interval: only ONE setter fires
    const id = setInterval(() => {
      checkStatus().then((r) => {
        setState(r.state);  // ❌ forgot to also call setLastSync
      });
    }, 3000);
    return () => clearInterval(id);
  }, []);

  return (
    <>
      <div>State: {state}</div>
      <div>Last synced: {lastSync ? formatTime(lastSync) : '—'}</div>
      {/* ← this is stuck at the mount-time value forever */}
    </>
  );
}
```

The trap is invisible because:
- The mount-time path works perfectly. First render shows correct data.
- The interval path also works for the OTHER state. So `state` updates correctly every 3s.
- The user sees `state` change and trusts the panel is live. They don't notice `lastSync` is frozen.
- No error, no warning, no exception. React doesn't track "you fetched this value but never set state for it."

**Fix:**

```tsx
const id = setInterval(() => {
  checkStatus().then((r) => {
    setState(r.state);
    setLastSync(r.lastSyncedAt);  // ✅ refresh ALL derived state
  });
}, 3000);
```

**Better fix — collapse the two paths into one helper so they can't drift:**

```tsx
async function refreshStatus() {
  const r = await checkStatus();
  setState(r.state);
  setLastSync(r.lastSyncedAt);
}

useEffect(() => {
  refreshStatus();
  const id = setInterval(refreshStatus, 3000);
  return () => clearInterval(id);
}, []);
```

Now there's exactly ONE place that maps the fetch result to component state. Adding a new field forces you to touch the helper, which means the interval picks it up automatically.

**Even better — single state object instead of multiple `useState` calls:**

```tsx
const [status, setStatus] = useState<{ state: SyncState | null; lastSync: number | null }>({
  state: null,
  lastSync: null,
});

async function refreshStatus() {
  const r = await checkStatus();
  setStatus({ state: r.state, lastSync: r.lastSyncedAt });
}
```

One setState call, one source of truth. The "miss a setter" failure mode is eliminated by construction.

**How to audit existing code:**

Search for `setInterval` and check each one against the mount-time initialization for the same component:

```bash
rg 'setInterval' src/ -l | xargs -I{} grep -H -A 30 'setInterval' {}
```

For each match, look at every `useState` in the file. If a state variable is set during mount but NOT inside the interval callback, it's almost certainly the bug — unless the value is truly immutable post-mount (and even then, prefer `useMemo` over `useState` for that).

**Related but distinct:** stale closures from missing dependency arrays. `setInterval(() => setX(x + 1), 1000)` captures `x` at mount. The fix is `setX(prev => prev + 1)`. This is a different bug from the setter-mismatch above — Trap 9 is specifically about missing setter *calls*, not stale closure values.

---

## Symptoms → cause quick reference

| Symptom | Likely trap |
|---|---|
| Image renders blank for 200-800ms on Windows only | Trap 1 — add `loading="eager"` |
| New item shows stale image briefly after navigation | Trap 2 — add `key={id}` |
| Morph animation works in prod, breaks in dev | Trap 3 — use `useLayoutEffect` |
| Top-row buttons unclickable on desktop builds | Trap 4 — add `pt-[44px]` clearance |
| Modal positions wrong inside animated parents | Trap 5 — portal to `document.body` |
| 15px horizontal jump when opening modals | Trap 6 — `scrollbar-gutter: stable` |
| Flight/morph shows blank frame mid-animation | Trap 7 — pre-decode the image |
| `getBoundingClientRect()` returns wrong rect | Trap 8 — separate mutation and measurement |
| Polled panel updates some fields, others stay frozen | Trap 9 — interval callback misses a setter |

---

## What NOT to do

- **Don't disable StrictMode to "fix" measurement bugs.** Fix the bug instead. StrictMode is catching a real issue — disabling it just hides it until production.
- **Don't add `loading="lazy"` blanket-style.** Above-the-fold images need eager loading. Lazy is correct for below-fold, not for everything.
- **Don't use `transform: translate3d(0,0,0)` to "promote to GPU layer" without thinking.** It does promote, but it ALSO creates a new containing block for `fixed` descendants, which breaks modals (Trap 5).
- **Don't rely on dev (Chrome) testing alone for visual polish.** Build the desktop binary and test on Windows + macOS targets at least once before declaring an animation "done." The dev/WebView2 divergence is real.
