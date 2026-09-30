---
stack: [css, animation, process, any]
kind: pattern
last_verified: 2026-09-30
---

# A motion mock harness: speed multiplier, replay, reduced-motion preview and variant toggles in plain HTML

**One-liner:** a person judging motion needs to slow it down, run it again and compare variants without reloading, and the builder can't watch it at all (an AI sees frames, not movement). So every motion mock ships the same small harness: one `--spd` custom property multiplies every duration and delay, Replay restarts CSS intros with a class removal and a forced reflow, a "Reduced" toggle previews the `prefers-reduced-motion` state, and body classes switch variants live.

*Status: the harness behind Playmoir's landing mock (2026-09-30), three directions × three logo motions, reviewed by the user ("those are good"). It generalizes the per-project motion-mock recipe in Playmoir's `docs/design/prototype/README.md`.*

## The pieces

**1. One speed variable, used everywhere.** Write every duration *and* delay through it, or slow-motion desyncs the choreography.
```css
:root { --spd: 1; }   /* toggle sets 1, 2 or 4 */
.play .word { animation: rise calc(800ms * var(--spd)) var(--ease) calc((500ms + var(--i) * 90ms) * var(--spd)) both; }
```
JS-timed pieces (typewriters, staggered class adds) read it too: `setTimeout(step, 26 * spd())`.

**2. Replay without reload.** Intros hang off a `.play` class on the page root. Remove it, force a reflow, add it back:
```js
root.classList.remove('play'); void document.body.offsetWidth; root.classList.add('play');
```
Scroll reveals (`IntersectionObserver` adding `.in` once) need the class stripped and the elements observed again. Scroll to top first.

**3. Variants as body classes.** One class per toggle group (`d-a / d-b / d-c`, `logo-resume / logo-recall`, `type-new / type-today`), and CSS scoped under them. Groups combine freely, so "direction B with logo motion 2" needs no extra mock.

**4. A reduced-motion preview.** A `.rm` class that collapses animation and transition durations and delays to 1ms shows exactly what a `prefers-reduced-motion` visitor gets, meaning every element in its final state. It also catches elements that only become visible *through* an animation and would stay hidden.

**5. A notes panel** per variant: its strength, its risk, and anything it changes beyond motion (type, layout). The reviewer reads the reasoning next to the thing it explains.

## Gotchas

- **Typed text flashes full before typing.** Hide it until its turn (`.box:not(.in) .txt { opacity: 0 }`), or the finished string shows for a frame before it's cleared.
- **A typewriter must keep inline markup.** Slice the HTML by visible characters, keep tags whole and close any open ones, so highlighted words (`<em>`) stay highlighted while typing. Count an entity (`&quot;`) as one character.
- **Measure hidden variants when shown.** Anything sized from layout (sideways-scroll travel) reads 0 while its variant is `display: none`; re-measure on every toggle.
- **Syntax-check, then hand over.** `node --check` on the script and a check that every image path exists are the builder's gates; the look is the reviewer's.

## Related

- `claude-project-template/global/WORK_STYLE_DETAIL.md` → "Mock first" (the policy: A/B toggles, real assets).
- `animation-keyed-to-creation-not-content.md`: what a mock can't show (cold-path async in the real app).
- `scroll-progress-as-a-css-variable.md`, `cursor-torch-reveal.md`, `crop-a-screenshot-region-in-css.md`: the techniques this harness was first used to judge.
