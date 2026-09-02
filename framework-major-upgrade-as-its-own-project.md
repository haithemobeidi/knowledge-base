---
stack: [react, typescript, pnpm, vite, process, upgrades]
kind: playbook
last_verified: 2026-09-02
---

# A framework major-version upgrade is its own project — verify to the day, then pause per phase

**One-liner:** run a major-version upgrade (React 18 → 19 here) as a separate, deliberately-tested project: re-verify every version claim against the registry on the day you start (a plan five weeks old was already wrong about "no library bumps needed"), check peer ranges before dreaming of a prerelease, let the codemod do the mechanical part and then normalize what it did to your files, and keep every unrelated modernization out of the train so each manual test gate has exactly one cause.

## Why a separate project, not "while we're in there"

- **No automated tests means every gate is a human click-through.** Bundling idioms (Actions, Suspense, the compiler) with the version bump means a regression at the gate has N candidate causes. One cause per pause is the whole point of pausing.
- **The motive is usually a subset of the release.** Ours was an animation-artifact family that only the View Transitions phase touches; Actions and `use()` are real wins with their own testing surfaces (every form, boot) and ride a later pass.

## The playbook — what actually mattered, in order

1. **Re-verify on the day you start.** `npm view <pkg> dist-tags`, and *unpack the tarball* for the one feature you are counting on (`grep` the production build for the export). Our July plan said React's `<ViewTransition>` was canary-only and "zero library upgrades required." Five weeks later the first was still true and the second was false: **radix-ui 1.4.3 had a React-19-only infinite re-render loop** (unstable composed ref callbacks) fixed in 1.6.1 on 2026-06-30. Claims about *other* libraries age fastest.
2. **Prereleases and peer ranges.** A `19.3.0-canary-*` satisfies **no** caret range — not `^19.0.0`, not `^18 || ^19`, not even `*` — under npm semver's prerelease rule (a prerelease only matches a comparator carrying a prerelease on the same major.minor.patch). With `strict-peer-dependencies=true` the install fails until you override every consumer's peer, and you redo it on every canary bump. Check this before "it's so close, let's use the canary." Verify with `npx semver -r '^19.0.0' 19.3.0-canary-x` (prints nothing = unmet).
3. **Diff the transitive tree of a bundled dependency before bumping it.** For a meta-package like `radix-ui` that re-exports dozens of primitives, `npm view <pkg>@old dependencies --json` vs `@new`, flag any major bump among the children. Ours: 44 minor bumps, zero majors — safe.
4. **Codemod, then normalize.** `types-react-codemod` (`scoped-jsx`, `refobject-defaults`) rewrote 40 files in seconds — and on Windows wrote them with CRLF and double-quoted the imports it inserted, in a repo that is LF and single quotes. `git ls-files --eol` shows it (`w/crlf` on the touched files only); a `perl -pi -e 's/\r$//'` pass restores LF before you review a diff that is otherwise one line per file. Run only the transforms you need, with `--yes` for non-interactive; a whole preset adds transforms for legacy APIs you may not have and noise you must read.
5. **Re-count the hand-sweep.** Type-level sites (global `JSX.Element`, `RefObject<T>` params that now need `| null`, deprecated `MutableRefObject`) roughly doubled between the plan and the port. Counts in an old plan are hints, not the work list. A blanket rename can create duplicate imports (`type RefObject, type RefObject`) — grep after.
6. **Gates per phase, then the human.** Typecheck → the full check suite → a production bundle build (the strongest boot proxy when you cannot run the app yourself) → the user's click-through. Commit only after the human verdict, one commit per phase, so a regression bisects to a phase.
7. **Re-test the behaviour changes on purpose (React 19).** StrictMode double-invokes ref callbacks on mount and reuses memo results across the double render; render errors are no longer re-thrown out of `root.render()` — wire `onUncaughtError` / `onCaughtError` / `onRecoverableError` on `createRoot` explicitly rather than trusting `window.reportError` → some global handler (and don't double-report what your error boundary already sends); `ref` is a plain prop, so `forwardRef` wrappers become plain functions taking `React.ComponentProps<typeof Primitive>` and spreading `ref` through with everything else; `inert` is typed as a boolean (the React 18 `{ inert: '' }` string spread goes); `useId` output format changed twice (check selectors keyed on it).
8. **Read what a "React 18 workaround" actually holds up before deleting it.** A comment said an inner scroll div existed to dodge a Motion/React-18 ref warning. The div was in fact keeping an absolutely-positioned backing from scrolling away with the content. The comment was stale; the structure was load-bearing. Rewrite the comment, keep the div.
9. **Defer the idioms.** Actions, `use()`, `useEffectEvent` sweeps, and the React Compiler (which reduces re-render cost and is irrelevant to compositor-driven animation) ride a later pass with their own gates.

## What NOT to do

- **Don't pin a daily canary in a shipped app for one component.** No patch line, no security backports, peer-override churn on every bump.
- **Don't bundle adjacent majors "while you're at it"** — bundler (Vite 8), TypeScript 6/7, an ORM's 2.x. None of them are required by the framework bump; each is its own project.
- **Don't trust the upgrade plan's dependency table after a few weeks.** Re-run the peer/changelog check on the day; the bump you didn't know you needed is the one that ships an infinite loop.
- **Don't let the codemod's diff hide behind line-ending noise.** Normalize first, review second.

Related: `resolve-versions-from-the-registry-not-a-search-index.md`, `monorepo-stale-dist-zod-strip.md`, `exit-animation-props-captured-at-unmount.md` (the ref-warning workaround this upgrade retired).
