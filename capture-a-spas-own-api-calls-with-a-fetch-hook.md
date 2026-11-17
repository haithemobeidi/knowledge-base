---
stack: [web, javascript, browser-automation, graphql, spa, claude-in-chrome]
kind: technique
last_verified: 2026-11-17
---

# To learn the exact API calls a single-page app makes, hook fetch and XHR, then move the app with pushState so the hook survives

**One-liner:** when an app's API isn't documented and introspection is off, let the app write the queries for you. Wrap `window.fetch` and `XMLHttpRequest.prototype.send` in the page to record request bodies. Then change route with `history.pushState(...)` plus `dispatchEvent(new PopStateEvent('popstate'))`: the router renders the new page and fires its requests without a reload, so the hook is still there to catch them. Typing into the app's own search box shows the filter shape the API expects. Replay the captured query with your own variables.

*Cove's admin dashboard (React, one GraphQL endpoint, introspection off), 2026-11-17, Chrome driven through Claude in Chrome. Four list queries (users across sites, sites, tenants with access-control settings, announcements) were captured this way in about a minute each.*

## Why the usual routes fail

- **One endpoint for everything.** Every operation is a POST to the same URL, so a network log filtered by URL shows nothing useful. The operation name and query text live only in the request body.
- **Network tools show URLs, not bodies.** `read_network_requests` lists the calls but not what was sent.
- **A real navigation wipes the hook.** Navigating the tab reloads the page and discards anything you put on `window`.

## The hook

Install it after the page has loaded, before you move the app:

```js
window.__cap = [];
const of = window.fetch;
window.fetch = function (u, o) {
  if (o && typeof o.body === 'string' && o.body.includes('operationName')) window.__cap.push(o.body);
  return of.apply(this, arguments);
};
const os = XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.send = function (b) {
  if (typeof b === 'string' && b.includes('operationName')) window.__cap.push(b);
  return os.apply(this, arguments);
};
```

## Move the app without a reload

```js
history.pushState({}, '', '/admin/users');
dispatchEvent(new PopStateEvent('popstate'));
await new Promise(r => setTimeout(r, 4000));
window.__cap.map(b => JSON.parse(b).operationName);   // which queries the page ran
```

Most client routers (React Router included) listen for `popstate`, so they render the route and run its queries. The page never reloads and the hook keeps recording.

## Get the filter shape from the app's own search box

The first load often sends an empty filter. To see how a search is expressed, type into the page's search input the way React expects. The native value setter plus an `input` event updates its state:

```js
const inp = document.querySelector('input[placeholder*="Search"]');
Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(inp, 'street');
inp.dispatchEvent(new Event('input', { bubbles: true }));
```

At Cove that showed `orGroups` of `CONTAINS` conditions on first name, last name, email and others. Replaying with a single `{field: 'email', operator: 'CONTAINS', value}` then found one user exactly.

## Replay

```js
const gq = async (query, variables) => (await fetch('https://api.example.com/gql', {
  method: 'POST', credentials: 'include',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query, variables })
})).json();
const j = JSON.parse(window.__cap.find(b => b.includes('ListUsers')));
await gq(j.query, { ...j.variables, filter: { items: [{ field: 'email', operator: 'CONTAINS', value: 'name@' }], orGroups: [] } });
```

Replay the captured query whole (it often carries fragments) and change only the variables.

## Traps

- **Reads only.** Replaying a captured mutation is how a hand-built write wipes fields. For a change, use [[guarded-write-through-an-apps-own-form]].
- **Agent output limits.** Return summaries and strip URLs and query strings; Claude in Chrome blocks some output ([[claude-in-chrome-traps]]).
- **Initial load and search can use different filter keys** (`items` versus `orGroups`). Copy whatever the app sent for the case you need.

## Related

- [[graphql-errors-map-a-schema-without-introspection]]: the other way to map a schema when introspection is off.
- [[audit-a-web-apps-ui-from-an-injected-script]]: the same page-injected approach, for UI checks.
- [[pushstate-overlay-history-drift]]
