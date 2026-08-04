---
stack: [any, desktop, steam, tauri, integrations]
kind: gotcha
last_verified: 2026-08-04
---

# The same judgement implemented twice — and the weaker copy is the one wired to something destructive

**One-liner:** when an app has to answer a yes/no question about external data ("is this a game?", "is this a real user?", "is this spam?"), that judgement tends to get implemented independently in more than one place, using *different methods* of different quality — and the copy nobody audits is reliably the one attached to the most user-visible trigger. This is not schema drift. The copies were never trying to agree; they were written months apart by someone solving a local problem, and only one of them got the good method.

## The concrete case

A Steam journaling app needed to know "is this appid a game, or is it a tool/demo/soundtrack/beta?" That question got answered in **three** places:

| Where | Method | Quality |
|---|---|---|
| Installed-library scan | Steam's own `common/type` from `appinfo.vdf` | authoritative |
| Owned-library sync (Web API) | **nothing** | no filter at all |
| Process watcher's exe map | **name matching** on a skip-list | provably weak |

Each was locally reasonable. Together they produced two separate bugs:

**Bug 1 — two paths disagreed.** The local scan correctly dropped non-games. The owned-library sync had no filter, so the moment a user signed in, every Application and Beta came straight back. Nobody noticed because each path was "working."

**Bug 2 — the weak copy governed the worst trigger.** The exe map feeds the process watcher, which decides whether the app's *quit ritual* fires. Its name skip-list (`["ost", "demo", "tool", "soundtrack", …]`) could never match "Borderless Gaming" or "Lossless Scaling" — neither contains a token. So launching a windowing utility armed the watcher, and closing it **prompted the user to journal a play session about a windowing utility.**

That's the shape worth remembering: *the filter guarding a mere list was good; the filter guarding an interruption was the naive one.*

## Why name matching always loses

The skip-list had already been patched once for a bug its own comment documents: `"ost"` as a substring matched **Lost** Soul Aside and **Ghost** of Tsushima, making them invisible to the watcher. The fix was whole-word matching — better, still wrong.

Measured over a real 389-app library, a name scan for `demo`/`ost`/`beta` flagged: *Democracy 4, Ghostrunner, Ghost of Tsushima, Banishers: Ghosts of New Eden, Lost Skies*. Every one a false positive. Meanwhile the two actual applications matched nothing.

**If the platform exposes a real type field, a name heuristic is never the answer — it fails in both directions at once.**

## How to find these in your own codebase

Grep for the *question*, not the implementation. Every place that asks "is this X?" about the same external entity is a candidate:

```bash
# find every site that filters the same entity
grep -rn "FROM games" src/ | wc -l     # then read each one
```

Then sort the hits by **blast radius, not by visibility**. The list view showing a wrong row is cosmetic. The one wired to a notification, a modal, a delete, a purchase, or an outbound email is the one to fix first — and it is usually the one that got the cheap implementation, precisely because it was written as plumbing rather than as a feature.

## The fixes, in order of value

1. **One exported predicate, not N inline copies.** A shared function (`playableGameWhere(alias)`, `isGame(id)`) that every site calls. Same argument as a shared column list: copies that agree today drift tomorrow.
2. **Authoritative source first, heuristic demoted to fallback.** Don't delete the name list — keep it for when the authoritative source is unreadable, and say so in a comment so nobody promotes it back.
3. **Fix at the layer that makes the decision, not the layer that renders it.** In the case above, the overlay that showed the quit prompt resolved its target *by appid* — filtering there would have created a session with nowhere to land. The watcher was the right layer. Ask "where is the choice made?", not "where did I see the bug?"
4. **Fail open, never closed.** An unclassifiable item must stay *visible*. If the authoritative source is missing or locked, hiding-on-unknown means a transient file-read failure empties the user's entire library.

## Two traps in the classification itself

- **Case.** 28 of the 389 apps reported a lowercase `game` where the rest reported `Game`. A naive `== "Game"` would have hidden 28 real games. Compare case-insensitively, and comment that it is load-bearing rather than defensive.
- **Hiding can be stronger than you intend.** If a list view is the *only* route to an item's detail page, filtering it out makes the item unreachable — not dimmed. No detail, no settings, no way back. **A filter with no escape hatch shouldn't ship**; add the "show hidden items" toggle in the same change, off by default.

## The rule worth carrying

> Before adding a filter, grep for every other place that answers the same question. Rank them by what happens when they're wrong, not by how visible they are. The copy attached to an interruption is the one that was written as plumbing, and it is the one that's naive.

## Related

- [n-copies-of-truth-drift-guard.md](./n-copies-of-truth-drift-guard.md) — the *schema* version: N descriptions of the same data drifting apart.
- [shared-schema-multiple-projections-drift.md](./shared-schema-multiple-projections-drift.md) — same-repo, same-commit drift across N producers feeding one schema.
- [steam-library-integration.md](./steam-library-integration.md) — where `appinfo.vdf` and the librarycache layouts are covered.
