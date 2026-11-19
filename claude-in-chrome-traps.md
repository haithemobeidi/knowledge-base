---
stack: [claude-code, claude-in-chrome, chrome, browser-automation, javascript]
kind: gotcha
last_verified: 2026-11-18
---

# Claude in Chrome: pick the right browser first, return no query strings, load local scripts through a file input, use a second profile for a second account, open local pages yourself, record tests as GIFs, switch pages inside the app when a draft is open, and read live data before the site signs you out

**One-liner:** eight traps and habits that cost or saved real time when an agent drives the user's own Chrome through the Claude in Chrome extension. (1) With **more than one browser connected**, the tools act on whichever one is selected, not the one the user just signed in on: list the connected browsers and select the right one by **deviceId** before the first step (the "Browser 1" and "Browser 2" names get reassigned), and never navigate a tab the user may be signing in on. (2) `javascript_tool` output that looks like a URL query string or cookie comes back as **`[BLOCKED: Cookie/query string data]`**: compare inside the page and return true/false, lengths or parameter names. (3) To run a local script file in a page, put a **file input** on the page and use `file_upload`, then evaluate the text; fetching it from localhost hung the tab for 45 s. (4) The agent **couldn't reach an incognito window**, even with "Allow in Incognito" on. To drive a second account beside the main one, make a separate Chrome profile with the extension: it shows up as a second connected browser with its own cookies. (5) The tools can't open `file://` pages ("Can't interact with browser-internal or unparseable URLs"); open a generated local page in the user's default browser from the shell instead. (6) The built-in **GIF recorder** turns a test into proof the user can show: start, screenshot, act, screenshot, stop, export to Downloads. (7) A page with **unsaved input** answers `navigate` with a "Leave site?" dialog that blocks the tools: change the route inside the app with `history.pushState` and a `popstate` event instead. (8) A long session can **outlive the site's sign-in**: do the live verification read before the end-of-day wrap, because the agent can't sign back in.

*Cove support work, 2026-11-12 to 11-18 (Windows 11, two Chrome browsers connected).*

## 1. Two connected browsers: the default can be the wrong one

The user signed in to Zendesk and the product dashboard "for you now in the browser". The agent's tab calls went to the other connected browser, which had neither sign-in, and the user had to say "wrong browser" twice. Tabs opened there could not be closed from the session afterwards ("not in tab group"), so they were left for the user.

- **Before the first step:** `list_connected_browsers`, then `select_browser` the one whose tabs match what the user described (`tabs_context_mcp` shows them). If two look plausible, ask which.
- **Select by `deviceId`, not by name.** The names are labels handed out by the list, not identities. After the main browser's extension reconnected, the two browsers swapped names between two calls 16 minutes apart, while each `deviceId` stayed the same. Note the `deviceId` of each browser once ("the staff one", "the test-account one") and select by it before each block of work.
- **Never navigate a tab the user might be using to sign in.** Open your own tab with `tabs_create_mcp`. Navigating theirs mid-login throws their work away.

## 2. Query strings in tool output are blocked

Returning a link such as `https://host/View?workOrderId=…&siteNetworkId=…` from `javascript_tool` came back as the literal text `[BLOCKED: Cookie/query string data]`, twice in a row, with nothing else. The filter acts on the output text, so the page itself can still read the URL. Do the comparison in the page and return only the verdict:

```js
// Is the email's link exactly the address we expect?
const a = [...document.querySelectorAll("a")].find((x) => /New activity/.test(x.innerText));
JSON.stringify({ found: !!a, exact: a?.href === EXPECTED, path: a?.href.split("?")[0],
                 params: a ? [...new URL(a.href).searchParams.keys()] : [] });
```

That still proves the exact link character for character, without the value crossing the filter. The same goes for attachment and image URLs (signed URLs carry tokens in the query): return `url.split("?")[0]`.

A second filter catches text that looks like encoded data. Returning `location.pathname` on a page whose path held a random 10-character record ID came back as `[BLOCKED: Base64 encoded data]` (Nov 17). Return a yes/no or a fixed label instead of raw IDs and paths.

## 3. Load a local script through a file input, not from localhost

To test a script file from disk inside a live page, `fetch("http://127.0.0.1:…")` from the https page hung the tab for about 45 s, most likely Chrome's local network access prompt waiting on a click nobody could make. What works:

```js
// in the page, via javascript_tool
const i = document.createElement("input");
i.type = "file"; i.id = "agent-load"; document.body.appendChild(i);
```

Then `file_upload` the script to `#agent-load`, and:

```js
const text = await document.getElementById("agent-load").files[0].text();
(0, eval)(text);                       // global scope, as a bookmarklet would run
```

