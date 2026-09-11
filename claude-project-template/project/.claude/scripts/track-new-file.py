#!/usr/bin/env python3
"""
PostToolUse hook for the Write and Edit tools.

When Claude touches a file that is NOT yet listed in docs/CODEBASE_INDEX.md,
this script appends the project-relative path to
.claude/pending-index-updates.txt. /end refuses to complete until every
entry there has a description in the index.

The "not yet in the index" check is what makes matching Edit safe:
PostToolUse fires after the file exists on disk, so existence cannot be the
new-file signal. The index is the source of truth — a path absent from it
needs an entry whether it was just created or merely edited.

Skip lists: protocol bookkeeping files (by basename) and build/generated
prefixes. Project-specific prefixes come from `.claude/protocol.json` →
`index_skip_prefixes`; never edit the list in this script.

Silent on every failure path.
"""

from __future__ import annotations

import json
import os
import pathlib
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


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    tool = data.get("tool_name", "")
    file_path = data.get("tool_input", {}).get("file_path", "")
    if tool not in ("Write", "Edit") or not file_path:
        sys.exit(0)

    rel = project_relative(file_path)
    if rel is None:
        sys.exit(0)  # outside the repo (memory files, other repos)
    if pathlib.PurePath(rel).name in SKIP_FILENAMES:
        sys.exit(0)

    cfg, _ = load_config()
    if any(rel == p.rstrip("/") or rel.startswith(p) for p in skip_prefixes(cfg)):
        sys.exit(0)

    proj = project_dir()
    try:
        index_path = pathlib.Path(proj) / "docs" / "CODEBASE_INDEX.md"
        if index_path.exists() and rel in index_path.read_text(encoding="utf-8"):
            sys.exit(0)
    except OSError:
        pass  # can't read the index → over-queue rather than under-queue

    try:
        pending = pathlib.Path(__file__).resolve().parent.parent / "pending-index-updates.txt"
        pending.parent.mkdir(parents=True, exist_ok=True)
        existing: set[str] = set()
        if pending.exists():
            existing = {ln.strip() for ln in pending.read_text(encoding="utf-8").splitlines() if ln.strip()}
        if rel not in existing:
            # newline="\n": in text mode Windows would write CRLF, and every
            # shell loop reading the queue would then see "path\r".
            with open(pending, "a", encoding="utf-8", newline="\n") as f:
                f.write(rel + "\n")
    except OSError:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
