#!/usr/bin/env python3
"""
PostToolUse hook for the Write and Edit tools.

When Claude touches a file that is NOT yet listed in
docs/CODEBASE_INDEX.md, this script appends the file path to
.claude/pending-index-updates.txt. The session-end protocol reads that
file and refuses to complete until each entry has a corresponding
description in docs/CODEBASE_INDEX.md.

The "not yet in the index" check is what lets us safely match both
Write and Edit. PostToolUse fires after the file already exists on
disk, so we cannot use existence as the new-file signal. The index
itself is the source of truth: if a path is absent from
CODEBASE_INDEX.md, the index is stale and the path needs an entry —
regardless of whether it was just created or merely edited.

This replaces discipline-based codebase index updates with automated
enforcement. Past projects had indexes go silently out-of-date because
end-session steps got skipped. Hooks fix that.

The script is silent on every failure path — it never blocks Claude's
work, even if the JSON is malformed or the filesystem is unavailable.
"""

import json
import os
import pathlib
import sys


# Filenames we never want to track because they ARE the protocol's bookkeeping.
# Tracking them would create infinite loops (write to index → triggers hook
# → adds index to pending list → next /end fails).
SKIP_FILENAMES = (
    "pending-index-updates.txt",
    "CODEBASE_INDEX.md",
    "CURRENT_STATE.md",
    "HANDOFF_LOG.md",
)

# Project-relative path prefixes (POSIX form) that we always skip — these are
# protocol/build/generated paths that should not appear in CODEBASE_INDEX.
# IMPORTANT: this list is matched against paths RELATIVE TO $CLAUDE_PROJECT_DIR,
# not absolute paths, because the project itself may live inside a directory
# named ".claude/" (e.g. when working in a worktree at .claude/worktrees/<name>/).
# A naive substring check on the absolute path would skip every file in such a
# project. Always normalize first, then check.
SKIP_PREFIXES = (
    ".claude/",
    "node_modules/",
    "dist/",
    "build/",
    "target/",
    ".next/",
)


def project_relative(file_path: str) -> str | None:
    """Return file_path relative to $CLAUDE_PROJECT_DIR, in POSIX form.

    Returns None if the path cannot be resolved relative to the project — i.e.
    the file lives outside the project tree (e.g. global memory files under
    ~/.claude/projects/...) or $CLAUDE_PROJECT_DIR is unset. Callers MUST treat
    None as "skip this file" — the codebase index only documents files that
    actually live in the project.
    """
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return None
    try:
        abs_path = pathlib.Path(file_path).resolve()
        project_root = pathlib.Path(project_dir).resolve()
        rel = abs_path.relative_to(project_root)
        return rel.as_posix()
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

    rel_posix = project_relative(file_path)

    # Skip files outside the project tree entirely. The codebase index only
    # documents files that live in this repo, so files under ~/.claude/projects/
    # (global memory), other repos, or system paths must never be tracked.
    if rel_posix is None:
        sys.exit(0)

    # Skip protocol bookkeeping by basename (works regardless of project layout).
    if pathlib.PurePath(rel_posix).name in SKIP_FILENAMES:
        sys.exit(0)

    # Skip build outputs and the project's own .claude/ directory by relative
    # prefix. We must check the relative form so that ancestor directories
    # named ".claude/" (e.g. a worktree path) do not cause false positives.
    if any(rel_posix == p.rstrip("/") or rel_posix.startswith(p) for p in SKIP_PREFIXES):
        sys.exit(0)

    # Skip if the path is already documented in CODEBASE_INDEX.md. This is the
    # mechanism that makes Edit-matching safe: existing files don't get
    # re-queued on every edit, only genuinely undocumented files do.
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    try:
        index_path = pathlib.Path(project_dir) / "docs" / "CODEBASE_INDEX.md"
        if index_path.exists():
            index_text = index_path.read_text(encoding="utf-8")
            if rel_posix in index_text:
                sys.exit(0)
    except OSError:
        # If we can't read the index, fall through and queue the path —
        # /end will sort it out. Better to over-queue than under-queue.
        pass

    try:
        script_dir = pathlib.Path(__file__).resolve().parent
        pending = script_dir.parent / "pending-index-updates.txt"
        pending.parent.mkdir(parents=True, exist_ok=True)
        # Avoid duplicate lines if the same undocumented file is touched twice
        # in one session.
        existing = set()
        if pending.exists():
            existing = {line.strip() for line in pending.read_text(encoding="utf-8").splitlines() if line.strip()}
        if rel_posix not in existing:
            with open(pending, "a", encoding="utf-8") as f:
                # Write the project-relative POSIX path. Cleaner index entries
                # and works identically across Windows/macOS/Linux contributors.
                f.write(rel_posix + "\n")
    except OSError:
        # Never block Claude on filesystem errors.
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
