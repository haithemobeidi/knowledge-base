---
stack: [web, spa, javascript, testing, verification, bookmarklet, tailwind]
kind: pattern
last_verified: 2026-11-13
---

# Check what a signed-in user can see across a web app: one injected script, a hidden same-origin iframe, and four traps

**One-liner:** to check what a signed-in user can see across dozens of pages of a single-page web app (a role or permission audit, a "does every page still have its button" sweep) without its API or a test harness, inject one script into the app's own tab and load each page in a hidden **same-origin iframe**. The script reads the real rendered UI with the real session, about 3 s a page, and it survives because the top page never navigates. Four traps decide whether its answers are true: read only after the frame's `load` and then poll, pick the **visible** copy of duplicated responsive markup, read "disabled" from the **property** and never from class names, and count a page only if the frame **stayed on its address**. Then give every result a reason, or a correct report reads as wrong.

*Cove Role Check, 2026-11-12 and 11-13: a bookmarklet that checked 66 dashboard features for one role in about 4 minutes, and on a restricted account found about 30 features missing.*

## The technique

```js
const frame = document.createElement("iframe");
// A real size, moved off-screen: the pages must lay out the way a user sees them,
// because visibility checks (offsetParent, sizes) need layout.
frame.style.cssText = "position:fixed;left:-6000px;top:0;width:1500px;height:1000px;border:0";
frame.setAttribute("aria-hidden", "true");
document.body.appendChild(frame);
const fd = () => frame.contentDocument;            // same origin, so readable

function goto(path) {
  return new Promise((res) => {
    const done = async () => {
      frame.removeEventListener("load", done);
      for (let i = 0; i < 25; i++) { await wait(400); if (headings().length) break; }  // SPA renders after load
      await wait(1000);
      res({ final: frame.contentWindow.location.pathname, heads: headings() });
    };
    frame.addEventListener("load", done);
    frame.src = path;
  });
}
```

Why a frame and not navigation: navigating the top page unloads the script. Why not `fetch` the page: a client-rendered app returns the same empty shell for every path, and the content only exists after its JavaScript runs (see [[negative-control-before-trusting-a-probe]]). The frame runs that JavaScript with the user's cookies, so it sees exactly what they see.

Clean up on a second click (remove any frame from an earlier run before adding one), and cache each page's reading so twenty checks on one page load it once.

## The four traps

**1. Read after `load`, then poll.** Reading straight after setting `src` reads the previous page. After `load`, the heading is often there before lists and some buttons, so wait for the specific thing with a bounded poll before deciding it is absent. Count the poll in tries, not clock time: a hidden tab slows timers to a crawl and a clock-based timeout then reports "missing" for things that were only slow ([[hidden-tab-timers-slow-to-one-a-minute]]).

**2. Responsive apps render the nav twice. Use the visible copy.** A hidden mobile menu and the visible desktop sidebar carry the same links. The first walk used the hidden copy: labels came out shifted, and `innerText` of the hidden element lost its newlines, so the site name came back as one run-on string. Filter on `e.offsetParent && e.getBoundingClientRect().width > 0`, and exclude the nav itself when looking for a page's own buttons.

**3. "Disabled" comes from the property, never from class names.** Tailwind variants like `disabled:opacity-50` sit on every working button, so a class regex reads working controls as greyed out (two did). Use:

```js
const isOff = (b) => b.disabled === true
  || b.getAttribute("aria-disabled") === "true"
  || b.classList.contains("disabled");          // an exact token, not a substring
```

For a field, also `readOnly`.

**4. A page counts only if the frame stayed on its address and shows the expected heading.** Without permission the app did not show an error. It redirected to its home page, which rendered fine and had buttons of its own. Compare the frame's final `location.pathname` with the requested one, and look for the heading you expect, before reading anything on it. "Redirects to Shortcuts" is the result, and it is the common shape of "not visible".

## The report: a state and a reason on every cell

The first report said "Yes" or "No" per feature. The person reading it doubted a correct run, because "Yes" alone does not say what was seen. Each cell now carries a state (Shown / Shown but locked / Limited / Not visible / Not checked) and a specific note: "New Task button on the Tasks page (/tasks)", "/work-order-groups redirects to Shortcuts". The reader can check any cell in ten seconds, and a wrong note points straight at the wrong check. Also check each subject only against its own expectations: comparing a role against every table in the matrix added rows from other tables as false "extra" findings.

## Getting the script into the page

A bookmarklet works and needs nothing installed. Once the script grew to about 75 KB, dragging the link to the bookmarks bar became unreliable, so the setup page also offers the code to copy and paste as a new bookmark's URL. When an agent drives the browser, load the file through a file input instead of retyping it ([[claude-in-chrome-traps]]). Give the script a test hook (`checker.test("<row text>")`) so one wrong row can be rerun alone.

## What this does not prove

A run from an admin account proves the checker finds things that are there. It does not prove it reports things that are missing; that needs a real restricted account ([[negative-control-before-trusting-a-probe]]).
