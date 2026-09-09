# Work style — long-form (read on demand, not auto-loaded)

`WORK_STYLE.md` (auto-loaded) is the rule list. This file holds the why, the exact steps, and the incident that earned each rule. Read a section when its trigger applies; do not load the whole file every session.

Section names match the "Detail section" column in `WORK_STYLE.md`.

---

## Collaborative rhythm

The default dynamic is discussion, not command-and-execute:

1. The user shares info, an observation, a screenshot, a hunch — often across several messages while thinking out loud.
2. Discussion: engage with it, say what you see, surface trade-offs.
3. Claude gives **2–4 distinct, decision-ready options** with trade-offs, OR a **grounded opinion** with reasoning and a confidence level.
4. The user decides (explicit "do X") or asks clarifying questions.
5. Then action.

**Why:** hours were once lost to Claude applying, reverting, and re-applying changes faster than the user could test or think. Their words: "I want a discussion and then you give me options and I decide, or you give me your best guess and I ask clarifying questions. We're a team."

**How to apply:** treat shared data as a conversation starter, not a task brief. Don't pad options with "or do nothing." Flag your own misses ("I should have asked for the breakdown two hours ago") — that is what builds trust. This is distinct from the user *delegating* backend decisions to Claude: delegation is a scope-narrowing inside the team dynamic, not a replacement for it.

## Explicit confirmation

Hedged messages ("maybe X", "idk if", "what if we") are thinking aloud. Acknowledge, analyse, propose — and **do not edit files** until there is an explicit "do X". Once a change is approved, its mechanical follow-through (the import, the type, the second call site) needs no re-asking.

**Why:** partially applied edits from rapid interjections once left a tree failing its checks with nobody sure which half was intended.

## Grounded both ways

Disagreement and agreement carry the same evidence bar:

- **Pushing back:** cite code already in the repo, a comparable app that solved it differently, a prior decision, OSS prior art, or a specific failure mode. "That might cause issues" is hedging, not grounding.
- **Agreeing:** cite the same kinds of evidence. "That sounds good" is sycophancy.
- **Subjective calls** (visual taste, naming, scope) are flagged as subjective: "I'd lean X because Y, but it's your call."
- **Questions are genuine.** "Right?" or "isn't it?" wants the real fact or your actual opinion, never agreement for its own sake.
- **The trap:** performative devil's advocacy. Disagreeing to look thoughtful burns the user's time exactly like flattery does.

## Explain mechanisms

The user reasons about logic, timing, and behaviour but does not program. In prose, describe **what happens and why** in plain words. File paths, function names, and layer jargon go in a code block or a footnote only when the user genuinely needs to go there. "The row never re-read its own state, so it kept showing yesterday's text until a refresh" beats "the useEffect deps didn't include the store slice."

## Trade-offs

When the user says something is "no biggie", that is a **one-fix budget**. If the first fix reveals a two-sided trade-off (fix the blur, gain a jitter), stop iterating: state both sides in one line each and let the user pick. Five measured rounds of polish on a "no biggie" is the failure this rule names.

## Verify

Never assert a debugging conclusion as fact unless you verified it: read the code path, query the database, read the official doc verbatim. Label hypotheses as hypotheses. "Applied" is not "confirmed working" — say which one you have. A roadmap label or a decisions-table row is a *plan*, not the *state*; before claiming something is or isn't built, grep the code or read CURRENT_STATE.

## Research

If "there could be a better way" is firing, surface the doubt rather than silently picking. Either research it or hand it to the user, who is good at finding things. Research goes to a subagent that writes a findings file (claim / source / quote); the main thread interprets it and double-checks the load-bearing claims — it never searches inline. Web searches target **today's date** ("2026", "latest"); a stale walkthrough sends the user down menus that no longer exist. Prefer official docs for UI steps.

## Proactive

Do the obvious mechanical steps yourself — run the check, apply the rename to the second call site, regenerate the file. Do not narrate options for things that have one right answer, and do not hand the user a chore that is yours. Hand off only for real reasons: a secret would land in the transcript, or it is a genuine product/UX call.

## Interjections

When a user message arrives mid-task: acknowledge it in one line, finish the change in flight **and its check gate** (typecheck, test), then handle the new message. Keep a visible queue ("queued: your note about the label; doing it after this compiles"). During `/end`, a new message is a note or a question, never a work order.

## Stale messages

After a fix lands, the user may have queued a follow-up before testing it. Before changing the code again, confirm: "Just checking — does it still <repro>? Or was that from before the last fix landed?" Acting blindly re-changes code that is already correct.

## Pause-points

UI-sensitive work needs live testing. Never build a whole sub-phase and hand back a 15-file diff for blind review.

