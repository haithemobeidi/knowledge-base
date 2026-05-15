# Work Style — read on demand, not auto-loaded

These are the long-form work-style rules for the project. They were extracted from `CLAUDE.md` so the auto-loaded context stays lean.

**When to read this file:**

- **Before starting a new sub-phase** → read the "pause at natural test milestones" section so you declare pause-points correctly.
- **Before designing a new screen or layout change** → read the "mock before you build" section (UI projects only).
- **Before designing any non-trivial component** → read "don't reinvent the wheel" — the search-first checklist.
- **Any time you push back on or agree with a user's idea** → read "grounded pushback + grounded agreement".
- **Before changing a read/write path or coordinating multiple surfaces** → read "one source of truth — data AND behavior".
- **Always, but especially before suggesting "let's ship and iterate"** → read "methodical pacing — V1 perfect > V1 fast".
- **Before starting an audit / cleanup pass** → read "audits target real optimization".

`CLAUDE.md` references this file by name in each relevant rule; you do not need to read it on every session.

---

## Mock before you build — design sandbox for all UI/UX changes

> Skip this section entirely if the project is not UI-heavy.

**Any new screen, layout change, or visual feature must be mocked in the HTML prototype before code lands.** A living prototype directory (suggested: `docs/design/prototype/`, one HTML file per screen with a shared CSS/JS layer) is the design sandbox — iterate there, get user sign-off on the visual, then implement in the real frontend.

How to apply:

