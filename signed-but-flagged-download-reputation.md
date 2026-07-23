---
stack: [windows, code-signing, azure-trusted-signing, smartscreen, chrome, distribution]
kind: gotcha
last_verified: 2026-07-23
---

# Your correctly-signed installer still says "may be dangerous" — it's reputation, not signature, and one tier has no appeal

## Symptom

You code-sign your Windows installer (e.g. Azure Trusted Signing), `signtool
verify /pa` passes clean, VirusTotal is 0/N. Yet:

- Chrome's download bar says **"This file isn't commonly downloaded and it may
  be dangerous"** (Keep / Discard).
- Windows SmartScreen throws **"Windows protected your PC"** on first run.

You start hunting for the signing bug that isn't there, or for an "appeal" form
that doesn't apply.

## Cause

Signing establishes IDENTITY, not TRUST. Both warnings are **reputation**
systems keyed on download volume + your signing identity + the file hash — and a
new publisher / new file has none yet:

- **Chrome's "not commonly downloaded"** is a SOFT Safe Browsing tier: literally
  "few people have downloaded this exact file." It is NOT a malware verdict (the
  "Download suspicious file" option is still offered). It clears with volume.
- **SmartScreen** reputation is per-file-hash AND influenced by the issuing CA's
  accumulated trust.

Two 2026-specific traps compound it for Azure Trusted Signing users:

- **The EV escape hatch is gone.** EV code-signing certs used to grant INSTANT
  SmartScreen reputation. Microsoft stopped issuing new EV code-signing certs in
  favor of Trusted Signing, which does NOT confer instant reputation.
- **A CA migration reset reputation.** Around late March 2026, Azure Trusted
  Signing silently moved signing to new intermediate CAs (Microsoft ID Verified
  CS AOC CA 03 / EOC CA 03–04) WITHOUT carrying SmartScreen reputation over, so
  correctly-signed builds began re-tripping SmartScreen. Widespread, Microsoft's
  side, self-heals as the new CA accrues. Check your chain with `signtool verify
  /pa /v` — an `AOC CA 0x` intermediate means you're in the affected cohort.

## Fix

There is no switch. The levers, honestly ranked:

1. **Do nothing structural; accrue reputation.** Volume under a STABLE signing
   identity + stable download URL. Reputation attaches to the publisher, so each
   new build sheds the warning faster over time. Churning the cert/identity
   resets the clock.
2. **Identify which warning you have — only one is appealable.** The Chrome SOFT
   "not commonly downloaded" notice has NO appeal path. `safebrowsing.google.com/
   safebrowsing/report_error/` is for contesting a FALSE _dangerous_/malware
   verdict or a "deceptive site" block — submitting a merely-unknown file there
   does nothing. Don't waste time on it.
3. **Publish reassurance, not a fix.** A VirusTotal permalink (0/N) does NOT
   clear Chrome's notice (Chrome doesn't read VT), but it's a public,
   no-login-needed artifact to link on your download page so testers read the
   warning as newness, not malware. Pair with "signed by <publisher>" + the
   SHA-256.

## Notes

- Dead-end value: the hours people lose here go to (a) re-verifying a signature
  that's fine and (b) hunting a Chrome appeal that doesn't exist for the soft
  tier. Recognize the tier FIRST — soft notice (no appeal, wait for volume) vs.
  hard "dangerous" block (a real false positive worth reporting).
- The VT permalink and SHA-256 are PER-BUILD. A versionless "latest" download
  URL changes hash every release, so a hardcoded VT link on your site points at
  an old version's scan after the next release — re-scan + update it each
  release, or state the general "signed + scanned each build" claim and let the
  link be clearly version-tagged.
- Related: [[azure-cli-windows-auth-traps]] (the `az` login side of a Trusted
  Signing pipeline), [[tauri-desktop-security-hardening]].
- Verified 2026-07-23 against a Trusted-Signing `AOC CA 04` chain: `signtool
  verify /pa` clean, VirusTotal 0/63 on the signed MSI, Chrome still showed the
  soft notice (expected — reputation, not signature).
