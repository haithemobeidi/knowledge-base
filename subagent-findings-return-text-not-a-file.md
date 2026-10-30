---
stack: [any, claude-code, llm-agents, research]
kind: gotcha
last_verified: 2026-10-30
---

# Brief a research subagent to return its findings as text: a file write can be refused, and a stopped agent takes its findings with it

**One-liner:** A subagent's findings exist in exactly one place until it hands them over: its own transcript, which the parent cannot read (the transcript file is the whole conversation and overflows the parent's context). If the brief says "write a findings file" and the write is refused, or the agent is stopped a turn before it hands off, the parent has paid for research it cannot see. Make the final message the delivery channel, with the file as an optional extra, and never stop an agent that is about to report.

## The shape

Three research agents were briefed identically: research a thread, then write ONE findings file at a scratchpad path in a claim / source / quote format, and return the path plus a summary. Two of the three reported back that the write was refused ("the harness blocked writing the findings file; subagents must return findings as text") and pasted the findings into their final message instead, which worked. The third wrote its file without complaint, to the same directory. Why two were refused and one was not was not established; the agents ran with identical tool sets and briefs.

The costly part came next. The third-thread agent was running long and the user had just complained about cost, so the parent stopped it. The stop landed on the turn where the agent, having had its Write refused, was switching to a Python script to write the file by another route. Its research was complete and verified, and all of it sat in a transcript the parent could not open. The only way to recover it was to resume the agent with one more message ("do not run any tools; paste what you have") and pay for another turn. The resumed agent complied and returned 220 lines of verified findings that would otherwise have been lost.

Two separate traps, then:

1. **The output contract depended on a permission the agent did not control.** A file path in the brief is an instruction the harness can veto; the agent's final message is not.
2. **Stopping an agent is not free, and it is most expensive at the end.** An agent that has finished researching and is composing its handoff has spent everything and delivered nothing. That is exactly when a cost-driven stop is most tempting, because the elapsed time is highest.

## What to do

- **Make the final message the contract.** "Return your findings as plain text in your final message, in this shape: ..." The parent saves them to a file itself if a file is needed; it is a cheap Write from text already in context.
- **If you also want a file, say it is optional** and tell the agent not to spend a single tool call working around a refusal: "If the write is refused, do not retry by another route; return the text."
- **Before stopping an agent for cost, check for its output.** List the directory it was told to write to, or look at whether its siblings have finished. If it is likely near handoff, send it a stop-and-report message instead of killing it: one short turn that returns the work beats a kill that returns nothing.
- **When a stop did land mid-handoff, resume with a tools-off message.** "Do not run any tool. Paste the findings you already have, in the agreed shape, and stop." The agent's context is intact and the turn is cheap relative to the research.
- **Keep research briefs short on mechanics.** The format of the deliverable matters; the path on disk is the parent's problem.

## Case (Cove ACS research, 2026-10-29)

Three `general-purpose` agents, each with a scratchpad `.md` path in the brief. Two refused-then-pasted, one wrote. The stopped agent was resumed once and delivered in full. The parent then wrote its own consolidated findings file from the three texts, which is what the project kept.

Related: [[subagent-inherits-the-parent-model-unless-told]] (the same session's other lesson: the stop happened because the agents were on the wrong model), [[handoff-for-a-reader-with-no-memory]] (the findings message is a handoff; shape it like one).
