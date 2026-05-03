#!/usr/bin/env python3
"""
Stop hook: enforces /end Step 4a (clean-tree guarantee) as a fail-safe.

Fires whenever Claude finishes a turn. The hook is silent during normal
work — it only intervenes when this exact protocol violation pattern
is detected:

  1. The most recent commit subject starts with "Session:" AND was
     made within the last 5 minutes (i.e. /end just completed), AND
  2. `git status --porcelain` returns non-empty output (i.e. the tree
     is NOT actually clean).

When that pattern matches, /end Step 4a was skipped. The hook returns
decision=block with a reason that forces Claude to address the dirty
tree before stopping.

Outside that pattern (no recent Session commit, or tree is clean), the
hook exits 0 and Claude stops normally. This avoids the trap of
nagging on every turn-end.

The script is silent on every failure path. If git is unavailable or
the project dir isn't set, we exit 0 and let the stop proceed.
"""

import json
import os
import pathlib
import subprocess
import sys


def run(cmd: list[str], cwd: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=5
        )
        return result.returncode, result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return 1, ""


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # If the hook was already triggered once and Claude is now on a
    # follow-up turn, do not re-trigger — that would be a loop.
    if data.get("stop_hook_active"):
        sys.exit(0)

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir or not pathlib.Path(project_dir).is_dir():
        sys.exit(0)

    # Skip if not a git repo.
    rc, _ = run(["git", "rev-parse", "--git-dir"], project_dir)
    if rc != 0:
        sys.exit(0)

    # Most recent commit: subject + age in seconds.
    rc, commit_info = run(
        ["git", "log", "-1", "--format=%s|%ct"], project_dir
    )
    if rc != 0 or "|" not in commit_info:
        sys.exit(0)

    subject, _, ts_str = commit_info.partition("|")
    try:
        import time

        age_seconds = int(time.time()) - int(ts_str)
    except ValueError:
        sys.exit(0)

    is_recent_session_commit = (
        subject.startswith("Session:") and age_seconds <= 300
    )
    if not is_recent_session_commit:
        sys.exit(0)

    # /end just ran. Tree must be clean.
    rc, status = run(["git", "status", "--porcelain"], project_dir)
    if rc != 0 or not status:
        sys.exit(0)

    # Step 4a violation. Block the stop and tell Claude to address it.
    payload = {
        "decision": "block",
        "reason": (
            "PROTOCOL VIOLATION: /end Step 4a (clean-tree guarantee) was skipped. "
            "The most recent commit is a 'Session:' commit but `git status --porcelain` "
            "is non-empty. You must NOT stop here. Run `git status`, categorize each "
            "remaining entry per /end Step 4a (real in-scope work → second 'Session followup:' "
            "commit; out-of-scope → ask the user to commit/stash/discard), then push again. "
            "Only stop once the tree is clean."
        ),
    }
    sys.stdout.write(json.dumps(payload))
    sys.exit(0)


if __name__ == "__main__":
    main()
