---
stack: [any, claude-code, llm-agents, research]
kind: gotcha
last_verified: 2026-10-30
---

# A subagent inherits the parent's model unless told otherwise: three research agents ran on Fable for 45 minutes

**One-liner:** In Claude Code, an `Agent` call with no `model` parameter and no `model` in the agent definition runs on whatever the main conversation runs on. A Fable or Opus session that fans out research therefore fans out Fable or Opus, at Fable or Opus prices, for search-and-quote work Sonnet does fine. Pass the model on every research spawn, and set a harness-level default so an omitted parameter falls to the cheap tier instead of the expensive one.

## The shape

A support-research question ("can contactless cards in a wallet case break a Bluetooth door pass?") was split into three threads and sent to three `general-purpose` agents in parallel from a Fable session. None of the calls carried `model`. Each agent ran 14 to 19 minutes, made 80 to 105 tool calls, and used about 200,000 tokens. The user saw the combined usage and asked whether the agents were Sonnet or Fable. They were Fable.

The resolution order, from the Claude Code subagents documentation (verified 2026-10-29):

1. the per-invocation `model` parameter on the `Agent` call;
2. the agent definition's `model` frontmatter, where `inherit` means the main conversation's model;
3. the `CLAUDE_CODE_SUBAGENT_MODEL` environment variable, when set to an alias or model ID;
4. the main conversation's model.

The built-in `general-purpose` agent has no `model` of its own, so with nothing set it lands on step 4. The documentation adds two details that matter: `CLAUDE_CODE_SUBAGENT_MODEL` "is a default, so a subagent's definition or a model Claude passes still takes precedence over it", and setting it "by itself doesn't change the model the built-in Explore and Plan subagents run on". `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` makes the variable override every source, including explicit picks, for subagents, teammates and workflow agents.

The model wrote the three briefs carefully (goal, what was ruled out, output shape, sources to prefer) and never once thought about which model would execute them. Cost is not in the brief; it is in a parameter the brief's author forgets.

## What to do

- **Every research, exploration or summarising spawn carries `model: "sonnet"`** (or `haiku` for a trivial lookup). Reserve the expensive tier for the main thread, which verifies the load-bearing claims anyway, and for subagents the user explicitly asks to run there.
- **Set the harness default in the user settings file** so an omitted parameter falls the cheap way:

  ```json
  {
    "env": {
      "CLAUDE_CODE_SUBAGENT_MODEL": "sonnet"
    }
  }
  ```

  Add `"CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "1"` only if you want a hard cap: it also downgrades reviewers and other agents a skill deliberately runs on Opus. Explore and Plan keep their own models either way.
- **Pin the model in your own agent definitions.** A `model: sonnet` line in the frontmatter of `~/.claude/agents/<name>.md` wins over the environment default and loses only to an explicit parameter. An agent file with `model: inherit` is the expensive path by design; make that a choice, not an accident.
- **Say the model in the status line when spawning.** "Sending three Sonnet agents out" is a sentence the user can object to in time; "sending three agents out" is not.
- **If the user notices cost mid-run, do not reflexively kill the agents.** An agent near its handoff has already spent the money; killing it loses the findings as well (see [[subagent-findings-return-text-not-a-file]]). Check for finished output first, stop only what is clearly far from done.

## Case (Cove ACS research, 2026-10-29)

Three Fable agents, about 45 minutes combined, before the user asked "were these sonnet agents you spun off or all fable agents?". The answer was yes, all Fable. A memory rule was saved the same day: research subagents run on Sonnet, model passed explicitly, Fable is the main thread only.

Related: [[hook-output-string-cap-measure-what-arrives]] (another harness behaviour that only shows up when you measure what actually happened), [[third-party-claude-skills-are-context-not-capability]].
