#!/usr/bin/env python3
"""
Secret scanner — the guard that .gitignore alone cannot provide.

Why this exists (found 2026-09-07 while porting the protocol to an older
project): an Android keystore password file and a worker's bypass token sat
untracked-but-unignored, one `git add .` away from being published. Nothing
had leaked, but nothing was stopping it either. .gitignore is a blocklist —
it only protects paths somebody remembered to list — and the files it missed
were exactly the risky ones. This script inspects CONTENT, so a file nobody
thought to ignore is still caught before it is committed.

Two modes:

    python .claude/scripts/scan-secrets.py
        Scans what is heading for a commit: staged + modified + untracked
        files that git does not already ignore. Run by /end Step 0c when
        `.claude/protocol.json` → `secret_scan` is true (the default).

    python .claude/scripts/scan-secrets.py --history
        Scans every object REACHABLE from any ref — everything that has been
        or could be pushed. Unreachable objects (orphaned by amend/rebase)
        are deliberately excluded: they are local-only and never travel on a
        push, so flagging them produces alarm without exposure.

Exit codes:
    0  clean
    1  findings (so /end can stop before committing)
    0  on any internal error — this must never wedge a session

Nested repos are NOT scanned (git does not see into them). If the project
contains a sub-repository, run the scanner inside it separately.
"""

from __future__ import annotations

import re
import subprocess
import sys

# Each rule is (name, pattern, value_group). Patterns target credential SHAPES
# that are hard to produce by accident, rather than the word "secret" near an
# assignment — the latter drowns real findings in noise.
#
# value_group is the capture group holding the assigned VALUE, or None when the
# whole match is the credential. Shape alone is not enough for assignment
# rules: `BYPASS_TOKEN: string;` (a type) and `API_KEY: 'settings_api_key'`
# (a storage key NAME) both match the shape while containing no secret.
RULES = [
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_\-]{35}"), None),
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), None),
    ("OpenAI API key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{32,}"), None),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"), None),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}"), None),
    ("Slack token", re.compile(r"xox[abprs]-[A-Za-z0-9\-]{10,}"), None),
    ("Stripe key", re.compile(r"(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{20,}"), None),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY"), None),
    ("Keystore password", re.compile(r"\"key(?:store)?Password\"\s*:\s*\"([^\"]{4,})\""), 1),
    ("Bypass/shared token",
     re.compile(r"(?i)\b(?:\w*bypass_token|shared_secret|webhook_secret|session_secret)\s*[:=]\s*[\"']?([^\s\"',;]{6,})"), 1),
    ("Generic API key assignment",
     re.compile(r"(?i)\b(?:api[_-]?key|apikey|secret[_-]?key|auth[_-]?token|access[_-]?token)\s*[:=]\s*[\"']?([A-Za-z0-9_\-]{20,})"), 1),
    ("Database URL with password",
     re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^:\s/]+:([^@\s]{4,})@"), 1),
]

# A matched VALUE that is really a type, a code reference, or another
# credential's NAME — never the credential itself.
NOT_A_VALUE = re.compile(
    r"(?i)^(?:string|number|boolean|null|undefined|any|unknown|object|symbol|bigint)\b|"
    r"^(?:env|process|import|Constants|BuildConfig|System|config|opts|options|this|self)\.|"
    r"(?:api[_-]?key|apikey|token|secret|password|passwd)"
)

# Values that LOOK like credentials but are template text — keeps .env.example green.
PLACEHOLDER = re.compile(
    r"(?i)your[_-]?\w*[_-]?(?:key|token|secret|password)|"
    r"xxx+|<[^>]+>|\$\{[^}]+\}|replace[_-]?me|changeme|example|placeholder|"
    r"dummy|sample|todo|fake|redacted|\.\.\."
)

# Binary and vendored paths never hold hand-written credentials but produce
# random high-entropy runs that trip the shape rules.
SKIP_PATH = re.compile(
    r"(?:^|/)(?:node_modules|\.git|build|dist|target|\.gradle|__pycache__|\.next)/|"
    r"\.(?:png|jpg|jpeg|gif|webp|ico|pdf|zip|7z|jar|aab|apk|keystore|jks|p12|so|dex|dll|exe|"
    r"ttf|otf|woff2?|mp4|webm|mp3|wav|bin|wasm)$|"
    r"(?:^|/)(?:package-lock\.json|pnpm-lock\.yaml|yarn\.lock|Cargo\.lock)$|"
    r"scan-secrets\.py$"
)

MAX_BYTES = 2_000_000


def run(cmd: list[str]) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return r.returncode, r.stdout
    except (subprocess.SubprocessError, OSError):
        return 1, ""


def candidate_files() -> list[str]:
    """Files heading for a commit: staged, modified, and untracked-not-ignored."""
    seen: list[str] = []
    for cmd in (
        ["git", "diff", "--name-only", "--cached"],
        ["git", "diff", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        rc, out = run(cmd)
        if rc == 0:
            for line in out.splitlines():
                path = line.strip()
                if path and path not in seen and not SKIP_PATH.search(path):
                    seen.append(path)
    return seen


def scan_text(text: str, label: str, findings: list[tuple[str, str, str]]) -> None:
    for name, pattern, value_group in RULES:
        for match in pattern.finditer(text):
            hit = match.group(0)
            value = match.group(value_group) if value_group else hit
            if PLACEHOLDER.search(value):
                continue
            if value_group and NOT_A_VALUE.search(value):
                continue
            shown = value[:12] + "..." if len(value) > 16 else value  # never the whole credential
            findings.append((label, name, shown))


def scan_working_tree() -> list[tuple[str, str, str]]:
    findings: list[tuple[str, str, str]] = []
    for path in candidate_files():
        try:
            with open(path, "rb") as f:
                raw = f.read(MAX_BYTES)
            if b"\x00" in raw[:8000]:
                continue  # binary
            scan_text(raw.decode("utf-8", errors="replace"), path, findings)
        except OSError:
            continue
    return findings


def scan_history() -> list[tuple[str, str, str]]:
    rc, out = run(["git", "rev-list", "--objects", "--all"])
    if rc != 0:
        return []
    oids = sorted({line.split()[0] for line in out.splitlines() if line.strip()})
    if not oids:
        return []
    try:
        proc = subprocess.run(
            ["git", "cat-file", "--batch"], input="\n".join(oids),
            capture_output=True, text=True, errors="replace", timeout=600,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    findings: list[tuple[str, str, str]] = []
    scan_text(proc.stdout, "<reachable git history>", findings)
    return findings


def main() -> None:
    history = "--history" in sys.argv
    try:
        findings = scan_history() if history else scan_working_tree()
    except Exception:  # noqa: BLE001 — never wedge a session
        sys.exit(0)
    scope = "reachable git history" if history else "files heading for a commit"
    if not findings:
        print(f"scan-secrets: clean ({scope})")
        sys.exit(0)
    unique = list(dict.fromkeys(findings))
    print(f"SECRETS DETECTED ({len(unique)}) in {scope}:")
    for label, name, shown in unique:
        print(f"  {label}: {name} -> {shown}")
    print()
    print("Do NOT commit. Move the value to an ignored file or a secret store,")
    print("rotate it if it was ever pushed, then re-run this scan.")
    sys.exit(1)


if __name__ == "__main__":
    main()
