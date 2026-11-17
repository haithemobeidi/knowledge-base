---
stack: [chrome, web, javascript, timers, browser-automation, bookmarklet, web-workers, windows]
kind: gotcha
last_verified: 2026-11-17
---

# A long in-page script crawls when its tab is out of view: Chrome slows chained timers to about one wake-up a minute

**One-liner:** a script that runs for minutes inside a web page (a bookmarklet audit, an in-page crawler, a polling loop) slows to a crawl when its tab has been out of view for 5 minutes. Chrome then lets chained timers wake the page about **once a minute**. Measured: a role checker went 24 of 85 rows in 15 minutes while the user watched videos in another tab, then 13 more rows in the minute after they came back. Another tab in front is enough, and on Windows so is another window covering the whole browser window. The computer doesn't have to sleep. Tell the user to keep the tab in front, show progress in the tab title, record time spent hidden, and count waits by tries, so a slowed run waits longer instead of reporting things missing. Don't pause the work while hidden: covered windows made a pause stall constantly. For work that has to keep going, a dedicated Web Worker held 1 request a second for about 44 minutes, but a worker made from a Blob can't resolve relative URLs, and the first one failed with no error at all.

*Cove Role Check, 2026-11-13 and 11-16, and a support-desk export, 2026-11-16. Chrome on Windows 11.*

## The rules (Chrome's own description)

