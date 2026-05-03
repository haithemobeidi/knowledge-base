#!/usr/bin/env python3
"""
SessionStart hook: replaces the manual `/start` typing.

Runs the worktree guard, then injects CURRENT_STATE.md + the last 5
HANDOFF_LOG.md lines into the first turn so Claude can give the 3-line
status report without the user typing /start.

If the worktree guard trips (cwd inside .claude/worktrees/ OR branch
starts with claude/), the hook injects the verbatim warning from
.claude/commands/start.md and tells Claude not to proceed with any
work until the user resolves it.

Output protocol: print a JSON object to stdout with the shape
  {"hookSpecificOutput": {"hookEventName": "SessionStart",
                          "additionalContext": "<text to inject>"}}
The text shows up as system context at the top of the first turn.

The script is silent on every failure path — if anything goes wrong
we exit 0 with no output rather than blocking session start.
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


def emit(text: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.exit(0)


def main() -> None:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir or not pathlib.Path(project_dir).is_dir():
        sys.exit(0)

    # Worktree guard. We mirror Step 0 of /start so the user gets the
    # same verbatim warning whether they typed /start or not.
    cwd_norm = project_dir.replace("\\", "/")
    in_worktree = ".claude/worktrees/" in cwd_norm

    rc, branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], project_dir)
    on_claude_branch = rc == 0 and branch.startswith("claude/")

    if in_worktree or on_claude_branch:
        emit(
            "⚠️ **Worktree guard tripped at session start.** "
            f"cwd `{project_dir}` on branch `{branch or '(unknown)'}` violates the workflow. "
            "Tell the user verbatim from `.claude/commands/start.md` Step 0 and DO NOT proceed "
            "with reading state, editing files, or running other commands until they resolve it."
        )

    # Happy path: read state docs and inject them.
    parts: list[str] = ["## Auto-loaded session context (SessionStart hook)\n"]

    state_path = pathlib.Path(project_dir) / "docs" / "CURRENT_STATE.md"
    if state_path.exists():
        try:
            parts.append("### docs/CURRENT_STATE.md\n")
            parts.append(state_path.read_text(encoding="utf-8").rstrip() + "\n")
        except OSError:
            pass

    handoff_path = pathlib.Path(project_dir) / "docs" / "HANDOFF_LOG.md"
    if handoff_path.exists():
        try:
            lines = handoff_path.read_text(encoding="utf-8").splitlines()
            # Keep the last 5 non-empty lines that look like log entries.
            entries = [ln for ln in lines if "|" in ln][-5:]
            if entries:
                parts.append("\n### Last 5 lines of docs/HANDOFF_LOG.md\n")
                parts.append("\n".join(entries) + "\n")
        except OSError:
            pass

    parts.append(
        "\n---\n"
        "**Action requested:** Give the user a 3-line status report "
        "(current phase / what was accomplished last session / what's next or blocking). "
        "Do not re-read CURRENT_STATE.md or HANDOFF_LOG.md — they are above. "
        "Do not run `/start`; this hook already covered Steps 1–2 of the start protocol. "
        "If the user asks for full git status, run it then."
    )

    emit("".join(parts))


if __name__ == "__main__":
    main()
