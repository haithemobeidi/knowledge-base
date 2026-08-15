---
stack: [dom, react, ui, web]
kind: gotcha
last_verified: 2026-08-15
---

# A layout shift between mousedown and mouseup silently eats the click

**One-liner:** The DOM fires `click` on the **nearest common ancestor** of the mousedown target and the mouseup target — so a button that moves between press and release never receives its click, no handler fires, no error appears, and the symptom reads as "I had to click it twice," which is exactly the shape people write off as user error because the second press always works.

## The mechanism

`click` is synthesized from a press-release pair. If the element under the cursor at release is not the element that was pressed, the event resolves to their closest shared ancestor — typically a container with no handler. Nothing throws. Nothing logs. The button's `onClick` simply doesn't run.

Any layout change during the ~100ms a human press lasts can cause it: content above the button unmounting or changing height, an image loading, a list row arriving, an animation reflowing.

## The trap that MANUFACTURES it: blur-committed forms

Forms that save a field on blur create this deterministically:

1. The user presses "Done" (or any button).
2. The press blurs the active field → **the blur handler is the save**.
3. The save changes state that renders ABOVE the button (in the observed case: the saved edit cleared an AI summary line, which unmounted and slid every control up by its height).
4. Release lands on whatever now occupies the button's old position → click resolves to the common ancestor → discarded.

Properties that make it evil to diagnose: it reproduces **only when the vanishing content existed** (entries without a summary behaved perfectly), and **never on the second press** (the layout already shifted), so every retry "proves" it works.

## The fix

**Geometry must not move while any pointer could be down on a control.** Don't debounce the click or move the save — freeze the layout:

- Hold the vanishing/changing content at its pre-interaction value for the duration of the mode that has live buttons (e.g. freeze a summary line at its pre-edit text while edit mode is open; re-sync on exit). The same freeze covers the reverse case — new content arriving mid-press.
- Fold the mode's enter/exit into one setter so the freeze and its release can't drift apart.
- Residual shifts are fine **below** the lowest interactive element, or when nothing clickable sits in the moved region — the rule is about what's above/under live controls, not about never reflowing.

## How to recognize it from a bug report

"I had to click twice," "the button ignored me once," "maybe I missed it lol" — combined with any state that saves on blur or any content that loads/clears near the button. Before blaming focus handling or event propagation, ask: *what changed height above that button between press and release?*

## Related

- [[exit-animation-props-captured-at-unmount]] — sibling family: UI correctness bugs born at the mount/unmount seam.
- [[single-select-that-commits-cant-be-a-radio-group]] — sibling family: interaction semantics that betray the user at commit time.
