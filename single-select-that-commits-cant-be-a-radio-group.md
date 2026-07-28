---
stack: [frontend, html, accessibility, react, forms]
kind: gotcha
last_verified: 2026-07-28
---

# A single-select that commits on choice cannot be a radio group

**One-liner:** a native radio group *selects as the arrow keys travel through it*, and that selection dispatches **both `change` and `click`** — so if your control does anything irreversible on selection (writes to a DB, closes a popover, submits), the first arrow press fires it on a value the user was only passing over. No event on a radio can tell "chose this" from "travelled through this". Use buttons with `aria-pressed`, or the ARIA manual-activation pattern.

## The failure shape

You build a small "pick one of five" control — durations, sort orders, filter presets. It lives in a popover, and picking an option should commit and dismiss, because leaving the panel open after a one-click answer makes the user close something they already answered.

Radios are the semantically correct control for one-of-N, so you reach for them: real `<input type="radio">` under styled labels, because a hand-rolled `role="radio"` div owes the user arrow-key traversal and focus management, and hand-rolled versions of that are how a codebase ends up with a fifth half-correct widget. Good instinct. Wrong control.

The bug the user reports is confusing, which is what makes this worth writing down:

> "tab works, arrows don't"

or

> "if i click the reminder, click tab (selects a chip) then the arrow key it goes to the next one and closes immediately"

The arrow keys are working perfectly. They move to the next option, select it, your `onChange` fires, you commit and dismiss — and the panel vanishes before the user sees anything move. It reads as "the arrow key is broken" when it is in fact "the arrow key did the whole job instantly, on the wrong value."

## Why this happens

Two separate facts combine badly:

1. **A radio group uses *automatic activation*.** Tab enters the group and lands on the checked radio (one tab stop for the whole group, which is correct). Arrow keys then move focus **and change the selection** at the same time. There is no "browse without selecting" state. Compare **manual activation**, where arrows move a focus ring and Enter/Space commits — that is the mental model most people describe when they say "it's just a selector, Enter should confirm", and radios do not offer it.

2. **Arrow-key selection runs the element's activation behaviour, which dispatches a `click` event.** This is the part that ambushes you. `click` is not a pointer-only event on form controls.

So both of the obvious discriminators fail:

```jsx
// FAILS: change fires for every option you arrow past.
<input type="radio" onChange={() => commitAndClose(value)} />

// ALSO FAILS: click fires on arrow traversal too.
<input type="radio"
       onChange={() => stage(value)}
       onClick={() => commitAndClose(value)} />
```

**Measured, not assumed:** the second form was actually built and tested, and the arrow key still closed the panel on the first press.

### The fix that looks clever and isn't worth it

`MouseEvent.detail` is 0 for keyboard-generated clicks and ≥1 for real pointer clicks, so `onClick={e => { if (e.detail > 0) commit() }}` looks like the answer.

**Not measured — reasoned, and rejected before building**, for three reasons worth knowing:

- Clicking a `<label>` dispatches a *second*, synthesized click at the labeled control, and its `detail` is not reliably 1 across browsers. Your commit either double-fires or doesn't fire.
- `Space` on a focused radio also produces a `detail: 0` click. If you filter those out you have just broken the keyboard path you were trying to protect, and now you need an `onKeyDown` for Enter and Space anyway.
- You end up with three handlers coordinating through event archaeology to reconstruct a fact the platform could have told you plainly. The next person to touch it will not know why, and there is a good chance they "simplify" it back into the bug.

## The fix

**Use buttons.** They have no traversal semantics to fight: Tab moves, Enter/Space activates, activation is the only signal, and there is exactly one event to handle.

```jsx
<div role="group" aria-label="Remind me in">
  {PRESETS.map(p => (
    <button
      key={p.days}
      type="button"
      aria-pressed={value === p.days}      // carries what `checked` used to
      onClick={() => commitAndClose(p.days)}
      className={/* focus-visible:ring-2 — you own the focus ring now */}
    >
      {p.label}
    </button>
  ))}
</div>
```

What you trade:

| | radio group | buttons + `aria-pressed` |
|---|---|---|
| Tab stops | 1 for the whole group | 1 per option |
| Arrow keys | move **and select** | nothing |
| Can browse without selecting | no | n/a — nothing selects until you activate |
| Distinguishes chose-vs-passed-over | **no** | yes, trivially |
| Screen reader announces | "radio group, 2 of 5" | pressed/not pressed per button |

Five tab stops for a five-item chip row inside a popover is what most people expect anyway — it is what the user in this case had assumed was happening before any of this came up.

If you genuinely need one tab stop (a long list, or a control that must not eat the tab order), use the ARIA **manual activation** pattern instead: `role="radiogroup"` + roving `tabindex`, arrows move focus *only*, Enter/Space selects. That is more code and you owe the user correct focus management — but it is the honest construct for "browse, then confirm", and it is what you were reaching for when you picked radios.

## When a radio group is still right

Radios remain correct — and preferable — when **selection is not a commit**:

- Inside a form that commits on Save. Nothing happens when the value changes, so automatic activation costs nothing. (In the case this came from, the same picker sits in a form *and* in a commit-on-click popover; the form half would have been perfectly happy as radios.)
- Any filter/toggle where changing the value is instantly reversible and has no side effect beyond re-rendering.

The rule is not "radios are bad". It is: **automatic activation is fine when activation is cheap.** The moment selection writes, navigates, closes, or otherwise costs something, arrow traversal is firing that cost on values the user never chose.

## Checklist

Before using a radio group, ask:

- [ ] Does anything happen the instant the value changes — a write, a network call, a dismiss, a navigation?
- [ ] If yes: can the user reach option 5 without options 2, 3 and 4 doing that thing on the way? **With radios, no.**
- [ ] Am I about to write `onClick` on a radio to detect "a real choice"? It fires on arrow keys. Stop.
- [ ] Am I about to inspect `event.detail`? You are reconstructing intent from event trivia. Change the control.
- [ ] If I switch to buttons: have I added `aria-pressed`, a `role="group"` with a label, and my own `focus-visible` ring? (Buttons don't group themselves, and a visually-hidden input's focus state is not free either way.)

## Related

- [[derive-dont-track-ui-flags]] — same family: the fix is changing the shape so the bug cannot exist, not adding another guard to the shape that has it.
