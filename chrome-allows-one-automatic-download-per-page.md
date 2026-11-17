---
stack: [chrome, web, javascript, browser-automation, bookmarklet, downloads]
kind: gotcha
last_verified: 2026-11-17
---

# Chrome lets a page save one file on its own; the next one waits on a prompt until the user clicks

**One-liner:** a script in a web page can save a file (an anchor with `download`, clicked from code) exactly once without asking. After that, Chrome holds every further download behind a "download multiple files" prompt until a real click, Enter, Space or a navigation resets it. A report script that saved an HTML report and then a CSV 1.5 s later got the report and never the CSV, and a re-save 22 minutes later never arrived either. The script saw no error: an anchor click returns nothing either way. Put everything in one file, or give each file its own button that the user clicks.

*Cove Role Check, 2026-11-16, Chrome on Windows 11. The script was a bookmarklet audit, driven by an agent through Claude in Chrome.*

## The rule (Chromium's own description)

From the comments in Chromium's `chrome/browser/download/download_request_limiter.h`:

- Each tab starts out allowing one download (`ALLOW_ONE_DOWNLOAD`).
- The first download is allowed, and the state changes to `PROMPT_BEFORE_DOWNLOAD`. The next one asks the user whether to allow it.
- A mouse click, Enter, the space bar, or navigating to another page resets it to one allowed download.
- If the user allows multiple downloads, that holds until they navigate to a different host. Chrome's site settings also keep a standing "Automatic downloads" choice per site.

A script's own `element.click()` is not user input, so it doesn't reset anything.

## What happened

| When | Started by | Result |
|---|---|---|
| Report | `element.click()` on the panel's Download button, from the agent | Landed in Downloads |
| CSV, 1.5 s later | Same, on the CSV button | Never arrived |
| Regenerated report, 22 min later, same page | Same | Never arrived |

As far as the session shows, no real input reached that window in between, since the agent was driving it. The prompt itself wasn't looked at. It sat in a window nobody was viewing, and an agent must not accept it on the user's behalf anyway. The pattern matches the limiter.

For contrast, an injected export script in another tab built a 4 MB gzip and saved it as that page's only download, and it landed without any prompt.

## What to build

- **One file per save.** Embed the CSV in the HTML report (a table plus a "copy as CSV" button), or zip the files, so one download carries everything.
- **One button per file, clicked by the user.** A real click resets the limit, so each press saves one file. Label the buttons so it's obvious what each saves.
- **Don't trust the click.** If you can see the Downloads folder (an agent with shell access can), check that the file arrived. If you can't, tell the user which button to click instead of saying "saved".
- **Leave the prompt to the user.** Allowing multiple downloads is a permission. Say what the prompt will ask and let them answer it.

## Related

- [[audit-a-web-apps-ui-from-an-injected-script]]: the report script this came from.
- [[hidden-tab-timers-slow-to-one-a-minute]]: the export that saved one 4 MB file at the end of a long pull.
- [[claude-in-chrome-traps]]: driving the user's browser, where a prompt in an unwatched window stalls silently.
