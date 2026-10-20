---
stack: [marketing, social-media, instagram, agents, research, process]
kind: pattern
last_verified: 2026-10-19
---

# News graphics come from research plus official art in templates, never an image model; verify one claim per agent

**One-liner:** asking an image model for a "cinematic news graphic" gets you invented art, a splotchy "atmospheric" texture, the platform's AI label, and facts from the model's memory, which is stale by construction. Split the job instead: an agent researches and grades every claim, official art goes into a fixed HTML template untouched, headless Chrome renders it. When the research is delegated, give each claim its own verifier agent.

## The failure (Playmoir, 2026-10-19)

A friend running the app's Instagram used a well-written "master prompt" for an image model: brand colours, layout, "realistic game-inspired artwork, atmospheric fog, subtle fading-memory effects". The result:
- AI-drawn versions of real game characters, and a mottled texture over everything (the "fading-memory effect" taken literally);
- Instagram's "AI info" label under the account name;
- **wrong facts:** it announced Resident Evil Requiem as "officially revealed, launching February 27, 2027", eight months after the game had shipped on Feb 27, 2026, while the caption (written separately) celebrated 8 million sales. Image and caption contradicted each other.

No prompt wording fixes this. The model is *drawing* the picture, and it answers "what's the news" from training data.

## The pattern

1. **Date first, from a live search.** Every claim about "upcoming" vs "out", sales, or "new" is judged against it.
2. **Facts are researched, traced, graded.** For each claim: trace to the origin (ten articles quoting one tweet are one source; upvotes prove nothing), judge the origin (official / press with its own reporting / a leaker's track record / players), find one independent confirmation, then grade it: Confirmed / Reported / Rumor / Unverified. The copy's wording follows the grade ("Konami says…", "Bloomberg reports…", a labelled rumor post, or not posted).
3. **Images are official and untouched.** Steam's `store.steampowered.com/api/appdetails?appids=<id>` returns 1920×1080 official screenshots; publishers' press pages have key art. The only treatment allowed is a CSS gradient into the background so text is readable.
4. **Layout is HTML + one shared stylesheet**, a few templates (news, memory card, carousel cover, carousel slide), rendered with `chrome --headless=new --screenshot --window-size=1080,1440 --virtual-time-budget=5000` (the budget lets web fonts load).
5. **One verifier per claim.** List every fact the post might use, one small claim per line, *before* writing, including the ones you "know". Each verifier agent gets one claim, the game and today's date, nothing else, and returns one source-log row with a "safe wording". Narrow context means it can't blur two facts together or carry an assumption from one claim to the next.
6. **The writer's own sentences are claims too.** A fact you add while writing needs a row before it ships.
7. **A cold check.** A separate agent that didn't write the post runs the checklist and re-opens the headline's sources.

## What the per-claim checking caught in its first run (Castlevania: Belmont's Curse)

- **Too cautious is also a miss.** The research agent marked "Rose is Trevor Belmont's daughter" Unverified; one more look at Konami's launch page found it verbatim. It became the best headline. Check before you drop, not only before you post.
- **The writer's own filler.** "The first new Castlevania in years" and "no need to have played it" had no source; both were cut.
- **Precise wording keeps a claim true.** "Made by the Dead Cells team" overstates; "made with Motion Twin, the studio behind Dead Cells" is what Konami and Steam support.
- **Two official dates a day apart** (Steam "Oct 14" vs Konami "October 15") are time zones: use the publisher's.

## Platform facts that shaped the templates (Instagram, verified 2026-10-19)

- Since May 2026 Instagram stops recommending accounts that "primarily post unoriginal content in photos or carousel posts"; reposted material must be meaningfully added to (e.g. "unique text… that provides more context"). Pure news reposts are the riskiest content a news account can make, so every post needs an angle.
- 3:4 (1080×1440) shows uncropped in the feed (Mosseri, 2025).
- Carousels get a "second chance" starting at slide 2, so slide 2 must stand alone.
Full table with sources: the `social-posts` skill's baseline in this repo.

## Where it lives

Playmoir's kit (agent instructions, knowledge files, templates, helper agents, a research walkthrough): `Checkpoint/docs/marketing/social-agent/`. Related: [chase-industry-stats-to-a-primary-source](./chase-industry-stats-to-a-primary-source.md) (the same instinct applied to one number), [character-consistency-via-edit-model-not-reprompting](./character-consistency-via-edit-model-not-reprompting.md) (when you *do* use image models).