From [Heavy throttling of chained JS timers beginning in Chrome 88](https://developer.chrome.com/blog/timer-throttling-in-chrome-88):

- A **hidden** page's timers are already limited to about one wake-up a second.
- **Intensive throttling:** once the page has been hidden for **5 minutes**, timers in a chain (a `setTimeout` scheduled from a timer, nesting level 5 or more, which is every polling loop) are aligned to **one wake-up a minute**, provided the page has been silent for 30 seconds and isn't using WebRTC.
- A later "quick intensive throttling" change can start this sooner (about 10 s) for a page that was fully loaded when hidden; whether it is on by default in a given Chrome version wasn't confirmed here.
- `requestAnimationFrame` doesn't run at all in a hidden tab ([[verify-motion-frame-by-frame]]).
- The post covers `setTimeout` and `setInterval` in pages. It says nothing about workers.

"Hidden" means another tab in front, the window minimized or fully covered (next section), or the screen off. The post's own words: browsers "may consider a page hidden whenever its content is totally not-visible". A screen wake lock doesn't help: Chrome releases it when the page is hidden.

## A covered window is hidden too (Windows)

Chromium's [Windows native window occlusion tracking](https://chromium.googlesource.com/chromium/src/+/main/docs/windows_native_window_occlusion_tracking.md) treats a Chrome window as occluded when the windows above it cover its whole rectangle, counting other apps' windows as well. An occluded window's foreground tab is then handled like a background tab: "rendering stops, and js is throttled". This is Windows only. Partial cover doesn't count, so side by side is fine.

Measured: the role checker's `visibilitychange` log recorded its tab hidden for 363 of the run's 453 seconds. It was the front tab of its own window the whole time; the agent was working in another Chrome window on top of it. So "keep the tab in front" isn't enough on Windows. Say "keep that window uncovered; side by side is fine".

## Don't pause the work while the page is hidden

The tempting fix is a loop that waits while `document.hidden` is true and shows "(paused)" in the title. It was tried and removed the same day. On a working desktop another window sits on top of the run all the time, so the pause stalled it again and again, while the user saw nothing wrong. And it bought nothing: the run that was out of view for 80% of its 7.5 minutes still came out right, and every result checked by eye matched, because its waits counted tries. Keep the hidden-time note in the report so a slow run explains itself, and let it carry on.

## Why it is a correctness bug, not only a slow run

A polling wait written against the clock (`while (Date.now() - t0 < 6000)`) gets one or two looks at the page in a throttled tab and then gives up. The checker records "not found" for a button that was only slow to appear. Count tries instead, so the wait has the same number of looks however slowly they come:

```js
// 15 looks, 400 ms apart when the tab is in front, a minute apart when it isn't
const waitFor = async (fn, tries = 15) => {
  for (let i = 0; i < tries; i++) { const v = fn(); if (v) return v; await wait(400); }
  return fn();
};
```

## For work that must keep going: a dedicated Web Worker

A data pull read every comment on 2,711 support tickets from the support desk's REST API, at about 1 request a second, using the signed-in session in one of the user's tabs. The loop ran in a dedicated worker created from a Blob:

- From 237 to 1,918 tickets in 1,698 seconds (0.99 a second) in the middle of the run.
- The worker fetched the remaining 2,520 in about 44 minutes. The pull ended with all 2,711 and 0 errors, and no rate-limit responses had come back by the last check, 71% of the way through.
- Meanwhile the user used the rest of the browser and couldn't even find the tab.

One gap: the tab's visibility wasn't logged during the pull, so this doesn't prove the tab was hidden for all of it. Log `document.visibilityState` from the page with each progress check, and the run proves it.

```js
const src = `onmessage = async (e) => {
  const { ids, origin } = e.data;                 // absolute URLs: see the trap below
  const sleep = (ms) => new Promise((s) => setTimeout(s, ms));
  for (const id of ids) {
    const t0 = Date.now();
    for (let tryNo = 0; tryNo < 5; tryNo++) {
      try {
        const r = await fetch(origin + "/api/items/" + id, { credentials: "include" });
        if (r.status === 429) { postMessage({ k: "429" }); await sleep(30000); continue; }
        postMessage(r.ok ? { k: "ok", id, data: await r.json() } : { k: "err", id, s: r.status });
        break;
      } catch (err) { postMessage({ k: "err", id, s: String(err) }); await sleep(5000); }
    }
    await sleep(Math.max(0, 1000 - (Date.now() - t0)));   // about 1 request a second
  }
  postMessage({ k: "done" });
};`;
const w = new Worker(URL.createObjectURL(new Blob([src], { type: "text/javascript" })));
w.onmessage = (e) => { /* keep results on the page, e.g. window.__pull */ };
w.postMessage({ ids, origin: location.origin });
```

- The worker has the page's origin, so same-origin requests carry the session cookies. No API token is needed.
- It needs a page whose Content Security Policy allows `blob:` workers; the support desk's did.
- **Show progress on the page itself.** Half an hour in, the user asked "which tab? ... i don't see anything happening". A fixed bar across the top of the page with the live count ("1,926 of 2,711 tickets") answered it. The tab title works too.
- **Save once, at the end.** Build one file (gzip it with `CompressionStream`) and save it with a single anchor download. A page gets one automatic download before Chrome starts asking ([[chrome-allows-one-automatic-download-per-page]]).

### The trap: relative URLs fail inside a `blob:` worker, silently

A worker made from a Blob URL has that URL (`blob:https://host/<uuid>`) as its base, and a path can't be resolved against it. `fetch("/api/...")` rejects with a TypeError. The same parse in Node's WHATWG `URL`, `new URL("/api/x", "blob:https://host/uuid")`, throws `ERR_INVALID_URL`, while a full `https://` URL parses fine.

It failed with no signal. The first worker's async `onmessage` had no `try`, so the rejection stayed inside the worker. `worker.onerror` didn't fire, and after 10 seconds the page showed 0 new tickets and 0 errors. Pass `location.origin` in, build absolute URLs, and catch each fetch and post the error back, as above. The second worker, with only those changes, moved at once: 38 tickets in its first 38 seconds.

## What to build in

- **Say so up front:** "Keep this tab in front, and its window uncovered, until it says Done."
- **Progress in `document.title`** (`(24/85) Role Check`), so it shows on the tab strip from any other tab, and on the page itself for anyone looking at it.
- **Record time hidden** with `visibilitychange`, and put it in the result ("the tab was out of view for about 12 min, which slows the run"), so a slow run explains itself. Record it; don't pause on it.
- **Request a screen wake lock while visible**, and request it again on return; it is released on hide.
- If the work must really run unattended, move it out of the page's own timers: a dedicated Web Worker (above), an extension service worker, a headless browser, or a script that calls the API directly.
