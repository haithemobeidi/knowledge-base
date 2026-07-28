---
stack: [any]
kind: playbook
last_verified: 2026-07-27
---

# Patch the consumer, not the value — changing a binary you can't rebuild

**One-liner:** when you must change the behavior of a compiled artifact you don't own, the folklore move is "find the constant, overwrite it" — but constants usually arrive from *outside* the binary (asset packs, config, saved state, network), so the copy inside the executable is a decoy. Patch the **branch that consumes** the value instead: it's the single choke point every source funnels through. Measured from the session this was extracted from: the offending value lived in an 18.5 GB asset pack, **not** in the 78 MB executable — the conventional value-search patch would have found nothing to change, while a **1-byte edit to the consuming branch** fixed it permanently and survives the value changing.

## The failure shape

You need one behavior changed in something you can only edit as bytes: a game executable, a vendored `.dll`, a minified bundle, a signed binary, a firmware image. The published technique for this class of problem is almost always *value-shaped*:

> "Search for the float `1.7777778` (`39 8E E3 3F`) and replace it with your value."

That works only when the binary is the **origin** of the value. It quietly fails when the binary is merely a **consumer** of it, which is the common case in any engine/asset architecture:

- game engine + asset pack (value set per-object in content, engine just reads it)
- app + config file / feature flags / remote config
- runtime + user profile or saved settings
- library + caller-supplied arguments

The tell: you find the constant, patch it, and nothing changes — because the shipped default you overwrote gets overwritten *again* at load time by the real source. You can burn a lot of rounds concluding "the patch didn't take" when the patch was applied perfectly to an irrelevant byte.

## The rule

**Find the code that branches on the value, not the value.** A value can enter from N sources; the code that acts on it is usually one place. Patching there is source-agnostic and therefore override-proof.

Concretely, the shape you're looking for is a test-and-branch:

```
test byte ptr [rcx+0x30], 1     ; read the flag (from wherever it came)
je   <good path>                ; branch
<the behavior you want gone>
```

You do not care where `[rcx+0x30]` was populated. Neutralize the branch and every source becomes moot.

## Prefer length-preserving edits

Two ways to force that branch:

| Edit | Bytes | Cost |
|---|---|---|
| Rewrite `je rel32` → `jmp rel32` | 6 → 5 | instruction shrinks; must recompute the displacement (it's relative to the *end* of the instruction, which just moved) and pad with a `nop` |
| Flip the test's immediate: `test r/m8, 1` → `test r/m8, 0` | 4 → 4 | condition is now always false; branch always taken; **no length change, no displacement math** |

Prefer the second whenever a comparison feeds the branch. Same effect, no relocation risk, and the diff is one byte — trivial to review, trivial to revert. Check that nothing between the test and the branch clobbers flags (`mov`/`movaps`/`movss` don't; arithmetic does).

## Use what shipped with the binary

Before pattern-scanning blind, **inventory the build's own metadata**. Release builds ship debugging artifacts far more often than people assume:

- `.pdb` next to a Windows `.exe` (this happens constantly in game builds)
- `.map` files, unstripped ELF symbol tables, `.dSYM` bundles
- `.js.map` sourcemaps served next to minified bundles
- embedded DWARF in "release" firmware

A shipped `.pdb` turns "scan 78 MB for a plausible pattern" into "resolve the exact address of `Namespace::Function`." You don't need a full PDB parser for a one-off: public symbols are `S_PUB32` records whose layout puts `segment` and `offset` immediately *before* the name string, so you can find the mangled name with a plain byte search, read the 10 bytes preceding it, validate the record-type tag is `0x110E`, and map `segment:offset` through the PE section table to an RVA. ~40 lines, no dependencies beyond a PE reader.

## Cross-validate the site before writing bytes

Never write to an address derived a single way. Get two independent derivations to agree:

- Resolve function `B`'s address from the symbol table.
- Disassemble function `A` and read the `call` target in the branch you intend to patch.
- If A's `call` lands exactly on B's independently-resolved address, you are provably in the right function and the right branch.

This is cheap and it's the difference between "I'm fairly confident" and "I know." A wrong byte in a 78 MB binary can produce a crash a thousand frames later that looks nothing like a bad patch.

## Distribute by signature, never by offset

The moment you share the fix, the hardcoded offset becomes a liability — the next patch/update shifts every address and a naive tool happily corrupts a stranger's install. Ship a **pattern scan** instead:

- Match the instruction plus enough surrounding context to be unique. Measure the uniqueness: in this case the bare 4-byte test matched **9 times**; the test + a following `je` + the value-load within a 128-byte window matched **exactly once**, landing on the known-good address.
- **Refuse to write on anything but exactly one match.** Zero matches means the build changed — say so and stop. Two means you'd be guessing. Both are strictly better than a plausible wrong write.
- Back up before the first write, and make the tool detect its own prior work so re-running is a no-op rather than a double-patch.

For byte-scanning in a scripting language without a fast search primitive, decode the buffer as latin-1 (codepage 28591 maps bytes 0–255 to chars 0–255 one-to-one) and use the native string `IndexOf`. Avoids a per-byte interpreted loop over tens of megabytes.

## Know which layer owns which half

Removing a behavior and choosing its replacement are often **two different layers**, and each alone is unsatisfying:

- the binary patch removed the constraint, but left the replacement behavior at an unhelpful default
- a config key selected the right replacement, but couldn't remove the constraint (the flag wasn't config-backed — no key exists to override it)

Applied separately, each looked like "partially worked," which is exactly the signal that reads as *failure* and tempts you to revert the half that was correct. Before concluding a patch didn't work, ask whether it's necessary-but-insufficient. Check which knobs are genuinely exposed (in this ecosystem, whether a property is marked `config`) so you know which half you can get for free and which needs bytes.

## Diagnose the failure mode before choosing the layer

One user-visible symptom usually covers several mechanically distinct causes, each fixed at a different layer. "It's not displaying right" split into: the value was clamped on load / the image is stretched / the image is cropped / the image is correct but inset with blank margins. These have *nothing* in common as fixes.

Cheapest possible disambiguation: get a description of what it actually looks like. One question resolved this after a launch-and-inspect cycle had already been spent on the wrong hypothesis. Automated inspection is also weaker than it looks here — screen capture of a hardware-composited surface commonly returns the desktop rather than the application, so an empty-looking capture proves nothing.

## When it's overkill

If you can rebuild the artifact, change the config, or the value genuinely does originate in the binary (a hardcoded limit with no external source) — just do the direct thing. This playbook earns its cost when: the artifact is opaque and un-rebuildable, the value demonstrably comes from outside it, or the patch has to survive updates and be handed to other people. A one-off local hack you'll redo in five minutes doesn't need signature-scanning.
