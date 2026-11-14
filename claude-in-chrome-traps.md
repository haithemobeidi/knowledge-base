---
stack: [claude-code, claude-in-chrome, chrome, browser-automation, javascript]
kind: gotcha
last_verified: 2026-11-14
---

# Claude in Chrome: pick the right browser first, return no query strings, and load local scripts through a file input

**One-liner:** three traps that cost real time when an agent drives the user's own Chrome through the Claude in Chrome extension. (1) With **more than one browser connected**, the tools act on whichever one is selected, not the one the user just signed in on: list the connected browsers and select the right one before the first step, and never navigate a tab the user may be signing in on. (2) `javascript_tool` output that looks like a URL query string or cookie comes back as **`[BLOCKED: Cookie/query string data]`**: compare inside the page and return true/false, lengths or parameter names. (3) To run a local script file in a page, put a **file input** on the page and use `file_upload`, then evaluate the text; fetching it from localhost hung the tab for 45 s.

*Cove support work, 2026-11-12 to 11-14 (Windows 11, two Chrome browsers connected).*

## 1. Two connected browsers: the default can be the wrong one

The user signed in to Zendesk and the product dashboard "for you now in the browser". The agent's tab calls went to the other connected browser, which had neither sign-in, and the user had to say "wrong browser" twice. Tabs opened there could not be closed from the session afterwards ("not in tab group"), so they were left for the user.

- **Before the first step:** `list_connected_browsers`, then `select_browser` the one whose tabs match what the user described (`tabs_context_mcp` shows them). If two look plausible, ask which.
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

## Related

- [[audit-a-web-apps-ui-from-an-injected-script]]: the kind of script this loads.
- [[hidden-tab-timers-slow-to-one-a-minute]]: why a long run in the user's browser slows down when they switch tabs.