1. **Before coding a new screen or major layout change**, update the prototype to show the proposed design. No build step — double-click to open in a browser.
2. **Show the user.** They approve the direction in the prototype, not in a 15-file diff.
3. **Then implement.** The prototype is the visual spec; the real code is the real thing. Once implemented, the prototype's version is a historical reference, not a living spec.
4. **Keep the prototype in sync** with the current app state. When features ship, update the prototype so it stays useful as a starting point for the next iteration.
5. **Rules of engagement** (bake into the prototype folder's own README): no frameworks/bundler/build step, duplicate markup across screens rather than abstracting, keep each CSS file under ~500 lines.

---

## Don't reinvent the wheel

**For ANY non-trivial problem** — file-format parsing, API client patterns, weird OS-specific lookups, content discovery, layout tricks, sync algorithms, etc. — pause and search for existing open-source projects before designing from scratch.

How to apply:

1. **Check first.** When you hit a problem that "must have been solved before," search GitHub topics / READMEs / source for prior art.
2. **Use the user's known reference repos.** <TODO: list your own reference project paths here, e.g. `~/Documents/Vibe Projects/<name>`. Same author, same domain often = the same patterns we want to mirror.>
3. **Improve, don't blind-copy.** Old projects may use outdated approaches. Note when an OSS solution uses an old API/layout/dep and propose the modern equivalent.
4. **Cite the source.** When you adopt a pattern from an OSS project, mention it in a comment or in `CODEBASE_INDEX.md`. Helps future-Claude understand why the code is shaped this way.
5. **Don't be paralyzed.** If 10 minutes of searching turns up nothing relevant, build from scratch. The rule is "look first," not "search exhaustively before any code lands."

---

## Pause at natural test milestones

UI/UX-sensitive projects need live testing — screens need to be pressed, animations watched, real data flowed through. Claude must not build an entire sub-phase in one shot and hand back a 15-file diff for blind review.

**The rule:** while implementing a phase or sub-phase, proactively pause at natural testable milestones and hand control back to the user for a live test before continuing. A milestone is any point where something observable becomes reachable — typically "first time the feature renders," "first end-to-end happy path," "first error path surfaced in UI." Milestones are organic, not arbitrary file-count checkpoints.

### Mandatory steps

1. **Declare pause-points BEFORE writing any code for a sub-phase.** First message of the sub-phase must contain a numbered list under a heading like `**Pause-points for this milestone:**`. Each entry is a one-line "click moment" — e.g., `Pause A: form renders, can submit a name-only manual entry and see it in the grid`. Default to **2–4 pause-points** per sub-phase. Zero pause-points is a red flag; if you can't think of any, the work is probably either invisible or not decomposed enough.

2. **Pause-point triggers — when in doubt, these always count.** If during execution any of these become reachable, **STOP** even if you didn't pre-declare it as a pause-point:
   - A new IPC command lands and is callable end-to-end
   - A new form first renders with at least one functional field
   - A new database migration runs successfully against the live DB
   - A new screen / route becomes reachable in the running app
   - The first end-to-end happy path through a feature works
   - The first user-visible error state surfaces correctly

3. **STOP-and-handoff after each pause-point.** When the code for a declared pause-point lands, **stop writing code immediately** — even if the next pause-point feels like only 10 more lines. Post a hand-off block with this exact shape:

   ```
   ## 🛑 Pause N — <pause-point name>

   **What's new since last pause:** <bullet list>
   **What to test:** <bullet list of clickable / observable things>
   **What I haven't built yet:** <bullet list of what's intentionally missing until the next pause>
   ```

   Then wait for the user. Do NOT continue coding the next pause-point until they've either reported back or explicitly told you to keep going.

4. **File-count safety net.** If you've written **4+ new files OR 300+ lines** of code in a single continuous burst without hitting a declared pause-point, you missed one. Stop, re-read your own pause-point list, and find the slice you should have stopped at.

5. **Use the pause for live feedback.** If the user reports something feels wrong (layout, copy, interaction, missing affordance), fix it immediately before moving on — course-correcting mid-phase is cheaper than mid-project.

6. **Skip the rule only for invisible work.** Pure refactors, docs, dep bumps, CI wiring, formatting passes, and protocol-bookkeeping commits have nothing the user can click — don't fake a milestone for them. **Prototype/mock iteration also skips this rule** — HTML mocks run straight through; pause once at the end of the mock track for user sign-off, not between revisions.

7. **Pause names use plain letters (A, B, C, ...), not Greek.** Keep the sequence continuous across mock/impl blocks of the same milestone (e.g. mocks land at A–C, React impl picks up at D–F). Greek letters confuse the user when re-referencing across sessions.

### What counts as a sub-phase

A sub-phase is any unit of work small enough to fit in one `/end` commit but large enough to need decomposition. In practice:
- Each numbered milestone in `ROADMAP.md`
- Any user-requested feature that touches more than ~2 files or ~100 lines
- Any bug fix that requires schema or IPC changes
- Refactors that span more than one feature folder

If the work is smaller than that — a one-line fix, a typo, a single dep bump — the pause-point rule doesn't apply. Just do it.

---

## Grounded pushback + grounded agreement

Disagreement and agreement both require evidence. Treat them as the same bar, not different bars.

**When you push back on a user's idea**, cite real evidence:
- Code already in the repo that handles it
- Comparable apps that solved the same problem differently (and link them)
- Prior decisions in `DECISIONS.md` that explain why we went a certain way
- OSS prior art for the pattern
- A specific failure mode the proposed approach exposes

"That might cause issues" without specifics is not grounded — it's hedging.

**When you agree with a user's idea**, cite the same kind of evidence:
- The existing code shape supports it cleanly
- A comparable app does exactly this and it works
- It matches a prior decision

"That sounds good" without specifics is sycophancy — equally useless.

**Subjective calls** (visual preference, naming, scope tradeoffs) should be flagged as such: *"This is subjective — I'd lean X because Y, but it's your call."* The flag is what makes it honest. Pretending a subjective call is objective is the same failure mode in disguise.

**The trap to avoid:** performative devil's-advocate. "I should push back on this so I seem thoughtful" is just as bad as sycophancy. Disagreement-for-the-sake-of-disagreement burns the user's time. The bar is the same in both directions — real evidence or flag it as subjective.

---

## One source of truth — data AND behavior, across all surfaces

Every concept in the project has TWO authoritative locations: a data location (where the value is stored / read from) and a behavior spec (what the UI does with it). Both must be singular.

**The trap:** the data layer gets one source of truth (good) but the same concept gets re-implemented across overlay, settings panel, quit ritual, etc. with subtly different behavior. Saving from the main form respects validation; saving from the quit ritual skips it. Pre-fill on the overlay reads field A; pre-fill on the main form reads fields A and B. Each surface looks reasonable in isolation; the inconsistency only shows up when a user moves between them and breaks something.

**How to apply when touching a read/write/pre-fill path:**

1. **List every surface that touches this concept.** Overlay, main form, quit ritual, debug screen, settings panel — wherever the user interacts with this value.
2. **Audit each for parity.** Does the validation match? The pre-fill logic? The save semantics? The error handling? The undo behavior?
3. **Pick the canonical behavior.** Usually the most-used surface defines the spec.
4. **Bring every other surface in line with that spec**, or document the deviation in `DECISIONS.md` with a reason.
5. **If the data shape changes (schema migration, new field)**, sweep all surfaces in the same commit. Drift is cheaper to prevent than to fix once it ships.

**What this is NOT:** "extract every duplicated function into a shared helper." DRY-by-3 still applies. This is about *behavioral* consistency across surfaces that necessarily have their own UI code — not about eliminating code duplication.

---

## Methodical pacing — V1 perfect > V1 fast

Long-horizon projects (months, not weeks) reward methodical pacing. Rushing a sub-phase costs more than the time it saved, because half-baked surfaces accumulate technical debt and "ship now, iterate later" rarely circles back.

**How to apply:**

- **Default to MORE pause-points, not fewer.** When in doubt about whether something deserves a pause, add one. The cost of an unnecessary pause is a one-line user reply; the cost of a missing pause is a 15-file blind-review handoff.
- **No "ship now, iterate later" defaults.** Every pause-point must leave its surface complete — fully functional, no obvious gaps, no "we'll fix the empty state next time." If a surface isn't complete at a pause, you haven't reached the pause yet.
- **Resist the urge to batch work** to feel more productive. Three separate pauses that each ship cleanly are better than one fast pause that ships three half-finished features.
- **Pace cues from the user matter more than progress velocity.** If the user explicitly says "we have time, let's do this properly," that's the signal to add more checkpoints, not the signal to keep moving.
- **The bar for "done" is the user's expectations**, not the code's working state. Code that compiles and renders is not "done" if the UX feels half-built.

**What this is NOT:** an excuse to gold-plate or over-engineer. Methodical pacing is about quality at each pause-point, not adding hypothetical scope.

---

## Audits target real optimization

Audit passes (file size cleanup, DRY violations, dead code, dependency drift, security review) are valuable when they target measurable wins. They're wasteful when they're change-for-change's-sake.

**Before starting an audit pass**, name the win:
- "Split this 850-line file because X has been added since the last split and a new section makes it worse" — real win.
- "Three identical 30-line blocks across these files; extracting them removes a known drift hazard" — real win.
- "This dep has a CVE patched in N+1" — real win.
- "This could be faster" — not a win. Faster how? By how much? Measured against what?
- "This pattern is old; the modern version is X" — not a win on its own. Does X measurably reduce LOC, surface fewer bugs, or improve type safety?

**Audit anti-patterns to avoid:**

- **Reshuffling without a measurable improvement.** Moving code around because the new shape "feels cleaner" but no one can name what got better.
- **Eliminating duplication that isn't drift-prone.** Two instances of similar-looking code that haven't drifted in a year don't need extraction.
- **Adding abstractions for hypothetical future reuse.** If only 1 caller exists, the abstraction is wrong shape until a 2nd caller validates it.
- **Sweeping all 800-line files at once.** Pick the worst offender; ship that; gather feedback before sweeping the next.

**Audit scope:** by default, audits cover production code only (`apps/`, `packages/` or equivalent). They EXCLUDE prototypes/mocks (`docs/design/prototype/` etc.) unless the user explicitly points at them. Prototype code is throwaway iteration; auditing it wastes effort.
