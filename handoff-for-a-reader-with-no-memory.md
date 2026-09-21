---
stack: [any, llm-agents, process, docs]
kind: pattern
last_verified: 2026-09-21
---

# Writing state for a reader with no memory of writing it — steal the handover protocol, don't invent one

**One-liner:** every long-horizon project eventually needs one session, shift or person to hand off to the next, and the structure that works is not obvious — it has been studied for decades in medicine and aviation, with outcome data, and the two elements everyone omits are the two that matter most: *what to do if it fails*, and *the receiver saying it back*.

## The problem this solves

A session ends. A new one starts with none of the first one's context. Whatever was not written down is gone — and crucially, **the writer cannot tell what is missing**, because everything is still obvious to them at the moment they write it. Compaction makes it worse: Claude Code's `/compact` explicitly preserves intent, files touched, errors and pending work while dropping "full tool outputs and intermediate reasoning," so a wrap written late in a long session is already summarising a summary.

The instinct is to write more. That is measurably wrong. A 2026 systematic review of nursing handovers (6 studies, 1,590 cases) found errors in roughly **88% of observed handoffs**, with **information omission the most prevalent category**, and named *"excessive non-essential information"* and lengthy duration among the leading contributing factors. Long unstructured narrative causes the loss it looks like it prevents.

## The structure that has evidence behind it

**I-PASS**, from a multicenter trial across 9 hospitals and 10,740 admissions: a **23% reduction in medical errors** (24.5 → 18.8 per 100 admissions, p<0.001) and **30% reduction in preventable adverse events** (4.7 → 3.3, p<0.001), **with no significant change in handoff duration** (Starmer et al., NEJM 2014;371:1803–1812). Structure did not cost time.

Its five elements were not brainstormed. They were chosen because pilot observers found these were the ones most often *missing* from real handoffs:

| I-PASS | What it is | Software session equivalent |
|---|---|---|
| **I**llness severity | One-word severity, first | Build/health status, before any detail |
| **P**atient summary | The case | What changed — **delta only** |
| **A**ction list | Owned items with done-conditions | The to-do ledger, cited by ID, never restated |
| **S**ituation awareness + contingency | **"If X, then Y"** | What to do when the happy path fails |
| **S**ynthesis by receiver | Read-back | The incoming party restates it |

Aviation and nuclear converge on the same shape and add one thing: an **explicit acceptance act**. FAA position-relief briefing and NRC-docketed shift-turnover procedures both require self-brief from the persisted record → a verbal brief scoped to the delta and anomalies → an explicit acceptance ("position responsibility has been assumed"; initialing the log after reading it back) → a post-handoff verification pass. Both treat completeness as **shared between outgoing and incoming**, not the writer's job alone.

## The two everyone omits

**Contingency.** Most handoffs describe the happy path and stop. The next session hits the first obstacle with nothing. One line — *"if the flight still stutters on the device, the fallback is the fixed-tempo version; if the build won't install, it's the keystore, not the code"* — is the cheapest thing in the document and the first thing wanted.

**Read-back.** This is the one with no natural analog in asynchronous software work, and it is the most protective mechanism in human handover. The written substitute: the incoming session **restates the next action in its own words and names what would make it wrong**, before starting. And if it cannot restate it from the handoff, that is a finding — *"the handoff was insufficient: it does not say X"* — recorded, not shrugged at.

Why it earns its place: a cross-check that compares documents against *each other* cannot detect staleness, because **stale documents agree with each other perfectly**. Only a reader comparing the document against reality closes that.

## Copy-forward is the dominant failure, and it is measured

The specific way written handoffs rot: the next writer opens the previous document, edits the parts they are thinking about, and everything else survives untouched and unverified. Not laziness — it is the default editing action.

Medicine has quantified this. 66–90% of clinicians copy/paste routinely; in VA charts, copied exam findings persisted a **median of 56 days** past the original note; among cases where copying had occurred, copy/paste mistakes **contributed to 35.7% of diagnostic errors** (ECRI Institute systematic review of 51 studies, 2015). Case reports include a cardiac diagnosis carried forward across 12 visits over two years, ending in the patient's death.

There is a companion finding on why nobody catches it: **diagnosis momentum, anchoring and premature closure** mean a claim written into a handoff gets *inherited and reinforced* rather than re-examined (Frye et al., Cureus 2018).

On one software project, a state document cited 146 to-do IDs and **65 were already closed** — 45% of every reference in the file, including a line saying two items "still wait for the other session" eight days after both were struck. Nobody was lying; nobody had re-read that paragraph in weeks.

**The guard:** a script that classifies every ID a state document cites against the source of truth — open / closed / not-found — and reports the closed ones for a human to read. Report, never block: "closed by X" is correct prose and only a person can tell it from "waiting on X."

## Practical shape

```
## YYYY-MM-DD HH:MM | <who/which track> | <area>
**Status:** green | yellow | red — what was verified, on what, when
**Changed:** the delta — NOT a re-summary of the project
**Next:** the first move, with enough context to make it
**If it fails:** the contingency
**Confirm:** the one thing the next reader must restate before starting
```

Three rules around it:

- **Append-only, and inject only the newest entry.** That is what lets it be as long as it needs to be — the length cap exists only when you read five of them as an index. Old entries cost nothing if nothing loads them.
- **Delta only.** The reader has the state document; do not restate the project.
- **If you cannot write "Confirm," the entry is not finished.**

## The caveat that matters most

**A template alone changes nothing.** A randomized trial gave nurses a structured SBAR form for after-hours physician calls: it did **not** improve the content communicated and trended toward *fewer* background details (Joffe et al., Jt Comm J Qual Patient Saf 2013;39(11):495–501).

So do not ship the shape and expect the behaviour. Whatever can be enforced by a script must be — the staleness check, the size measurement, the archive move — because the same project measured every script-backed rule holding and every discipline-only rule failing. A form is a reminder, not a mechanism.

Related: `shared-budget-caps-relocate-mass.md` (what to inject and what to leave on disk), `n-copies-of-truth-drift-guard.md` ("docs don't run; scripts do"), `parallel-writers-minting-ids-collide.md` (an ID that escaped into an immutable reference can never be reclaimed).
