---
stack: [llm, prompt-engineering, ai-features, gemini]
kind: gotcha
last_verified: 2026-08-12
---

# An LLM summarizer with world knowledge silently "corrects" user content back to canonical facts

**One-liner:** if your product runs an LLM over user-authored content about a subject the model knows (a famous game, a real city, a public figure), the model will treat the user's deviations from canon as errors and quietly fix them — and the "fix" survives naive re-generation because your own extracted fields feed the old canon back in. User content is law; the model needs to be told that explicitly, with the failure as an in-prompt example.

## The symptom

A game-journal app summarizes each session note into a one-liner and extracts factual
fields (location, milestone). The user edited their note, renaming a fortress from the
game's real name to their own word. Three rounds of fixes later, the summary STILL said
the game's canonical name:

1. **Round 1:** edits didn't refresh the summary at all (a plumbing bug — summaries
   minted at create-time only). Fixed: content edits clear the summary and re-mint.
2. **Round 2:** the re-mint *resurrected* the old name — the previously-extracted
   factual fields ("milestone: captured <real name> keep") were part of the prompt
   context and outvoted the edited note. Fixed: carry the pre-edit summary as an
   explicit minimal-revision draft, and flip field writes from fill-blanks-only to
   correct-stale.
3. **Round 3:** STILL the real name. The model knew the game (its title was in the
   prompt), judged the user's word a typo for the fortress that "really" exists there,
   and canonicalized it back. No stale input remained — this was pure world knowledge
   overriding the source text.

## The mechanism

Three reinforcing layers, worth checking independently:

- **World knowledge as an error model.** Summarizers are trained to fix typos and slips.
  When the subject is canon the model knows, a user's deliberate rename is
  indistinguishable from a mistake — so "fixing" it is the model doing its job.
- **Extracted-field feedback loops.** Anything your pipeline extracted from *earlier*
  versions of the content and feeds back as context (fields, tags, prior summaries)
  is a vector for old facts to outvote the current source. Regeneration is not
  refresh if yesterday's outputs are in today's prompt.
- **Blanks-only field writes.** "Only fill empty fields" sounds safe but means a stale
  extracted value can never be corrected by a newer source — the stale value is
  permanent the moment it's written.

## The fix (all three layers)

1. **Edits invalidate derived text.** Any content edit clears the derived summary in
   the same write and triggers re-generation; every surface falls back to the raw
   (correct) source text meanwhile, so the system degrades to truth, not to staleness.
2. **Prior outputs enter the prompt only as a draft to minimally revise**, labelled as
   such — never as authoritative context. Extracted fields are written as
   correct-stale (`COALESCE` semantics on null, overwrite on change), not
   fill-blanks-only.
3. **An explicit anti-canonicalization law in the prompt, with the live failure as the
   example.** Ours, roughly: *"The user's names are law. If the note calls a place
   'X', the summary says 'X' — never the game's real name for it, even if you are
   certain you know the real one. Example: the note says 'Flaming keep'; you know the
   region's real fortress is <real name>; the summary must still say 'Flaming keep'."*
   The concrete example mattered — the abstract rule alone did not stop round 3's
   typo-judgment. Mirror the law verbatim into every prompt that touches the content
   (we had two prompt sites; one law, copied, with a comment binding them).

## The ten-second identification

Diff the model's output against the user's source for **proper nouns the model could
know from training**. If the output "fixes" one back to canon, you have this bug —
and if it survives a clean regeneration, go hunting for the feedback loop (layer 2)
before blaming the prompt.

## The general rule

A generative feature over user-authored content needs the same discipline as a sync
engine: **the user's version is the authoritative replica, and everything derived from
it must be invalidated by edits and forbidden from writing canon back over it.**
Models are helpful by default, and helpfulness includes correcting you; products built
on memory and journaling are exactly where correction is data loss.

## Related

- [local-fixture-reverts-under-authoritative-sync.md](./local-fixture-reverts-under-authoritative-sync.md) — the sync-engine version of "an authoritative-looking source quietly overwrites the user's truth."
- [resolve-versions-from-the-registry-not-a-search-index.md](./resolve-versions-from-the-registry-not-a-search-index.md) — its "LLM answers are the same class of cache" aside is this lesson's cousin: model knowledge is a stale snapshot, not ground truth.