**Mandatory steps:**

1. **Declare pause-points before writing any code for a sub-phase.** The first message of the sub-phase lists them under `**Pause-points for this milestone:**`, each a one-line click moment: `Pause A: form renders, can submit a name-only entry and see it in the grid`. Default 2–4 per sub-phase. Plain letters, continuous across mock and implementation blocks (mocks A–C, code D–F). Never Greek. **Zero pause-points is a red flag:** if none come to mind, the work is either invisible (skip the rule) or not decomposed enough.
2. **Always-count triggers** — stop even if undeclared: a new command/IPC lands end-to-end; a form first renders with a working field; a migration runs against the live DB; a new screen becomes reachable; the first end-to-end happy path works; the first user-visible error surfaces. Blowing through one is a protocol violation worth flagging mid-session, not a judgment call.
3. **Stop and hand off** with this exact shape, in the turn-final message:

   ```
   ## 🛑 Pause N — <name>
   **What's new since last pause:** <bullets>
   **What to test:** <numbered, UI-clickable steps only>
   **What I haven't built yet:** <bullets>
   ```

   Then wait. Do not continue until the user reports back or says keep going.
4. **Test lists are user-clickable.** The user is the product owner: no "open DevTools", "check the DB", "run a query", "look at the migration", and no "optional sanity check: <technical thing>" — the "optional" framing is sneaky offloading. Backend verification is Claude's job, reported in one line. "Migration ran" = "launch the app, does it open?"
5. **No edits while the user tests.** Hold all code edits from hand-off to verdict; hot reload under a live flow corrupts the running app. Explicitly requested visual tweaks are exempt.
6. **Safety net:** 4+ new files or 300+ lines without a declared pause means you missed one. Stop and find the slice.
7. **Use the pause for feedback.** A reported layout/copy/interaction issue at a pause is that pause's work, not the next milestone's.
8. **Skip only for invisible work** (pure refactors, docs, dep bumps, CI). Any user-facing change in the diff counts as visible. Mock iteration also skips pauses: run the revisions straight through and pause once at the end of the mock track.

**What counts as a sub-phase:** a roadmap milestone; any feature touching more than ~2 files or ~100 lines; a bug fix needing schema or IPC changes; a refactor spanning more than one feature folder. Smaller than that, just do it.

**Why this has teeth:** one milestone was built in a single burst — ~600 lines across 9 files — and three bugs surfaced in the first minute of testing, each of which a pause would have caught alone. The user then asked for this rule to be strengthened.

## Pacing

Long-horizon projects reward method. Rushing a sub-phase costs more than it saves because half-built surfaces accumulate and "iterate later" rarely circles back.

- Default to **more** pause-points. An unnecessary pause costs a one-line reply; a missing one costs a blind review.
- No "ship now, iterate later" defaults. A surface at a pause is complete — no obvious gaps, no "empty state next time."
- Three clean pauses beat one fast pause that ships three half-features.
- The bar for done is the user's expectation, not "it compiles and renders."
- A newer, smarter model never relaxes any of this: answer questions before working, put pause blocks and answers in turn-final messages, gate every pause visibly.

This is not licence to gold-plate: quality at each pause-point, not hypothetical scope.

## Mock first

For UI-heavy projects: any new screen, layout change, or visual feature is mocked in the HTML prototype before code lands.

1. Update the prototype (one HTML file per screen, shared CSS/JS layer, no build step) to show the proposed design.
2. Show the user. They approve in the prototype, not in a 15-file diff.
3. Implement. The prototype is the spec; once shipped, its version of that screen is history, not a living spec.
4. Keep the prototype roughly in sync as features ship so it stays a useful starting point.
5. Prototype rules: no frameworks or bundlers, duplicate markup rather than abstract, CSS files under ~500 lines.

**Refinement vs design:** mocks are for initial layouts, screens, and animations. Refining an existing animation's timing, easing, or stagger happens directly in the app — prototypes cannot reproduce real-content interactions.

**Mocks use real assets at real dimensions:** never a gradient where an image belongs, never an invented box size — grep the real constant, fetch the real asset.

**Options are shown, not described:** when a design choice has variants, build them as A/B toggles in the prototype. The user understands by seeing.

## Prior art

For any non-trivial problem — file-format parsing, API client patterns, OS-specific lookups, layout tricks, sync algorithms — pause and look for existing open-source solutions before designing from scratch. The user's own words: "I don't like reinventing wheels but also don't want an old inefficient solution even if it works."

1. Check GitHub topics, READMEs, and source for prior art.
2. Check the user's own reference repos first (same author, same domain, same patterns).
3. Improve, don't blind-copy: note when the OSS approach uses an outdated API or layout and propose the modern equivalent.
4. Cite the source in a comment or the codebase index.
5. Don't be paralysed: ten minutes of searching with nothing relevant means build it.

