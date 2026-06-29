---
stack: [git, security]
kind: howto
last_verified: 2026-06-29
---

# Purge a leaked secret from git history

**When:** you committed something you shouldn't have — an API key, `.env`, private key, a DB dump with tokens/PII — and it's now in git history (possibly already pushed).

## The two-part truth

1. **Removing it from history is necessary but NOT sufficient.** Once a secret has been pushed — especially to a public/shared remote, or anywhere indexed/cached/forked — treat it as compromised and **rotate/revoke the credential.** That's the real fix; history rewriting only stops *future* exposure of the same blob.
2. **The remote is your backup until you force-push.** Do the rewrite locally, verify, THEN force-push. If anything looks wrong, re-fetch from origin (still has the old history) before pushing. The force-push is the only point of no return.

## Recipe (`git-filter-repo` — the modern tool, not `filter-branch`)

`git-filter-repo` is a single Python script, not bundled with git:
```bash
pip install git-filter-repo            # or: brew install git-filter-repo
# if the `git filter-repo` subcommand isn't on PATH, call the module directly:
python -m git_filter_repo --version
```

Investigate first:
```bash
git ls-files <path>                    # is it currently tracked?
git log --oneline --all -- <path>      # which commits touched it
git remote -v                          # is it pushed anywhere?
```

Working tree must be clean (or pass `--force`). Remove the file from ALL history:
```bash
python -m git_filter_repo --path "<path/to/secret>" --invert-paths --force
```
- `--invert-paths` = remove the named path, keep everything else.
- Rewrites every commit that contained it → **all commit SHAs from that point change.**

filter-repo **removes the `origin` remote** on purpose (so you don't push to the wrong place by reflex). Re-add it:
```bash
git remote add origin <url>
```

Verify, then force-push:
```bash
git log --all --oneline -- "<path>"          # empty = purged from history
ls "<path>"                                   # filter-repo also drops it from the worktree
git push --force-with-lease origin main       # --force-with-lease beats --force (won't clobber unexpected remote changes)
# the remote re-add can reset branch tracking:
git push origin main && git branch --set-upstream-to=origin/main main
```

## Prevent the repeat

- Add a `.gitignore` rule — but **scope it** so you don't ignore legit files. (Don't `*.sql`-ignore your migrations; use `backup-*.sql` / `*.dump` for the dumps.)
- Secrets belong in env / a secrets manager (Fly secrets, Doppler, 1Password), never in committed files. Keep a `.env.example` with placeholders only.

## Notes

- **Solo repo:** force-push is safe. **Shared repo:** coordinate — everyone else must re-clone (their history is now divergent).
- **GitHub caches commits by SHA** for a while after a force-push, and forks keep their own copies → another reason rotation, not just purging, is the real mitigation.
- filter-repo expires reflogs + gc's, so local recovery after the rewrite is hard *by design*. The remote (pre-push) is your safety net.

---
*Captured from the Playmoir pre-paywall security pass, 2026-06-29 (purged a DB dump carrying expired Google OAuth tokens + PII from 539 commits).*
