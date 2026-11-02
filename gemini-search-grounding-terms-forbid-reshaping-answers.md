---
stack: [llm, gemini, google, terms-of-service, research]
kind: gotcha
last_verified: 2026-10-27
---

# Gemini's "Grounding with Google Search" terms forbid caching, reshaping or analysing grounded answers, so a feature that stores or grades them needs its own retrieval

**One-liner:** Grounding with Google Search is the easy way to give a Gemini answer live web sources, but its terms limit what you may do with the result. You may show it only to the user who asked, and you may not modify it, mix other content into it, cache it, re-serve it, or analyse it. A feature that grades answers, builds a shared answer cache, restructures the text into cards or tables, or learns from past answers can't sit on grounded results. Do the retrieval yourself instead: a search API finds the pages, your app fetches them, and the model reads them as an ordinary prompt, so the output is yours to keep and reshape.

## The shape

Playmoir's "tips finder" idea: a player asks a question about their game, and the app answers with sourced, graded tips, cached so the next player who asks the same thing gets the answer at once. Grounding looked like a one-flag solution. The terms rule out three of those four words (graded, cached, shared).

## What the terms say

From https://ai.google.dev/gemini-api/terms, section "Grounding with Google Search" (read 2026-10-27; the page shows no revision date):

- Who may see it: grounded results are shown only to the end user who submitted the prompt.
- No reshaping: you "will not modify, or intersperse any other content with, the Grounded Results or Search Suggestions".
- No caching or reuse: you "will not, and will not allow your end user or any third party to, cache, frame, syndicate, resell, analyze, train on, or otherwise learn from Grounded Results or Search Suggestions".
- Narrow storage: "You may copy and store, for up to two (2) years, the text of the Grounded Result(s)" only for (1) your own evaluation of how you display them, (2) that end user's own chat history, visible only to them, and (3) temporary storage to resubmit in a later function-call prompt.
- Own app only: "You will only use Grounding with Google Search in an application that is owned and operated by you".
- Also: no click tracking or link monitoring on the results, and no interstitials between a link and its page.

Reading (not legal advice): a per-user chat history is allowed; a cross-user answer cache is not. Whether turning grounded text into structured UI counts as "modify" is not settled by the text. The cautious reading is yes.

## Price, for scale

Gemini 3 and newer bill grounding per search query the model chooses to run, not per prompt: 5,000 free a month shared across those models, then $14 per 1,000 (https://ai.google.dev/gemini-api/docs/google-search, "You will be charged for each individual search query performed"). Gemini 2.5 and older bill per prompt. One user question can trigger several queries.

## The way out

Separate the search from the model:

1. a search API returns URLs for the question;
2. your app fetches those pages (respecting each site's own terms; many game wikis forbid scraping);
3. the model reads the fetched text in an ordinary, ungrounded request and writes the answer.

The answer is then the model's output on your prompt, governed by the model's general terms rather than the grounding section. Check the search provider's own storage terms before caching anything derived from its results, since some search APIs restrict storage too. Plain search APIs were also far cheaper per query than grounding in the 2026-10 comparison: roughly $1 to $5 per 1,000 against $14. Re-price before building.

## Before building anything on a "grounded" or "with search" feature

Read the terms section for that feature, not just the pricing page. The limits sit there, and they decide the architecture.