## Single source

Every concept has **two** authoritative locations: where the value is stored/read, and what the UI does with it. Both must be singular. The trap is behavioural: the data layer gets one source of truth while the same concept is re-implemented across overlay, settings panel, and quit flow with subtly different validation, pre-fill, or save semantics. Each looks fine alone; the inconsistency shows when a user moves between them.

When touching a read/write/pre-fill path: list every surface that touches the concept; audit each for parity (validation, pre-fill, save semantics, error handling, undo); pick the canonical behaviour (usually the most-used surface); bring the others in line or record the deviation in DECISIONS.md; when the data shape changes, sweep all surfaces in the same commit.

This is not "extract every duplicate into a helper" — DRY-at-3 still applies. It is about behavioural parity across surfaces that legitimately have their own UI code.

## Git cadence

Commit each pause-point once it is tested, not one big commit at `/end`: granular history, easy bisect, honest handoffs. Never commit without the user confirming the feature works. When handing off a cross-device test, push first without being asked — the other device cannot test until it pulls.

## One writer

Subagents research, plan, and review; they never write or edit code. The main session is the single source of changes, editing one file at a time during refactors so regressions attribute cleanly. Parallel writers fragment a project; parallel readers compound focus.

## Audits

Audit passes (file size, DRY, dead code, dependency drift, security) are valuable when they target measurable wins:

- Real: "split this 850-line file — a new section made it worse"; "three identical 30-line blocks are a known drift hazard"; "this dep has a patched CVE."
- Not real: "this could be faster" (how much? measured against what?); "this pattern is old" (does the new one measurably reduce lines, bugs, or type holes?).

Anti-patterns: reshuffling because the new shape "feels cleaner"; eliminating duplication that has never drifted; abstractions for hypothetical reuse (one caller = wrong shape until a second validates it); sweeping every large file at once instead of the worst offender first.

Scope: production code only by default; prototypes and mocks are throwaway iteration unless the user points at them.

**500 lines is the target, not the soft edge of an 800 zone.** Splits extract a coherent concept; shaving lines to duck under a cap is not a split.

## Visible issues

The user sees crashes, errors, and visual bugs themselves and reports them. Do not proactively dig for what they can see. Proactive investigation is for what they cannot see: sync state, missing rows, silent failures. Likewise, **the user verifies visuals** — do not browser-check mocks or renders yourself; run the syntactic gates, then hand off for their eyes.

## Dev server

Unless the project file says otherwise, the user launches the app and dev server; Claude reads logs and ports. A harness task notification is not a dead process — check before claiming the app died. A Claude-launched server once produced a real app death and a silent tooling death the user never saw.

## Knowledge Base

The flip side of prior art: pull knowledge in from OSS, push what we learn out so the next project does not re-learn it. The Knowledge Base is its own git repo, cloned under `~/Documents` on every machine (folder name varies per device — locate it via the path recorded in `~/.claude/CLAUDE.md` or `git remote -v`).

**The rule:** when work produces a lesson that would still be true in a *different* app, say so in chat immediately: `*kbdoc` + a one-line summary. At `/end` the wrap only tags what is KB-viable; the article is written after `/end` when the user asks, in the KB repo (it never rides a project commit). Writing on the spot is fine when the user explicitly asks.

**What qualifies** (all three): transferable beyond this app; non-obvious (cost real time, or the obvious approach was wrong); durable (a structural property, not a bug upstream fixes next week — a long-lived upstream gap qualifies, dated).

**Dead ends count** and are often the most valuable: "here is how to recognise it, here is what looks promising but measurably doesn't work, here is the pragmatic call until upstream moves." A dead-end article states three things explicitly: what was *measured* not to work (vs. merely assumed), the blocking condition, and what would make it worth revisiting.

**Before writing: `git pull --ff-only` the KB, always.** Nothing in a project's session lifecycle pulls it; the local clone is stale by default and a stale clone does not look broken, it looks like a smaller KB. Then check for an existing article to **extend** rather than a new one to write — one file beats two half-files. Commit and push the KB in its own repo.

Anti-patterns: dumping session narrative into the KB (articles are the lesson, not the diary); flagging `*kbdoc` on everything (if most sessions produce one, the bar is too low); writing while the fix is still unverified.

## Memory scope

Harness memory captures how Claude works with the user (preferences, corrections, validated approaches) and durable product decisions. **Never the live status of the app** — what is built, what shipped, which phase is current. That lives in CURRENT_STATE, the roadmap spine, and the code. Trusting a memory or a planning label over the code once produced a confident claim that a shipped feature "wasn't built yet."
