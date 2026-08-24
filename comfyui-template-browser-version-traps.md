---
stack: [comfyui, image-gen, diffusion, desktop, windows]
kind: gotcha
last_verified: 2026-08-24
---

# ComfyUI's template browser: version traps, wrong-lineage downloads, and the sampler that isn't there

First live session with ComfyUI Desktop (models pre-installed, app never launched before). Four traps, each of which cost a confused round-trip; one cost a 20 GB wrong download.

## Trap 1 — there is no template for your model version, and that's normal

Built-in templates ship with the app and lag (or skip) model releases. We had `Qwen-Image-Edit-2511` installed; the browser offered only `2509`, a specialized "2511 Material…" variant, and Int8 variants. No plain 2511.

**Fix — don't hunt for an external workflow; repoint a sibling.** Open the nearest same-family template (2509), decline its download offer, then change exactly two dropdowns: diffusion model → your installed file, LoRA → your installed Lightning LoRA. Model families share their text encoder and VAE across versions, so everything else in the graph is already correct.

Corollary: the **"missing models" error is not breakage** — it just means dropdowns still reference the files the template wanted to download. The red-outlined nodes are the to-do list. Repoint each; never accept the download when equivalent files are already on disk.

## Trap 2 — the version number is a release month, not a lineage

"Qwen-Image **2512**" and "Qwen-Image-**Edit** 2511" are **different model lines** (text-to-image vs image editing) that happen to share a month-numbering scheme. Seeing "2512 > 2511" and assuming it's the newer version of the same thing downloaded ~20 GB of the wrong lineage.

**The ten-second tell:** an image-*edit* workflow has a **Load Image** input node; a text-to-image workflow doesn't. Check for it before downloading anything.

## Trap 3 — precision variants are separate templates wanting separate downloads

Template tiles come in precision flavors (`Int8`, fp8, bf16). An Int8 template references int8 model files — if your installed files are fp8/bf16, it will demand duplicates of models you already own. Match the template variant to the files on disk, or apply Trap 1's dropdown-repoint.

## Trap 4 — modern templates are subgraphs: the KSampler exists but is invisible

Recent official templates fold the whole pipeline into one big node (e.g. "Image Edit (Qwen 2509)"). Consequences that mislead a newcomer:

- **There is no visible KSampler.** Searching the node-library sidebar finds nothing (that sidebar is a catalog for *adding* nodes, not a search over your graph). The sampler is inside the subgraph — the expand icon in the node's title bar opens it.
- **Don't add a KSampler** to "fix" this — a fresh one arrives unwired and does nothing.
- **Sampler settings may be governed by a subgraph widget instead.** Ours had `enable_turbo_mode: true`, which internally engages the Lightning-LoRA 4-step/CFG-1.0 path. Check the subgraph's own widgets before manually hunting steps/CFG at all.

## Sundry: finding your file among look-alikes

All models dump loras/encoders/VAEs into shared folders, so every dropdown is full of other models' files (a Wan video LoRA sat where the Qwen LoRA belonged; two near-identical `qwen*` text encoders differ only in which model they serve). **Type in the dropdown to filter** — and know your filenames before you start. Keep a per-machine notes file mapping model → exact encoder/VAE filenames; it converts every one of these dropdowns from a guess into a lookup.
