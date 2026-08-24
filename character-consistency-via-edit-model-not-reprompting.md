---
stack: [comfyui, image-gen, diffusion, game-assets]
kind: pattern
last_verified: 2026-08-24
---

# Consistent characters come from an edit model re-posing a reference — not from re-prompting the generator

Need the same character in many poses/expressions (game sprites, visual-novel sheets, storyboards)? Re-prompting a text-to-image model with the same description gives you a *different* character every seed — the description underdetermines the character, and the seed fills in the rest. No amount of prompt detail fixes this reliably.

**The pattern: two stages with different models doing different jobs.**

1. **Create once** — a fast text-to-image model generates the character until you like one. Speed matters here because this stage is a volume game (rerolls); a turbo-class model at ~1 s/image changes how you work.
2. **Vary via an image-EDIT model** — feed the chosen image as a reference to an editing model (Qwen-Image-Edit family, or equivalent) and instruct the change. Identity lives in the reference pixels, not in a prompt's description, so it survives.

Verified live (2026-08-24, first attempt, no cherry-picking): a pixel-art knight from Z-Image Turbo, re-posed by Qwen-Image-Edit — helmet, cape, shield emblem, belt, and sword hilt all survived a full pose change from standing to lunging attack. Established ecosystem workflows exist for the same shape (pose-changer and character-sheet workflows on Civitai/RunComfy), so this is convergent practice, not a one-off.

**Prompt shape that worked for the edit stage:** a literal instruction plus explicit same-anchors —
*"the knight in a dynamic attacking pose, swinging his sword forward, **same** pixel art style, **same** armor and red cape, plain white background."*
Edit models follow positionally and literally; name what must not change.

**Scope honestly:**
- Expect small drift per edit (our shield emblem tilted). "Recognizably the same character" is the realistic bar; pixel-identical is not.
- Chain from the *original* reference each time, not from edit-of-edit — drift compounds.
- Static poses/portraits work; smooth *animation frames* (walk cycles) remain diffusion's weak spot. Design scope accordingly — turn-based/static-art projects are the AI-friendly ones.
