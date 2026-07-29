---
stack: [product-design, ux, information-architecture]
kind: pattern
last_verified: 2026-07-29
---

# Two surfaces separated only by a threshold will collide — time is a knob *within* a surface, never the divider *between* two

**One-liner:** "recent items here, older items there" feels like clean information architecture and is actually one list with a seam in it — the two queries overlap for whatever population sits near the boundary, an action in one surface makes the item reappear in the other so the button looks broken, and items migrate between surfaces on their own as time passes; the fix is to divide by **what evidence you have about the item**, which is a property that doesn't drift.

## The shape

You have a list of things and want to surface them in more than one place. The obvious split is time:

- "Recently played" / "Played a while ago" / "Haven't touched in months"
- "New" / "This week" / "Older"
- "Due soon" / "Overdue"
- "Active projects" / "Stale projects"

Each surface gets a threshold. Ship it, and the trouble starts.

## Failure 1: the buttons stop working

The version that made this obvious: a "remind me about this game" feature delivered matured reminders into a row, and the *same row* also auto-surfaced games you hadn't played in a while. Both used the same 14-day constant.

So virtually every matured reminder was simultaneously an automatic candidate. Un-setting a reminder removed the game from the reminder feed — and the automatic feed instantly re-picked it up, into the same row, at the same position.

**The button visibly did nothing.** No error, no bug report that makes sense, just "un-remind is broken." It wasn't broken; it did exactly what it said, and a second query put the card straight back.

This is the general case: when two feeds share a slot and their predicates overlap, **removing an item from one feed is not removal.** Any per-item action in either surface is suspect.

## Failure 2: items move house on their own

The subtler one, and it survives even if you fix the overlap.

If surface A is "0–14 days" and surface B is "15+ days," then an item you did nothing to will disappear from A and appear in B overnight. From the user's side, a thing they know moved somewhere else while they weren't looking, and nothing they did caused it.

Location is one of the strongest memory cues in an interface. Spending it on "how long ago" — a value that changes continuously and that the user is not tracking — throws it away. Worse, the move is invisible in the moment and only noticed later as "where did that go?"

## Failure 3: thresholds drift apart and nobody notices

Two constants that must stay in a fixed relationship is a drift trap. Ours were literally the same constant used by both surfaces, which is the *most* coupled version and still wrong. Split them into two constants and now a change to one silently opens a gap (items in neither surface) or an overlap (items in both). Neither fails loudly.

## The fix: divide by evidence, not by elapsed time

Ask what you actually **know** about each item and what question that lets you answer. Our three surfaces came out as:

| Evidence you have | The question it answers | Surface |
|---|---|---|
| The user explicitly asked | "what did I promise myself?" | reminders |
| The user has written about it | "what did I abandon mid-thread?" | the forgotten row |
| Nothing written, activity only | "what should I start?" | recommendations |

These do not overlap, and an item cannot drift from one to another with the passage of time — only a *user action* moves it (writing about something, or asking to be reminded). That's the property you want: **transitions between surfaces should be caused, not scheduled.**

Note what happened to time in that model. It didn't disappear — the forgotten row still has a 14-day floor. But it's now a knob *inside* one surface controlling how much that surface shows, not a wall between two surfaces. Tuning it changes a volume, not a taxonomy.

## Make the disjointness structural, not incidental

Once you have the split, enforce it in the query rather than trusting the predicates to stay non-overlapping:

```sql
-- the guessed feed excludes anything the user explicitly asked for
AND NOT (<the exact predicate the explicit surface uses>)
```

Import that predicate; don't restate it. If the two definitions ever drift, items appear in both surfaces or vanish from both — the exact bug you just removed, returning through the back door. One exported function, two call sites:

```ts
export function activeRequestWhere(alias?: string): string {
  const p = alias ? `${alias}.` : '';
  return `${p}requested_at IS NOT NULL AND (${p}last_seen IS NULL OR ${p}last_seen <= ${p}requested_at)`;
}
```

There's a UX dividend too: because the surfaces are disjoint by construction, taking the explicit action **visibly moves the item** from the guessed surface to the asked-for one. The mechanism becomes legible instead of mysterious.

## The test to apply before adding a surface

Before splitting anything into two lists, ask:

1. **Can one item satisfy both predicates at once?** If yes, you have one list, not two.
2. **Can an item move between them with no user action?** If yes, you're spending location on a value the user isn't tracking.
3. **What does each surface know that the other structurally cannot?** If you can't answer without saying "it's newer," they're the same surface.

Question 3 is the useful one. If a proposed surface has no evidence of its own — only a different number — it's a filter, a sort order, or a "show more," not a place.

## Related

- [derive-dont-track-ui-flags.md](./derive-dont-track-ui-flags.md) — same instinct one level down: prefer a property you can compute over a state you have to keep in sync.
- [n-copies-of-truth-drift-guard.md](./n-copies-of-truth-drift-guard.md) — why the shared predicate gets imported rather than restated.
