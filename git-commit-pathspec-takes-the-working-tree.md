---
stack: [process, multi-agent, git]
kind: gotcha
last_verified: 2026-09-30
---

# `git commit -- <path>` commits the working tree, not your staging — a folder pathspec sweeps in a concurrent session's edits

**One-liner:** giving `git commit` paths switches it into `--only` mode, which ignores the index and records the *current working-tree content* of every tracked file the pathspec matches. "Stage exact files, never `git add -A`" doesn't protect you if the commit line then names a folder: any tracked file under it that another session has modified, staged or not, rides your commit.

## The near miss

Playmoir, 2026-09-30. Two sessions share one checkout on purpose (per-track rule set in `PROTOCOL.md`). A mock session staged its six new files by exact path, then committed with a directory pathspec for brevity:

```
git add docs/design/prototype/landing-motion.html docs/design/prototype/screens/landing-motion*.{css,js}
git commit -m "…" -- docs/design/prototype/landing-motion.html docs/design/prototype/screens/
```

`git show --stat HEAD` showed only the six files, so nothing leaked. It was clean only because no other session happened to have a modified tracked file under `screens/` at that moment. The staging discipline did nothing here; luck did.

## The mechanism (git's own docs, git 2.50)

`git-commit(1)`, `--only`: *"Make a commit by taking the updated working tree contents of the paths specified on the command line, disregarding any contents that have been staged for other paths. This is the default mode of operation of git commit if any paths are given on the command line."*

And in the description: listing files as arguments means *"the commit will ignore changes staged in the index, and instead record the current content of the listed files."*

So a pathspec on `commit` acts as a second, silent `git add` over everything it matches. A directory, a glob, or `.` matches files you never looked at.

## The fix

1. **Never give `git commit` a directory or glob in a shared checkout.** Stage exact files, then `git commit -m "…"` with *no* pathspec: the index is then the only source.
2. If you must use a pathspec (to commit a subset while other things are staged), list **exact files**, the same list you staged.
3. **Before pushing, run `git show --stat HEAD`** (or `git log --stat origin/main..HEAD`) and read the file list. It's the only check that sees what actually went in.

## Related

- [parallel-writers-minting-ids-collide.md](./parallel-writers-minting-ids-collide.md): the same one-checkout, two-sessions setting, colliding on ledger IDs instead of files.
- `claude-project-template/global/PROTOCOL.md` → Parallel tracks, rule 5 ("The tree is not yours alone").
