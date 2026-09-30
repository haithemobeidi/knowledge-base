---
stack: [claude-code, process, security, any]
kind: gotcha
last_verified: 2026-09-30
---

# A third-party Claude skill is text injected into the model's context, not a new ability: read it before installing, and check its date

**One-liner:** skill packs shared online ("motion skills", "design skills") look like capabilities, but a `SKILL.md` is instructions that get loaded into Claude's context when it triggers, plus any scripts it tells Claude to run. It can't teach the model anything the model couldn't do before, and it can make the output worse by pinning an outdated API. Treat installing one like accepting a pull request: read all of it, check its scripts, check it against the library's current docs.

## The case

2026-09-30, Playmoir. The user found `freshtechbro/claudedesignskills` → `motion-framer/SKILL.md` alongside a post about motion graphics made with Claude, and asked whether Claude now "has motion skills". A research pass read the skill:

- **What it is:** documentation and code patterns for the Motion animation library (variants, gestures, layout animations, scroll effects). Bundled Python scripts import only the standard library and write an output file. No command execution, remote fetches or package installs. Harmless.
- **What it isn't:** new capability. Everything in it is ordinary library knowledge.
- **Why it would have hurt:** every sample imports from `"framer-motion"`, the library's old package name, not the current `"motion/react"`, and nothing covers React 19. Installed, it would have steered generated code toward the legacy import.
- **What the post actually showed** (16 looping HTML animations): its author's own line, "it wasn't one prompt. I needed the exact states, a good reference and a few rounds of fixes." The result came from the iteration loop, not a skill.

The work that followed used no skill: three motion directions as a mock, judged by the user's eye (see `motion-mock-harness.md`).

## The check before installing a skill

1. **Read the whole `SKILL.md` and every bundled script.** You are adding instructions to every session where it triggers. Look for commands it tells the model to run, URLs it fetches, packages it installs, and anything that touches credentials or pushes data out.
2. **Date it against the library.** Compare its imports and APIs with the library's current docs. Skills are written once and rarely maintained; libraries rename packages and move APIs.
3. **Ask what it adds.** Project-specific conventions, house style, a workflow the model can't infer: worth it. A summary of a public library's docs: usually not, and it goes stale.
4. **Mind the context cost.** Every installed skill's description sits in context, and a triggered skill loads whole (see `shared-budget-caps-relocate-mass.md`).

## Related

- `claude-project-template/DESIGN.md`: how this template's own skills are scoped.
