---
stack: [product, research, data, scoping]
kind: gotcha
last_verified: 2026-09-18
---

# The risk you flagged passing is not evidence the idea survived — test fit, not access

**One-liner:** when you propose repurposing a data source for a job it was not built for, the risk you instinctively name is about **access** — is the data reachable, complete, permitted, parseable? Those questions are concrete, answerable, and feel like diligence. The thing that actually kills the idea is almost always **fit**: whether the data you can happily obtain is *about* the thing you need. And because access questions feel rigorous, clearing one manufactures confidence that the idea has been reviewed, when the question that matters was never on the list.

## The worked example

**The pitch:** ingest Steam's achievement schema per game and use it as a corpus of boss names, to give an AI writing about your play session real proper nouns to work with.

**The risk named:** hidden achievements withhold their descriptions — will we get usable *names* for them? A real risk, correctly identified, worth checking.

**It resolved favourably.** Achievement names are public on `steamcommunity.com/stats/{appid}/achievements/` even where descriptions are withheld. The gate passed. The idea now felt validated: someone had asked a hard question and the answer was good.

**It died anyway, on something never listed:** corpus composition. Most games do not name bosses in their achievements. The pitch had generalised from Souls-likes, where the achievement list happens to *be* the boss roster — an unrepresentative case that had quietly supplied the whole premise. Access was fine. Fit was fatal.

## Why the passed gate is the dangerous part

A failed gate kills an idea cleanly and cheaply; nobody is harmed by a risk that fires. The expensive case is the gate that **passes**, because clearing it converts "we have not examined this" into "we examined this," and the examination covered the wrong axis. Everyone now believes the idea has survived scrutiny. The next questions get less rigorous, not more, and design work begins on a premise nobody ever tested.

This is why "test your assumption" is not the whole lesson — that part is close to obvious. The non-obvious half is that **passing a plausible-sounding test actively reduces the chance anyone asks the right question.**

## The countermeasure, which is cheap

**Before designing anything on a repurposed source, run it against the specific case that motivated the idea.**

Not a representative sample, not a benchmark — *the actual case you had in mind when you got excited*. In the example above, that was one lookup against the two games the user had genuinely played that night. It took a minute and killed a feature that had already survived a formal-feeling risk review.

The reason this works is that the motivating case is where your intuition was formed, and it is the one case you can evaluate without any measurement apparatus: you already know what the right answer looks like. If the source cannot serve the example that inspired it, nothing downstream matters.

## A question to add to any "we could use X for Y" pitch

After the access questions, before any design:

> **Is this data *about* Y, or does it merely co-occur with Y in the examples I happen to know?**

If the honest answer is "it is about Y in the games/customers/documents I was thinking of," you have found the real gate, and it is a composition question you can usually settle with a handful of lookups.

## The general rule

**Feasibility questions crowd out suitability questions, because feasibility is concrete.** "Can I get it?" has a yes/no answer, a clear method, and a satisfying feeling of rigour. "Is it the right thing?" is fuzzier, so it gets deferred — and it is the one that decides the outcome. Whenever a plan clears a named risk, ask explicitly: *which risks did naming that one stop us from naming?*

## What NOT to do

- Don't treat a passed gate as validation of the idea. It is validation of exactly one hypothesis, and you chose that hypothesis before you understood the problem.
- Don't generalise from the example that inspired you. It is, by selection, the case where the idea works best — that is why it inspired you.
- Don't build the ingestion layer first because "we will need the data either way." The data is cheap to sample and expensive to pipeline; sample first.
- Don't skip writing the dead end down. A killed idea that leaves no record gets re-proposed, and the second time it will clear the same access gate just as convincingly.

## Related

- [chase-industry-stats-to-a-primary-source.md](./chase-industry-stats-to-a-primary-source.md) — the same instinct applied to numbers: the comfortable check is not the one that decides.
- [suspect-the-statistic-before-the-threshold.md](./suspect-the-statistic-before-the-threshold.md) — questioning the measure rather than tuning against it.
- [negative-control-before-trusting-a-probe.md](./negative-control-before-trusting-a-probe.md) — the experimental-hygiene sibling: prove your test can fail before believing it passed.
