#!/usr/bin/env python3
"""
/end Step 0d — the mechanical half of the file-size and DRY rule.

Scope: the files THIS session touched — every path changed in the commits
since the last wrap (the last commit that touched docs/HANDOFF_LOG.md; a
wrap always writes it, a pause-point commit never does), plus the working
tree (staged, unstaged, untracked). Not the whole repo: a session answers
for what it touched, the repo-wide audit is its own sitting.

Checks, on code files only (`file_caps.extensions`):
  - over the SOFT cap (default 500 lines)  → flagged; /end writes a ledger
    line per file (the wrap records, the split happens at a quiet point —
    never during /end);
  - over the HARD cap (default 800)        → exit 1; /end STOPS until the file
    is split or the user overrides explicitly;
  - a NEW file whose basename already exists elsewhere in the repo (a cheap
    DRY smell: a second `Format.kt`, a second `helpers.ts`) → flagged, with
    the twin named. Common structural names (index.ts, mod.rs, README.md…)
    are exempt.

Config lives in `.claude/protocol.json` → `file_caps` (soft, hard,
extensions, skip_prefixes); `index_skip_prefixes` and the built-in
generated/vendored prefixes are skipped too. Never edit this script per
project. Silent on git failures (exit 0) — a check that cannot run must not
block a wrap by accident; it says so instead.

Usage:
    python .claude/scripts/check-file-caps.py            # report, exit 1 on a hard breach
    python .claude/scripts/check-file-caps.py --all      # the whole repo (the audit sitting)
    python .claude/scripts/check-file-caps.py --since <commit>   # a feature's range (the feature-close pass)
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import load_config, project_dir, skip_prefixes  # noqa: E402

# Windows consoles default to a legacy code page (cp1252 here), and every
# document this toolchain prints is full of arrows, em dashes and smart
# quotes. Without this the script dies with UnicodeEncodeError mid-report, or
# silently mangles characters — both seen live on 2026-09-22, which is what
# prompted this. stdout may be a pipe with no reconfigure(), hence the guard.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


# Names that legitimately repeat across a tree; never a DRY signal.
EXEMPT_BASENAMES = {
    "index.ts", "index.tsx", "index.js", "index.mjs", "index.html", "index.md",
    "mod.rs", "main.rs", "lib.rs", "build.rs", "main.py", "__init__.py",
    "README.md", "CHANGELOG.md", "LICENSE", "package.json", "tsconfig.json",
    "build.gradle.kts", "settings.gradle.kts", "proguard-rules.pro", "AndroidManifest.xml",
    "styles.css", "types.ts", "schema.ts", "constants.ts", "test_contract.py",
}


def git(proj: str, *args: str) -> list[str]:
    try:
        out = subprocess.run(
            ["git", *args], cwd=proj, capture_output=True, text=True, timeout=20, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def touched_since_last_wrap(proj: str, since: str | None = None) -> tuple[set[str], set[str]]:
    """(all touched paths, paths new since the wrap). [since] overrides the
    base commit — a feature's starting point for the feature-close pass.
    Falls back to the working tree alone when no wrap commit exists yet."""
    base = [since] if since else git(proj, "log", "-n", "1", "--format=%H", "--", "docs/HANDOFF_LOG.md")
    touched: set[str] = set()
    new: set[str] = set()
    if base:
        touched.update(git(proj, "diff", "--name-only", f"{base[0]}..HEAD"))
        for ln in git(proj, "diff", "--name-status", "--diff-filter=A", f"{base[0]}..HEAD"):
            parts = ln.split("\t")
            if len(parts) >= 2:
                new.add(parts[-1])
    touched.update(git(proj, "diff", "--name-only", "HEAD"))
    untracked = git(proj, "ls-files", "--others", "--exclude-standard")
    touched.update(untracked)
    new.update(untracked)
    return touched, new


def main() -> None:
    proj = project_dir() or os.getcwd()
    if not (pathlib.Path(proj) / ".git").exists():
        print("check-file-caps: not a git checkout, skipped")
        sys.exit(0)
    cfg, _ = load_config(proj)
    caps = cfg.get("file_caps") or {}
    soft = int(caps.get("soft", 500))
    hard = int(caps.get("hard", 800))
    exts = {e if e.startswith(".") else "." + e for e in caps.get("extensions") or []}
    skips = list(skip_prefixes(cfg)) + [
        p if p.endswith("/") else p + "/" for p in (caps.get("skip_prefixes") or [])
    ]

    if "--all" in sys.argv:
        touched = set(git(proj, "ls-files"))
        new: set[str] = set()
    else:
        since = sys.argv[sys.argv.index("--since") + 1] if "--since" in sys.argv else None
        touched, new = touched_since_last_wrap(proj, since)

    def skipped(rel: str) -> bool:
        return any(rel == p.rstrip("/") or rel.startswith(p) for p in skips)

    code = sorted(
        rel for rel in touched
        if pathlib.PurePosixPath(rel).suffix in exts and not skipped(rel)
        and (pathlib.Path(proj) / rel).is_file()
    )

    over_soft: list[tuple[str, int]] = []
    over_hard: list[tuple[str, int]] = []
    for rel in code:
        try:
            with open(pathlib.Path(proj) / rel, "rb") as f:
                n = sum(1 for _ in f)
        except OSError:
            continue
        if n > hard:
            over_hard.append((rel, n))
        elif n > soft:
            over_soft.append((rel, n))

    # Same-basename twins for NEW files.
    twins: list[tuple[str, str]] = []
    if new:
        by_name: dict[str, list[str]] = {}
        for rel in git(proj, "ls-files"):
            if skipped(rel):
                continue
            by_name.setdefault(pathlib.PurePosixPath(rel).name, []).append(rel)
        for rel in sorted(new):
            name = pathlib.PurePosixPath(rel).name
            if name in EXEMPT_BASENAMES or pathlib.PurePosixPath(rel).suffix not in exts or skipped(rel):
                continue
            for other in by_name.get(name, []):
                if other != rel:
                    twins.append((rel, other))

    if not (over_soft or over_hard or twins):
        print(f"check-file-caps: clean ({len(code)} code file(s) in scope)")
        sys.exit(0)
    for rel, n in over_hard:
        print(f"HARD  {n:5d} > {hard}  {rel}")
    for rel, n in over_soft:
        print(f"soft  {n:5d} > {soft}  {rel}")
    for rel, other in twins:
        print(f"twin  new {rel}  shares its name with  {other}")
    if over_hard:
        print("check-file-caps: a file is over the HARD cap — split it (a coherent concept, never shaved lines) or get an explicit override before the wrap continues.")
        sys.exit(1)
    print("check-file-caps: soft breaches and twins go on the ledger (one line per file, with the split candidate named); the split itself waits for a quiet point.")
    sys.exit(0)


if __name__ == "__main__":
    main()
