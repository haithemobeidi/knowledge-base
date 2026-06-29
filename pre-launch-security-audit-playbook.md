---
stack: [security]
kind: playbook
last_verified: 2026-06-29
---

# Pre-launch security-audit playbook

A repeatable way to security-review an app before it takes payments / ships to real users. Used as the "pre-paywall" pass on Playmoir; generalizes to any client + backend app.

## Shape: fan out read-only auditors by DOMAIN, then synthesize
Spawn independent read-only reviewers, one per trust-boundary domain, then merge into one triaged report. Independent passes that co-flag the same issue = confirmation. Typical domains for a desktop/web client + backend:

1. **Backend auth & authorization** — is identity verified correctly (OAuth/OpenID round-trips, JWT alg pinning, expiry, nonce/replay)? **IDOR**: is the user id taken from the verified token, or a client-supplied param/body? Enumerate every route and whether it enforces auth. Token leakage (logs, URLs, error bodies). Revocation story.
2. **Backend data & input** — SQL injection (parameterized vs string-built; allowlist interpolated identifiers), validate **every boundary** (schema-validate request bodies — names AND values, with length caps), upload abuse (size/type/path-traversal/quota), rate-limit effectiveness (per-user vs global, survives restart/scale?), CORS (wildcard + credentials?), SSRF in outbound calls, error messages leaking internals.
3. **Client trust boundary** (desktop/mobile) — capability/permission over-grant, path traversal in native commands, command injection / shell-out with untrusted args, deep-link / OAuth-callback hijack, secrets stored plaintext on disk, and **client-side enforcement of things that must be server-side** (e.g. paid-tier gating that a user can flip in localStorage).
4. **Frontend + repo-wide secret scan** — XSS sinks over untrusted/synced content, tokens in insecure storage, hardcoded endpoints/keys, and a full git-history + tree scan for committed credentials.

## Auditor prompt rules (signal, not noise)
- Read-only; report findings ONLY.
- Each finding: **severity / one-line title / file:line / concrete exploit-or-impact / one-line fix.**
- Grounded, not theoretical — no "could be faster" hand-waving; require a file:line. Mark unconfirmed suspicions `NEEDS-VERIFY`.
- Include a **"Verified OK"** section so you know what was checked and is sound — prevents re-auditing, and surfaces the load-bearing defenses.
- Calibrate severity to the real threat model (a local user controls their own machine; the real risk is untrusted *data* crossing into code/path/SQL).

## Triage + remediate
- Merge findings, dedupe overlaps, rank by **real-world exploitability**, not theoretical severity.
- Batch fixes by area (server / auth / client / secrets), each its own **tested commit** — not one giant blind diff.
- **Defer deliberately, not silently.** Items that pair with future work (e.g. session revocation belongs with the entitlement system; storage quotas with paid tiers) get filed with rationale, not crammed in early.

## Lessons that recur
- **"No CRITICALs" ≠ "done."** A mature codebase's findings are usually *hardening* (least-privilege, defense-in-depth), not "built wrong." That's the expected, good outcome — don't manufacture severity.
- **The audit's blind spot is INFRA CONFIG.** Code audits don't see cloud-provider defaults: an auto-on public API (e.g. Supabase PostgREST + anon key), RLS posture, bucket policies, DB TLS verification. Add an explicit infra-config pass — that's where the real "default-open door" usually hides.
- **Verify the load-bearing assumption explicitly.** e.g. "is any untrusted string rendered as raw HTML?" is the lynchpin that makes several lower findings live or dormant. Confirm it; don't assume.
- **Reproducibility of the fix matters.** If a fix is applied as ad-hoc dashboard SQL or a one-off secret, codify it (migration file, documented secret) so a rebuild re-applies it — otherwise the hardening silently rots.

---
*Captured from the Playmoir pre-paywall security pass, 2026-06-29 (4-domain fan-out, no CRITICALs, 4 remediation batches, deployed + validated).*
