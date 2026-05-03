# Work Style — read on demand, not auto-loaded

These are the long-form work-style rules for the project. They were extracted from `CLAUDE.md` so the auto-loaded context stays lean.

**When to read this file:**

- **Before starting a new sub-phase** → read the "pause at natural test milestones" section so you declare pause-points correctly.
- **Before designing a new screen or layout change** → read the "mock before you build" section (UI projects only).
- **Before designing any non-trivial component** → read "don't reinvent the wheel" — the search-first checklist.

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

6. **Skip the rule only for invisible work.** Pure refactors, docs, dep bumps, CI wiring, formatting passes, and protocol-bookkeeping commits have nothing the user can click — don't fake a milestone for them.

### What counts as a sub-phase

A sub-phase is any unit of work small enough to fit in one `/end` commit but large enough to need decomposition. In practice:
- Each numbered milestone in `ROADMAP.md`
- Any user-requested feature that touches more than ~2 files or ~100 lines
- Any bug fix that requires schema or IPC changes
- Refactors that span more than one feature folder

If the work is smaller than that — a one-line fix, a typo, a single dep bump — the pause-point rule doesn't apply. Just do it.
