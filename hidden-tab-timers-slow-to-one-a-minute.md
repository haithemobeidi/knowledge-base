---
stack: [chrome, web, javascript, timers, browser-automation, bookmarklet]
kind: gotcha
last_verified: 2026-11-14
---

# A long in-page script crawls when its tab is out of view: Chrome slows chained timers to about one wake-up a minute

**One-liner:** a script that runs for minutes inside a web page (a bookmarklet audit, an in-page crawler, a polling loop) slows to a crawl when its tab has been out of view for 5 minutes. Chrome then lets chained timers wake the page about **once a minute**. Measured: a role checker went 24 of 85 rows in 15 minutes while the user watched videos in another tab, then 13 more rows in the minute after they came back. Another tab in front is enough; the computer doesn't have to sleep. Tell the user to keep the tab in front, show progress in the tab title, record time spent hidden, and count waits by tries, so a slowed run waits longer instead of reporting things missing.

*Cove Role Check, 2026-11-13, Chrome on Windows 11.*

## The rules (Chrome's own description)

From [Heavy throttling of chained JS timers beginning in Chrome 88](https://developer.chrome.com/blog/timer-throttling-in-chrome-88):

- A **hidden** page's timers are already limited to about one wake-up a second.
- **Intensive throttling:** once the page has been hidden for **5 minutes**, timers in a chain (a `setTimeout` scheduled from a timer, nesting level 5 or more, which is every polling loop) are aligned to **one wake-up a minute**, provided the page has been silent for 30 seconds and isn't using WebRTC.
- A later "quick intensive throttling" change can start this sooner (about 10 s) for a page that was fully loaded when hidden; whether it is on by default in a given Chrome version wasn't confirmed here.
- `requestAnimationFrame` doesn't run at all in a hidden tab ([[verify-motion-frame-by-frame]]).

"Hidden" means another tab in front, the window minimized or fully covered, or the screen off. A screen wake lock doesn't help: Chrome releases it when the page is hidden.

## Why it is a correctness bug, not only a slow run

A polling wait written against the clock (`while (Date.now() - t0 < 6000)`) gets one or two looks at the page in a throttled tab and then gives up. The checker records "not found" for a button that was only slow to appear. Count tries instead, so the wait has the same number of looks however slowly they come:

```js
// 15 looks, 400 ms apart when the tab is in front, a minute apart when it isn't
const waitFor = async (fn, tries = 15) => {
  for (let i = 0; i < tries; i++) { const v = fn(); if (v) return v; await wait(400); }
  return fn();
};
```

## What to build in

- **Say so up front:** "Keep this tab in front until it says Done."
- **Progress in `document.title`** (`(24/85) Role Check`), so it shows on the tab strip from any other tab.
- **Record time hidden** with `visibilitychange`, and put it in the result ("the tab was out of view for about 12 min, which slows the run"), so a slow run explains itself.
- **Request a screen wake lock while visible**, and request it again on return; it is released on hide.
- If the work must really run unattended, move it out of a page tab (an extension service worker, a headless browser, or a script that calls the API directly).
