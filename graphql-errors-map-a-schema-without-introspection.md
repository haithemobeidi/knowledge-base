---
stack: [graphql, api, web, javascript, reverse-engineering]
kind: technique
last_verified: 2026-11-12
---

# With GraphQL introspection off, the validation errors still map the schema one guess at a time

**One-liner:** a GraphQL server with introspection disabled refuses `__schema` ("GraphQL introspection has been disabled…", `GRAPHQL_VALIDATION_FAILED`), but its ordinary validation errors still describe the schema. "Cannot query field X on type Y" names the parent type; "Field "user" argument "id" of type "ID!" is required" names an argument and its type; "Unknown argument "search" on field "Query.users"" rules one out; "Field "GQLFilterInput.items" of required type "[GQLFilterItemInput!]!" was not provided" spells out an input shape. Send a batch of guesses, one query each, and keep a map of guess to answer. A handful of calls found the signed-in user's role and every internal role name in a product API with no public docs.

*Cove's dashboard API, 2026-11-12, called from the signed-in dashboard tab with its session cookie. Queries only.*

## Use it only where you're allowed to

This is for an API you are entitled to call, as yourself: your own product, or a vendor's product where your signed-in account already sees the data and only the docs are missing. Read-only queries only: never guess at mutations, never use another person's session, and stop at what the task needs.

## The loop

Run it from the app's own tab, so the request carries the session the app uses. Take the endpoint from the app's own requests in the network tab; here it was on a separate API host, and `credentials: "include"` sent the cookie:

```js
const gql = async (q) => {
  const r = await fetch(API_URL, { method: "POST", credentials: "include",
    headers: { "content-type": "application/json" }, body: JSON.stringify({ query: q }) });
  const j = await r.json();
  return j.errors ? "ERR " + j.errors[0].message : "OK " + JSON.stringify(j.data).slice(0, 80);
};
const guesses = ["me { id }", "currentUser { id }", "viewer { id }", "user { id }"];
const out = {};
for (const g of guesses) out[g] = await gql(`{ ${g} }`);
JSON.stringify(out);
```

What the answers said, in order:

| Guess | Answer | What it taught |
|---|---|---|
| `{ __schema { types { name } } }` | introspection has been disabled | the normal route is closed |
| `currentUser`, `viewer`, `self`, `session`, `getMe` | Cannot query field "…" on type "Query" | not root fields |
| `user` | argument "id" of type "ID!" is required | a root field, and its argument |
| `me { id }` | OK | the root field for the signed-in user |
| `me { roles }`, `me { userRole }` | Cannot query field "…" on type "GQLUser" | the user type's real name, and two wrong fields |
| `me { role }` | OK "cove-admin" | the answer |
| `users { id }` | Cannot query field "id" on type "GQLUserPage" | a paged list: try `items` |
| `users(search: …)` | Unknown argument "search" on field "Query.users" | not a search argument |
| `users(filter: {…})` | "GQLFilterInput.items" of required type "[GQLFilterItemInput!]!" was not provided | the filter's exact shape |

The working list query was `users(filter: {items: [{field, operator: CONTAINED_IN, value}]}) { items { id role } }`.

## Habits that make it fast

- **Read the type name in every error.** `GQLUserPage` instead of `GQLUser` says "paged wrapper", which turns the next guess from a dozen names into one (`items`).
- **Guess the names the app's own UI uses**, and the common conventions (`me`, `items`, `nodes`, `edges`, `totalCount`, `filter`, `input`, `id`).
- **Batch per round**, one guess per query, because one bad field fails the whole query. Return a compact map, not the full responses.
- **Watch the network tab first.** The app's own requests show real query shapes, and are often enough on their own.
- No "Did you mean …?" suggestions came back here; many servers turn those off along with introspection, so don't count on them.

Write what you learn down where the next person will find it (operations, argument shapes, which filters work and which error), because none of it is documented anywhere else.
