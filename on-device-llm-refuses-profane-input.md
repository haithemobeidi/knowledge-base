---
stack: [llm, android, ml-kit, gemini-nano, chrome-ai, privacy]
kind: decision-record
last_verified: 2026-10-02
---

# On-device LLMs refuse profane input, so when emotional text is the input, defuse it before the model

**One-liner:** small on-device models (Gemini Nano through ML Kit GenAI on Android, and Chrome's built-in AI is the same family) ship with safety filtering you can't turn off, and they refuse or blank out on input like "fuck you". That's fatal for a product whose input is anger: a rant-to-reply rewriter, a journaling app, a de-escalation tool. Don't fight the filter and don't jump straight to the cloud. Put a deterministic step in front of the model that splits the text into **the feeling** (shown back to the user) and **the facts** (sent to the model), and drops the insults. The model never sees what it would refuse, and the output gets better, because the facts were the only part the reply needed.

*Rephrase Buddy (BuddySystem), 2026-10-02. The user's report from using the Android MVP: "issue though with local phone AI is it censors so i can't type 'fuck you' or something". The decision is in BuddySystem's DECISIONS.md; the defuse pass itself is not built yet, so treat the mechanism below as the design, not a measured result.*

## Why this bites privacy-first apps hardest

The appeal of on-device AI is that the user's angriest, most private text never leaves the phone. That text is exactly what the on-device filter rejects. The obvious escape, sending it to a cloud model with looser filtering, breaks the privacy promise *and* the economics: a lifetime-purchase app can't carry an ongoing per-request cloud bill. So the fix has to happen before the model, on the device.

## The pattern: defuse, then rewrite

```
raw rant ──► defuse (deterministic, on device) ──► { feeling, intensity, facts[] }
                                                        │
                       shown to the user ◄── feeling + intensity ("Frustrated · 8/10")
                                                        │
                         model input ◄── facts[] + chosen tone + audience
```

- **Feeling + intensity** comes from word lists and simple signals: profanity count, caps ratio, `!!`/`??` runs, second-person insults. Showing it back to the user ("sounds like you're frustrated, about 8 out of 10") is affect labeling, which has research support for reducing the emotional response (Lieberman et al., 2007). Venting itself doesn't (Kjærvik & Bushman, 2024 meta-analysis).
- **Facts** are the rant minus insults and profanity, with the claims kept: "I said it three times", "the export is broken on the admin account". Show the user the facts the model will get, so nothing is a surprise.
- **The rules live in code or data, not in a prompt.** A prompt asking the model to "ignore the swearing" still hands it the swearing.

## Options weighed

| Option | Privacy | Cost | Verdict |
|---|---|---|---|
| Send raw text to on-device model | ✅ | free | ❌ refused |
| Defuse pass, then on-device model | ✅ | free | ✅ default |
| Less-filtered open model on device (Gemma/Qwen-class via llama.cpp or MediaPipe) | ✅ | 1GB+ download | fallback if defuse output isn't good enough |
| Cloud model, user's own API key | ⚠️ user's choice | user pays | opt-in tier; lifetime-compatible ([`byo-api-key-client-direct-tier.md`](./byo-api-key-client-direct-tier.md)) |
| Cloud model, our key | ❌ | ongoing | subscription only, never lifetime |

## Gotchas

- **Refusals can be silent.** An on-device rewriter can return empty text or a generic "couldn't generate a response" instead of a clear refusal. The Rephrase MVP already saw that message on very short inputs, so the same error text can mean two different causes. Log the input class (length, profanity count) next to failures before concluding which one you hit.
- **Don't over-strip.** "The export is broken" is a fact; "broken AGAIN" carries the useful information that it's a repeat. Keep repetition and time markers as facts.
- **Never send raw text by default,** even when a cloud tier exists. Make sending the original an explicit, visible choice.

## Related

- [`llm-summarizer-canonicalizes-user-content.md`](./llm-summarizer-canonicalizes-user-content.md): another case of a model quietly rewriting what the user meant.
- [`byo-api-key-client-direct-tier.md`](./byo-api-key-client-direct-tier.md): the bring-your-own-key tier that keeps cloud optional.
