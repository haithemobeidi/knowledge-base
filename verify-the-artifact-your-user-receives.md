---
stack: [release-engineering, distribution, cdn, cloudflare, r2, code-signing, virustotal]
kind: pattern
last_verified: 2026-08-08
---

# Verify the artifact your USER receives, not the one you built

**One-liner:** if you publish a "scanned clean, here's the hash" badge for a desktop download, you are making a claim about **the bytes a stranger gets from your site** — but every convenient way to check verifies *the bytes on your build machine* instead, and the two are separated by an upload, an object store, a CDN cache, and a versionless alias. The fix is not more checks; it is choosing the **one** comparison that collapses the whole chain: have a human download from the real link and scan *that*, then match its hash against your local artifact. One `md5` comparison then proves build = served = scanned, and the CDN verification you were dreading becomes free.

## The shape

Any signed desktop distribution ends up looking like this:

```
local build output          ->  Playmoir_1.3.0_x64_en-US.msi
uploaded to object store    ->  r2://releases/Playmoir_1.3.0_x64_en-US.msi
                            ->  r2://releases/Playmoir_x64_en-US.msi   (stable alias)
fronted by a CDN            ->  https://releases.example.com/...
linked from the site        ->  /download -> 302 -> the alias
scanned by a third party    ->  VirusTotal report for SOME file
published on the site       ->  "Signed & Verified Clean" -> links that report
```

The badge asserts a chain: **the file users download is the file that was scanned, and it is the file you built and signed.** Three links, each independently breakable:

1. **build -> served.** Upload silently failed, or the alias still holds the previous release because a CDN edge cached it. The stable alias is the dangerous one: *one URL whose CONTENT changes while its NAME does not*, which is precisely the shape caches get wrong.
2. **served -> scanned.** You scanned your local file; users get a different one.
3. **scanned -> published.** The hash in your HTML is not the hash of the report you think you linked.

## Why the obvious checks don't close it

- **Hashing your local build proves link 3 and nothing else.** It is the check everyone runs because it is the easy one.
- **`curl`-ing your own CDN to hash the served bytes is the right idea and is often blocked.** WAF bot management classifies on TLS/HTTP fingerprint as well as user-agent, so curl gets a challenge while browsers sail through. (See [bot-challenge-blocks-your-auto-updater.md](./bot-challenge-blocks-your-auto-updater.md) — same CDN behaviour, worse consequences.) You end up spoofing a Chrome UA and hoping the fingerprint passes, which works until it doesn't and gives you a confidently wrong answer either way.
- **Trusting the scanner's page to prove the file exists** fails for a subtler reason, worth its own lesson: see [negative-control-before-trusting-a-probe.md](./negative-control-before-trusting-a-probe.md).

## The move

**Ask the human to scan the file they downloaded from the real, public link** — not the artifact in `target/release/bundle/`. Then hash your local build and compare against the scan's own record of what it scanned.

Most scanners expose the scanned file's digest. VirusTotal's temporary result URL encodes it directly:

```bash
# the /gui/file-analysis/<base64> URL a fresh scan hands you
echo "YWRmNDIwNGQwY2UyMjRjNzhjNTk0OWYxYjJhNzFhYTM6MTc4NjE2MTQyOA==" | base64 -d
# -> adf4204d0ce224c78c5949f1b2a71aa3:1786161428
#    ^ md5 of the scanned file          ^ analysis timestamp

md5sum Playmoir_1.3.0_x64_en-US.msi
# -> adf4204d0ce224c78c5949f1b2a71aa3   MATCH
```

That single match proves **all three links at once**:

- the scanned file came through the site -> CDN -> alias path (they downloaded it),
- it is byte-identical to the local build (the md5 matched),
- so the sha256 you compute locally addresses the same object in the scanner's index.

**The post-upload alias verification you were going to fight the bot challenge for is now redundant by proof, not by omission.** That distinction matters: you are not skipping the check, you are getting it from a comparison you had to make anyway.

Measured contrast, same project, two releases apart: the previous release needed a scripted `curl` with a spoofed Chrome user-agent, run after a manual CDN purge, to hash the served alias. The next release got the identical guarantee from one `base64 -d` and one `md5sum`.

## The traps that survive this

**Publish the permanent URL, never the per-analysis one.** A fresh scan hands you a URL tied to *one analysis run* (`/gui/file-analysis/<base64>`), which rots. The durable form is keyed by content (`/gui/file/<sha256>`). A badge is a long-lived claim; point it at a long-lived resource.

**Order matters: scan, confirm, THEN deploy.** Deploying a green "verified clean" chip that links a report which does not exist yet is worse than having no chip.

**Your build directory is stale by default.** `dist/` holds the *previous* build's content-hashed assets. A bare `deploy dist` without a preceding build ships the old hash while every source-file grep reads green, because the source is correct — only the artifact is old. This is the same trap as [monorepo-stale-dist-zod-strip.md](./monorepo-stale-dist-zod-strip.md), one boundary further out: there it was a runtime importing a week-old build, here it is a CDN serving one. **Rule: the deploy command always begins with the build command.**

**A verification run seconds after deploy reads the previous deployment.** Propagation is not instant, and the failure looks alarming and structural — the live page referencing a bundle hash you have never seen reads as a routing or project-binding fault. Re-check after ~30s before diagnosing anything.

**Check every surface that carries the hash.** Badges multiply: a hero chip, a beta/testers page, a docs snippet. In the case this came from, the testers page silently lagged **two full releases** behind the homepage because only one of them was on the checklist. Grep for the *old* hash after updating; the correct post-condition is zero occurrences, not "I edited the file I remembered."

## When this doesn't apply

- **No human in the loop** (fully automated release). Then you do need the programmatic served-bytes check, and you need to solve the bot-challenge problem properly — an allowlist rule for your own verifier, or verifying from inside the origin rather than through the edge.
- **The scanner doesn't expose the digest of what it scanned.** Without that, the human's download proves nothing you can tie to your artifact.
- **Reproducible-build guarantees are the actual requirement** (supply-chain attestation, SLSA). This pattern proves *your* file reached the user; it does not prove the file was built from the source you think. Different problem, different tooling.

## The transferable core

The badge is a promise about the user's copy. Every cheap check available to you examines your copy. **Design the verification so the one artifact you can definitely obtain — the user's — is the one that gets measured**, and let the hash comparison carry everything else. Where you cannot obtain it, get a human to fetch it for you; that is not a workaround, it is the most direct evidence available.
