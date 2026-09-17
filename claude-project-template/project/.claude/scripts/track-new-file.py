#!/usr/bin/env python3
"""
PostToolUse hook for the Write, Edit and shell tools (Bash, PowerShell).

When Claude touches a file that is NOT yet listed in docs/CODEBASE_INDEX.md,
this script appends the project-relative path to
.claude/pending-index-updates.txt. /end refuses to complete until every
entry there has a description in the index.

The "not yet in the index" check is what makes matching Edit safe:
PostToolUse fires after the file exists on disk, so existence cannot be the
new-file signal. The index is the source of truth — a path absent from it
needs an entry whether it was just created or merely edited.

SHELL TOOLS (Bash, PowerShell): a file created by a script, a generator, a
heredoc or a `git mv` never passes through Write/Edit, so the Write/Edit
matcher alone is blind to it — a session that wrote 24 Kotlin files through
Python scripts queued nothing (Playmoir, 2026-09-16; the /end diff backstop
caught them). After every shell call this hook lists the repo's UNTRACKED
files (`git ls-files --others --exclude-standard`, ~50 ms) and queues the
unindexed ones under the same skip rules. Tracked-but-unindexed files a
script edits are still /end's backstop (Step 1b diffs HEAD).

Skip lists: protocol bookkeeping files (by basename) and build/generated
prefixes. Project-specific prefixes come from `.claude/protocol.json` →
`index_skip_prefixes`; never edit the list in this script.

Silent on every failure path.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import load_config, project_dir, skip_prefixes  # noqa: E402

SKIP_FILENAMES = (
    "pending-index-updates.txt",
    "CODEBASE_INDEX.md",
    "CURRENT_STATE.md",
    "HANDOFF_LOG.md",
    "SESSION_LEDGER.md",
)


def project_relative(file_path: str) -> str | None:
    """POSIX path relative to $CLAUDE_PROJECT_DIR, or None if outside it."""
    proj = project_dir()
    if not proj:
        return None
    try:
        return pathlib.Path(file_path).resolve().relative_to(pathlib.Path(proj).resolve()).as_posix()
    except (OSError, ValueError):
        return None


SHELL_TOOLS = ("Bash", "PowerShell")


def untracked_files(proj: str) -> list[str]:
    """Repo-relative POSIX paths git does not track and does not ignore."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=proj, capture_output=True, text=True, timeout=10, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def wants_entry(rel: str, cfg, index_text: str | None) -> bool:
    """The one rule every path goes through: not bookkeeping, not a skip
    prefix, not already in the index."""
    if pathlib.PurePath(rel).name in SKIP_FILENAMES:
        return False
    if any(rel == p.rstrip("/") or rel.startswith(p) for p in skip_prefixes(cfg)):
        return False
    # can't read the index → over-queue rather than under-queue
    return index_text is None or rel not in index_text


def queue(paths: list[str]) -> None:
    try:
        pending = pathlib.Path(__file__).resolve().parent.parent / "pending-index-updates.txt"
        pending.parent.mkdir(parents=True, exist_ok=True)
        existing: set[str] = set()
        if pending.exists():
            existing = {ln.strip() for ln in pending.read_text(encoding="utf-8").splitlines() if ln.strip()}
        fresh = [p for p in paths if p not in existing]
        if fresh:
            # newline="\n": in text mode Windows would write CRLF, and every
            # shell loop reading the queue would then see "path\r".
            with open(pending, "a", encoding="utf-8", newline="\n") as f:
                f.write("".join(p + "\n" for p in fresh))
    except OSError:
        pass


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    tool = data.get("tool_name", "")
    proj = project_dir()
    if not proj:
        sys.exit(0)

    if tool in ("Write", "Edit"):
        file_path = data.get("tool_input", {}).get("file_path", "")
        if not file_path:
            sys.exit(0)
        rel = project_relative(file_path)
        if rel is None:
            sys.exit(0)  # outside the repo (memory files, other repos)
        candidates = [rel]
    elif tool in SHELL_TOOLS:
        candidates = untracked_files(proj)
        if not candidates:
            sys.exit(0)
    else:
        sys.exit(0)

    cfg, _ = load_config()
    index_text: str | None = None
    try:
        index_path = pathlib.Path(proj) / "docs" / "CODEBASE_INDEX.md"
        if index_path.exists():
            index_text = index_path.read_text(encoding="utf-8")
    except OSError:
        index_text = None

    queue([rel for rel in candidates if wants_entry(rel, cfg, index_text)])
    sys.exit(0)


if __name__ == "__main__":
    main()