It runs the exact file on disk, with no retyping and no copy drift between what you tested and what you ship. It needs a page whose Content Security Policy allows `eval`; the product dashboard here did. Remove the input afterwards.

## 4. A second account: a separate Chrome profile, not incognito

The job needed the app as a restricted test account while the main window stayed signed in as staff. The user's plan was incognito, and they turned on **Allow in Incognito** for the Claude extension and opened an incognito window. The agent still couldn't reach it (November 2026 build):

- The tab from `tabs_context_mcp` opened in the normal window. The app's own API (`{ me { role } }`) answered with the staff role, not the test account.
- The tab list showed only the agent's own tab group.
- `list_connected_browsers` showed one browser.

None of the tools used could open or pick an incognito tab. What works:

1. In Chrome: profile picture > **Add** > **Continue without an account**. Name it after the account ("App +test").
2. In that profile, install the Claude extension and sign in to Claude.
3. The profile now appears as a **second connected browser**, with its own cookies. The test account stays signed in there beside the staff session in the main profile.
4. The user signs the test account in. A one-time code is theirs to type.
5. Select that browser by `deviceId` (section 1) whenever the work moves between the two.

Two side effects to plan for. Tabs opened in one browser can't be closed once the session has switched to the other (section 1). And on Windows a fully covered window counts as hidden, so a long run in the profile window can slow down whenever the other window covers it. Keep the two side by side ([[hidden-tab-timers-slow-to-one-a-minute]]).

## 5. Local pages (`file://`) are out of reach

The agent built a local HTML page (a copy-paste helper) and tried to check it in the browser. `navigate` to a `file:///C:/...` URL failed with "Can't interact with browser-internal or unparseable URLs". So:

- Open it for the user from the shell: `Start-Process <path>` in PowerShell (`start "" <path>` in cmd) opens it in their default browser.
- Check what you can without a browser: parse the output, count the elements you expect, compile any script.
- Say plainly which interactive part you couldn't test (for example, the clipboard buttons), so the user knows what to watch on first use.

## 6. Record a test as a GIF, so "did you test it?" has an answer

The support lead wanted proof of each reproduction attempt. The extension's `gif_creator` does it with no setup:

1. `start_recording`, then take a screenshot at once: that becomes the first frame.
2. Run the steps. Clicks, typing, scrolls and navigations are captured, each with a label.
3. Take a final screenshot, then `stop_recording`.
4. `export` with `download: true` and a name that says what it shows, e.g. `<ticket>-<what>-<role>-<site>-<date>.gif`. It lands in the user's Downloads.

22 frames came to about 5 MB at 1229x980. It's frame-per-action, not smooth video; for real video, tell the user when you start so they can record (on Windows, Snipping Tool's video mode, Win+Shift+R). The agent can't start an OS recorder itself.

## 7. Unsaved input blocks `navigate`: change the route inside the app

A page had text typed into a form, not submitted. `navigate` to the next record's URL never finished: the page raised the browser's "Leave site?" dialog (`beforeunload`), and a browser dialog blocks every later tool call until the user dismisses it by hand.

In a single-page app, don't leave the page. Change the route the way the app's own links do:

```js
history.pushState({}, '', nextPath);   // the path the app's own link would go to
window.dispatchEvent(new PopStateEvent('popstate'));
```

The app's router picks up the new path and renders the new record. No unload happens, so no dialog, and the unsent text on the first one is still there when you come back. Check the page title or a heading afterwards to confirm the switch.

## 8. The site can sign you out mid-session: read live data before the wrap

At the end of a long day the agent went to re-read 30 records' statuses for its handoff. Every call came back 401 and the tab had moved to a sign-in page: the site caps session length no matter how active the tab is. The agent can't type credentials, so the handoff had to be written from local notes and say so.

- **Do the live verification read while the user is still working,** not after they've said goodnight.
- **A burst of failures from parallel calls looks like rate limiting.** Check one call's status code and the tab's URL before retrying.
- **Text typed into a page but not submitted may not survive the sign-out.** Keep a copy of every draft in a local file as it's written.
- **Write the handoff honestly:** name which facts are the user's word, which are local notes, and that nothing was re-read live ([[handoff-for-a-reader-with-no-memory]]).

## Related

- [[audit-a-web-apps-ui-from-an-injected-script]]: the kind of script this loads.
- [[hidden-tab-timers-slow-to-one-a-minute]]: why a long run in the user's browser slows down when they switch tabs or cover the window.
- [[chrome-allows-one-automatic-download-per-page]]: why a second file saved from a page the agent is driving never arrives.
- [[capture-a-spas-own-api-calls-with-a-fetch-hook]] and [[read-shadow-dom-admin-pages-from-a-script]]: reading apps through this extension.
