---
stack: [zendesk, customer-support, llm-agents, browser-automation]
kind: gotcha
last_verified: 2026-11-18
---

# Zendesk: AI drafts must leave out the sign-off, and writes through /api/v2 can fire "via API" triggers

**One-liner:**
- **Sign-off:** the agent workspace adds the agent's signature to public replies, and a signature usually starts with the sign-off ("Best Regards, <name>"). An AI-drafted reply that ends with its own sign-off arrives doubled. Read the signature (`/api/v2/users/me.json`, field `signature`) and end drafts before it.
- **Writes:** updates made through the REST API are logged as coming "via API", and triggers conditioned on that channel fire on them. On one instance, six AI-agent automation rules did. Make ticket changes in the agent workspace until you've tested how your write path is logged.

*A support team's Zendesk with Fin (Intercom) answering first, 2026-11-17. The signature was verified on a real reply sent from the workspace: it appeared once, after the drafted text.*

## The signature

- `GET /api/v2/users/me.json` returns the agent's `signature`, e.g. "Best Regards,\nName\nTitle".
- A reply submitted from the agent workspace showed the drafted text followed by the signature, once.
- So the drafting prompt says: no sign-off, and a draft ends after its last line.

## "Via API" is a trigger condition

- Every comment and update carries `via.channel`: `web` for the agent workspace, `api` for REST calls (agent bulk edits count as `api` too), `rule` for triggers.
- On this instance, six rules belonging to the AI agent's integration (mark solved, mark pending, mark open, courtesy close, rating tag, follow-up counts) were conditioned on updates via API. Any tool that writes through `/api/v2` can set them off on tickets carrying that integration's tags.
- **Untested:** whether a `fetch` to `/api/v2` from inside a signed-in agent tab is logged as `web` or `api`. Test it once on a throwaway ticket before building tools that write that way. A new ticket can route to the AI agent and send emails, so get the owner's OK first.

## Smaller traps from the same work

- **One comment per submit.** A public reply and an internal note need two submits, so post the reply first.
- **Followers aren't CCs.** The requester doesn't see followers. `follower_ids` and `email_cc_ids` are separate, while the older `collaborator_ids` mixes both. A rule like "take internal people off the CC" is about `email_cc_ids`.
- **Read before you rely on a status.** On this instance, Pending started a follow-up-then-close automation only for some assignees, and three custom statuses were excluded by name. Read the automations' conditions; don't assume what a status does.
- **Switching tickets with a draft open.** An automated `navigate` away from a ticket with unsent text hangs on the browser's "Leave site?" dialog. Switch inside the workspace instead: `history.pushState({}, '', '/agent/tickets/<id>')`, then dispatch a `popstate` event. The drafts on both tickets stay ([[claude-in-chrome-traps]], section 7).
- **Lists in the composer.** Typing `1. ` or `- ` starts a list and the editor adds the marker to every following line. Type it on the first line only, and press Enter twice to leave the list. It leaves no blank line before the next paragraph.
- **The agent session has a maximum length.** Zendesk signs the browser out with `max_session_timeout` even mid-work: API reads return 401 and the tab moves to the sign-in page. An agent that can't sign in should do its status re-reads before the end of the day, and keep a local copy of every draft, since unsent composer text may not survive.

## Related

- [[supervised-support-agent-modular-knowledge-and-earned-autonomy]]
- [[backtest-an-ai-drafting-agent-on-past-tickets]]
