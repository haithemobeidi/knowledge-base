---
stack: [web, javascript, browser-automation, shadow-dom, react, intercom, claude-in-chrome]
kind: gotcha
last_verified: 2026-11-17
---

# Admin pages inside a shadow root: ShadowRoot has no innerText, names live in input values, and React rows open through their props

**One-liner:** reading Intercom's Fin admin pages from a script, the main lists rendered inside a shadow root, so `document.body.innerText`, `get_page_text` and the find tool saw nothing.
- **Text:** `shadowRoot.innerText` is `undefined`, because a ShadowRoot isn't an element. Read `[...root.children].map(c => c.innerText)` instead.
- **Names:** names typed into editable rows exist only in `input.value`.
- **Row expanders:** `.click()` and synthetic mouse events did nothing; calling the element's React `onClick` prop worked.
- **Check both trees:** some pages of the same app were plain light DOM.

*Intercom Fin admin (Train > Guidance, Escalation and Attributes), 2026-11-17, Chrome driven through Claude in Chrome.*

## Reading the text

```js
const roots = [...document.querySelectorAll('*')].filter(e => e.shadowRoot).map(e => e.shadowRoot);
const text = roots.map(r => [...r.children].map(c => c.innerText || '').join('\n')).join('\n');
```

The first attempt read `root.innerText` and got `undefined` back, which looked like an empty page. The Guidance page held about 25,000 characters of rules. To get that much out past a tool's output cap, write it into a `<pre>` in `document.body` and read the page text in one call. That replaces the page, so reload afterwards.

## Names live in inputs

Escalation rule names on Intercom's Escalation page sat in editable inputs. They weren't in any element's text, so they appear only through `[...document.querySelectorAll('input')].map(i => i.value)`. Inputs and rows come in the same order, so the names line up with the usage counts.

## Opening a React row

```js
const tr = [...root.querySelectorAll('tr')].find(r => r.innerText.trim().startsWith('Topic'));
const div = [...tr.querySelectorAll('div')].find(e => {
  const k = Object.keys(e).find(k => k.startsWith('__reactProps')); return k && e[k].onClick;
});
const k = Object.keys(div).find(k => k.startsWith('__reactProps'));
div[k].onClick({ preventDefault() {}, stopPropagation() {}, target: div, currentTarget: div, nativeEvent: {} });
```

- **Never fire `onClick` on an unlabelled button** in a settings row. The same row had four buttons: "Edit", plus three usage counts. On other pages a row button can be an enable/disable toggle. Read each button's text first.
- **Stop at a stale editor.** After switching rows, Intercom's attribute editor kept showing the first attribute's fields. Two tries is enough. Get the data another way: here, the value lists came from the helpdesk's own ticket-field API.

## Check both trees

The Escalation page rendered in the light DOM, where the shadow-root reader found one character. Probe both before deciding a page is empty:

```js
document.body.innerText.length;                                                  // light DOM
[...document.querySelectorAll('*')].filter(e => e.shadowRoot).map(e => e.id);    // shadow hosts
```

## Related

- [[claude-in-chrome-traps]]: output caps and blocked strings.
- [[audit-a-web-apps-ui-from-an-injected-script]]
