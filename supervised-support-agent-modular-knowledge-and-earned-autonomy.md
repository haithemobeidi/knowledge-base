---
stack: [llm, llm-agents, customer-support, claude-code, prompt-engineering]
kind: pattern
last_verified: 2026-11-18
---

# A supervised support agent: modular knowledge behind a router prompt, one risk test for assumptions, autonomy earned per action

**One-liner:** a support agent that drafts and acts with a human approving each step works best when:
- Its knowledge is split by job, behind a short router prompt: core rules for every ticket, one file per ticket type, one per tool.
- Every assumption passes one test: "if I'm wrong, does someone gain power, lose access, or get notified?" If not, make the obvious call the way a person would. If so, ask or get approval.
- Autonomy is earned one action type at a time, never for role upgrades, removals or mass notices.

On its first live ticket, the old prompt asked the customer a needless question in 80 words. The reworked one made the obvious call in 45 words, matching what the support lead actually sent.

*Cove support copilot, 2026-11-17: two live tickets worked end to end in Claude Code with the support lead's go at each step, after a backtest on 20 past tickets ([[backtest-an-ai-drafting-agent-on-past-tickets]]).*

## Arrange knowledge by job

| Folder | Read | Holds |
|---|---|---|
| `core/` | Every ticket | judgment (act, assume, ask, never); the lead's rulings, which win; voice, including matching the customer's mood; shared facts |
| `areas/` | By ticket type | one playbook per request area (login, accounts, access, work orders...) |
| `systems/` | When touching a tool | what the helpdesk's triggers do per status and tag; how to fill its fields; the AI front-line agent's training; the product's API reads and safe-change procedure; known feature ideas and bugs |
| skills | As procedures | ticket research, bug report, feature request, handoff, trigger fixes |

The router prompt only says what to read when. Why it pays off:
- A ruling changes in one place.
- The agent reads a fraction per ticket.
- After any change you can point a fresh agent at the files for a clean test.

## One test for every assumption

Ask: *if I'm wrong, does someone gain power, lose access, or get notified?*

- **No: make the obvious call.**
  - Example: two tenants whose names differ only in capitals, with only one of them in use. Pick the live one.
  - Example: the requester's own tenant is the default for the person they're asking about.
  - Say it plainly in the reply ("I've moved him to X"). Don't explain the internals a person wouldn't mention.
- **Real split: ask.** Two live candidates, or a request that could mean two different outcomes (move or add?). One to three precise questions.
- **Never assume:** role upgrades, removals and deletions, anything that notifies many people, other users' details.

The first version, written to "ask when unsure", asked about everything and sounded like a bot. The test keeps the caution where it matters.

## Rules that came from the first live tickets

- **Change only the field the task names**, through the app's form, guarded and diffed ([[guarded-write-through-an-apps-own-form]]).
- **Match the customer's mood.** Frustrated: one plain line that acknowledges and owns it, no cheer. Calm: short and friendly. The helpdesk adds the signature ([[zendesk-agent-drafts-and-api-writes]]).
- **Don't show your work in the ticket.** Lookups, assumptions and repro steps go to the human in chat. Internal notes only for a handoff, a link, or something a colleague needs.
- **Test as the requester's role, never staff.** Staff accounts have more permissions, so a bug can hide there. Use a test account in a separate browser profile, on a sandbox, and record the test (a GIF) so "did you test it?" has an answer.
- **Hand off what the agent can't touch.** The issue tracker stayed the lead's: the agent wrote a search prompt for the tracker's AI and a finished draft as a copy-paste page.

## Autonomy is earned per action type

Every action starts behind the human's yes. A peer's advice was to drop approval on everything except customer replies. Rejected for now:
- A wrong role or deletion does damage before anyone notices.
- The helpdesk's API path can fire automation rules nobody tested ([[zendesk-agent-drafts-and-api-writes]]).

The plan instead: an action type stops asking after a run of clean, uncorrected uses, about ten. The never-assume list always asks. The lead's own call was "after many months of testing".

## The first unattended run is read-only, and proves it

Before the agent works tickets with nobody watching, give it one run where it can't write at all.

- **Block writes in the tab and count them.** Wrap `fetch` and XHR so anything that isn't a read is rejected, and report the blocked count at the end. Zero blocked means the agent never tried; that number is the evidence, not the agent's word.
- **Drafts go in a local file keyed by ticket, not the live reply box.** A draft left in the helpdesk's composer is one stray click from being sent, and it's invisible until someone opens that ticket.
- **Every ticket gets an output, even a stuck one.** Findings, the items that need the human's go, a suggested status and a paste-ready reply. For a stuck ticket, say what's missing and who to ask. A ticket the run skipped silently looks the same as one it never saw.
- **Scope the run by time.** "Open tickets created before 5 PM" gives a fixed list; a ticket that arrives mid-run is named as not worked.
- **The human sends the next morning,** after re-reading each ticket live: a customer reply overnight changes the draft.

First run here: five tickets, zero writes attempted, five drafts. Once the human was at the desk and reviewing each one, drafts moved into the live composer, typed but never submitted. That's a supervised habit, not an unattended one.

## Check the agent by rerunning it

After changing the knowledge, rerun a fresh agent on a ticket the human already handled, with the same inputs. Compare its plan and reply with what was done. Here, the old prompt's draft asked which tenant. The reworked one picked the right tenant, changed only that field and flagged a wrong resolution value. It also asked on its own for the access-control mapping a person would check.

## Related

- [[backtest-an-ai-drafting-agent-on-past-tickets]]: measuring drafts before going live.
- [[third-party-claude-skills-are-context-not-capability]]
- [[capture-a-spas-own-api-calls-with-a-fetch-hook]]
