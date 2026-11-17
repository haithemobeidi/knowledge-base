---
stack: [llm, llm-agents, evaluation, prompt-engineering, customer-support, claude-code]
kind: pattern
last_verified: 2026-11-17
---

# Backtest an AI reply-drafting agent on past tickets it never saw: its misses are answers past what it could check

**One-liner:** to find out whether an AI agent can draft support replies the way one specific person would, replay recent handled tickets it was never built from. Give it each conversation only up to the team's first reply, hide subjects the team retitled after handling (they give the answer away), and set its draft beside what was actually sent. First run, 20 tickets, on the builder's own first read: 10 good, 7 OK, 3 poor. Routine work was fine: routing, macros, feature requests, redirects to the building. 8 of the 10 misses answered past what the agent could check. It stated a guessed cause as fact, reported an action as done before asking which records were meant, or skipped a "which one?" question. The fix to test next is read-only lookups plus "only state what you checked", not more knowledge.

*Cove support copilot, 2026-11-16. The agent was Claude (Opus) with a drafting prompt and playbooks built from about 2,600 past tickets of three teammates. The person's own verdicts were still pending when this was written.*

## The setup

**Pick cases the agent has never seen.**
- Recent tickets only, created after a cutoff.
- None that were sampled into the playbook-building batches or cited in the playbooks.
- Stratified across the six request areas: 4, 4, 3, 3, 3, 3.
- The target person's own replies preferred. 18 of 20 were theirs, 2 a teammate's.
- The first team reply has to be at least 22 words, not a follow-up template, with a customer message before it.
- A fixed random seed, so the pick can be rebuilt.

**Give it only what the team had at that moment.**
- The conversation up to the first public team reply, including any earlier bot replies and internal notes.
- The subject, except in 4 of 20 cases where the team had retitled the ticket after handling it. Those showed "(hidden: the team retitled this ticket after handling it)".

**Ask for a full plan, not just a reply.** Per case the agent gave:
- the area and request type
- who is asking
- what it would look up and what result it assumed
- the actions and approvals needed
- its confidence
- questions for the person
- the reply exactly as it would be sent
- an internal note

The "assumed" field makes guesses visible, and the confidence line paid off: one of the three poor drafts had flagged itself low. Five cases went to each subagent, with no live lookups.

**Review side by side, in a local file.**
- Each card shows the conversation (collapsed), the draft, what was sent and what happened next.
- The person rates each draft: As is, Small edits, Big edits or Wrong, plus a note. Ratings save in `localStorage`.
- A "Copy my verdicts" button lets them paste the result back into chat.
- The builder's first read sits on each card, so disagreements are visible.
- The page holds customer text, so it stays a file in an ignored folder. It is never published or committed.

## What it found

| | Cases | Detail |
|---|---|---|
| Good | 10 | Same path as the person, often the same questions. One suggested trying another network, which was the real cause |
| Guessed a cause and stated it as fact | 3 | See the mirrored pair below. A third invented an integration cause |
| Said an action was done before asking which records were meant | 3 | "I've moved the user", "I've cancelled the two tickets", "I've moved the managers". The person first asked which tenant, the open tickets or the whole schedule, and for examples |
| Skipped a "which one?" question | 1 | Three similar tenant names at the target site; the person asked which first |
| Different diagnosis | 1 | Treated an invite that never arrived as an address mismatch |
| Escalated before the team's usual first step | 2 | The team first asked for a screenshot and which reader, or ran its checklist |

**The mirrored pair.** In one login case it assumed a bounced-email block and said it had removed it. The person only asked for a retry while watching the logs, and the code arrived. In another it guessed an address mismatch where the real cause was a bounced-email block. The playbook covered both causes. Only a lookup tells them apart, so more knowledge would not have helped.

**Length.** Measured by the same word count, sign-off excluded: median 89 words in the drafts against 59 in what was sent. That is about a third longer, and 3 of 20 drafts were shorter.

## What to change next

Rules that cost nothing. These are added to the prompt and not yet re-tested:
- **Only state what a lookup in this session showed.** No "I checked", "I'm not seeing" or "our logs show" without one.
- **Don't write that something is done** unless it is unambiguous and the person approves the action together with the reply.
- **When the request is ambiguous, or the answer depends on something unchecked, ask** one to three precise questions. That was the person's own habit in every "acted too early" case.
- **Take the team's first step before escalating.**
- **Set a word target from the person's measured median.** Here 30 to 60 words, from a median of 36 words of body text across about 1,400 replies.

Then build what the misses point to: read-only lookups into the helpdesk history and the product's admin data before drafting. Rerun the poor cases, then try live drafts that the person approves one by one before anything is sent.

## What not to conclude

This is 20 cases on one reviewer's first read. It says where the agent goes wrong, not how good it is. Keep the review page and the verdicts: the cases where the person disagrees with the builder are the next thing to tune.

## Related

- [[subagent-findings-return-text-not-a-file]]: the drafting subagents' results came back in their final message, not in files.
- [[negative-control-before-trusting-a-probe]]: the same instinct applied to an agent. A confident answer is a claim until something it checked backs it.
