---
stack: [web, spa, javascript, testing, verification, bookmarklet, tailwind, permissions]
kind: pattern
last_verified: 2026-11-17
---

# Check what a signed-in user can see across a web app: one injected script, a hidden same-origin iframe, and four traps

**One-liner:** to check what a signed-in user can see across dozens of pages of a single-page web app (a role or permission audit, a "does every page still have its button" sweep) without its API or a test harness, inject one script into the app's own tab and load each page in a hidden **same-origin iframe**. The script reads the real rendered UI with the real session, about 3 s a page, and it survives because the top page never navigates. Four traps decide whether its answers are true: read only after the frame's `load` and then poll, pick the **visible** copy of duplicated responsive markup, read "disabled" from the **property** and never from class names, and count a page only if the frame **stayed on its address**. Then give every result a reason, or a correct report reads as wrong. For a permission audit, each check must **test the action the spec claims**, not a stand-in like "the page opens". Score "locked" (visible but greyed or read-only) as its own state: a match where the spec says no, a flag where it says yes. And give anyone spot-checking by hand a link to the exact screen that holds the control.

*Cove Role Check, 2026-11-12 to 11-16: a bookmarklet that checked 66, later 81, dashboard features for one role in 4 to 7 minutes, and on a restricted account found about 30 features missing.*

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

## What each check has to prove (a permission audit)

The first version answered "yes" when the feature's button was on screen and not flagged disabled. Several rows only checked that a page opened, though the spec row was an action (configure settings, approve, edit). A by-hand spot-check as the restricted role then disagreed on two features. One was a checker error. The other was a bad spot-check link: the person was sent to a list page with no Add button, while the Add button lives on a sibling page with a similar name. These rules came out of going through it feature by feature on the role's own screen:

1. **Test the action the spec claims.** If the feature is a control on a record (a status menu, an Edit button, a Save on a settings page), open a real record and read that control. If it's a form, open the form and confirm it renders for the role, then leave it unsaved. Read a control's enabled state; don't operate it on live data. The most privileged account's view, read-only, is the reference for what each control looks like. A row that still only checks "the page opens" says so in its note. 13 of 81 rows were still stand-ins when this was written.
2. **Prove each check both ways.** A check counts once it has said yes for a role that has the feature and no for one that doesn't ([[negative-control-before-trusting-a-probe]]).
3. **Decide only after the address holds still.** A page the role may not use rendered at its own address for under a second and then redirected home. One run reported a Create button on such a page. The cause wasn't proven, so the fix closes both ways it could happen: decide only after the frame's address has stayed the same for 2 s, and check the address again after finding the button.
4. **"Locked" is its own state.** Greyed out or read-only means the role can see the control but not use it, and roles mix read and write access. Where the spec says no, locked is a **match**. Where the spec says yes, locked is a **flag to check**, because the record's own state can lock a control: an approval control stays greyed until the item is closed. On one role all 9 locked controls were "no" in the spec, so all 9 became matches.
5. **A feature with two halves can be "Limited".** "Create and configure tasks" covered one-off and recurring tasks, and the role could make one-off tasks only. Check both halves, and say in the note which one the role has.
6. **A table-driven check can't see what the table doesn't list.** Checking each row of the role's own table misses features the app gives the role that the table never mentions. In this audit it was a New button on a consent-forms page. Walk the role's own menu as well, and report extras in a section of their own.
7. **Check the spec's date before trusting a difference.** The owner had a newer matrix (a PDF dated that day) with rows the help center article lacked. The article caught up a few hours later and then matched the PDF cell for cell (90 rows, compared by script). Compare the checker's source with the owner's current copy first.
8. **Give a spot-checker the exact screen.** Link the page that holds the control, and name the control. A list page with a similar name cost a round of "the checker is wrong" that wasn't.

Once a result has been checked by eye, keep it. Rerun only the rows a fix touched (a single-row test mode, with the result patched into the saved run), not the whole role.

## Getting the script into the page

A bookmarklet works and needs nothing installed. Once the script grew to about 75 KB, dragging the link to the bookmarks bar became unreliable, so the setup page also offers the code to copy and paste as a new bookmark's URL. When an agent drives the browser, load the file through a file input instead of retyping it ([[claude-in-chrome-traps]]). Give the script a test hook (`checker.test("<row text>")`) so one wrong row can be rerun alone.

## What this does not prove

A run from an admin account proves the checker finds things that are there. It does not prove it reports things that are missing; that needs a real restricted account ([[negative-control-before-trusting-a-probe]]). An agent can drive that account in a separate Chrome profile beside the admin window ([[claude-in-chrome-traps]]). Keep the two windows side by side, because a covered window counts as hidden ([[hidden-tab-timers-slow-to-one-a-minute]]). Save the report as one file, because Chrome holds a page's second automatic download behind a prompt ([[chrome-allows-one-automatic-download-per-page]]).
