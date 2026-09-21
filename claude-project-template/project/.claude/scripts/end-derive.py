#!/usr/bin/env python3
"""
/end Step 2/3 helper — the facts git can prove, so the wrap does not recall them.

Aider's repo map is the only surveyed agent context that cannot go stale, and
the reason is that it is COMPUTED rather than maintained. Everything derivable
here is a line that cannot drift: what changed, which tracks it touched, how
many commits, since when. The wrap writes the judgement (what it means, what is
next, what to do if it fails) and stops retyping the facts.

It deliberately does NOT derive build status. That comes from `check_command`
at Step 0c, which has already run by the time this is useful — re-running it
would double a slow build, and inferring "green" from a clean tree would be
exactly the unearned confidence this protocol keeps finding. It prints what it
knows and leaves the verdict blank for a human.

Scope is the same window as check-file-caps.py: commits since the last wrap
(the last commit touching docs/HANDOFF_LOG.md) plus the working tree.

Usage:
    python .claude/scripts/end-derive.py
    python .claude/scripts/end-derive.py --since <commit>
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import load_config, multi_track, project_dir, track_of_path  # noqa: E402


def git(proj: str, *args: str) -> list[str]:
    try:
        out = subprocess.run(["git", *args], cwd=proj, capture_output=True,
                             text=True, timeout=20, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [ln.rstrip() for ln in out.splitlines() if ln.strip()]


def main() -> None:
    proj = project_dir() or str(pathlib.Path(__file__).resolve().parent.parent.parent)
    cfg, _ = load_config(proj)

    since = sys.argv[sys.argv.index("--since") + 1] if "--since" in sys.argv else None
    if not since:
        base = git(proj, "log", "-n", "1", "--format=%H", "--", "docs/HANDOFF_LOG.md")
        since = base[0] if base else ""

    if since:
        commits = git(proj, "log", "--format=%h %s", f"{since}..HEAD")
        changed = set(git(proj, "diff", "--name-only", f"{since}..HEAD"))
        span = git(proj, "log", "-1", "--format=%cI", since)
    else:
        commits, changed, span = [], set(), []
    changed |= set(git(proj, "diff", "--name-only", "HEAD"))
    changed |= set(git(proj, "ls-files", "--others", "--exclude-standard"))

    print("DERIVED FOR THE WRAP — facts from git, not recall\n")
    print(f"Since the last wrap{' (' + span[0][:16] + ')' if span else ''}: "
          f"{len(commits)} commit(s), {len(changed)} file(s) touched")

    if commits:
        print("\nCommits:")
        for c in commits[:20]:
            print(f"  {c}")
        if len(commits) > 20:
            print(f"  … and {len(commits) - 20} more")

    if changed:
        groups: dict[str, list[str]] = {}
        for rel in sorted(changed):
            kind, owner = track_of_path(cfg, rel)
            key = owner if kind == "track" else ("shared" if kind == "shared" else "unowned")
            groups.setdefault(key, []).append(rel)
        print("\nFiles touched, by ownership:" if multi_track(cfg) else "\nFiles touched:")
        for key in sorted(groups):
            print(f"  {key} ({len(groups[key])}):")
            for rel in groups[key][:12]:
                print(f"      {rel}")
            if len(groups[key]) > 12:
                print(f"      … and {len(groups[key]) - 12} more")
        if multi_track(cfg) and any(k == "shared" for k in groups):
            print("\n  ⚠️  A shared path changed — that needs a ledger line tagged →all or →<other track>")
            print("      saying what changed and what the other side must do.")

    print("\nStatus: <from check_command at Step 0c — this script will not guess it>")
    print("Paste the above into the wrap as facts; write the judgement yourself.")


if __name__ == "__main__":
    main()
