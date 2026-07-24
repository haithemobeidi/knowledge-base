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

    # Open-item ledger — the append-and-strike record of session-scoped open
    # items (queued tests, gates, riders). Injected whole: it is small by
    # design (open items + <7-day-old struck lines, pruned at /end), and its
    # header carries the during-session rules the agent must follow. Silently
    # skipped if the project has no ledger file.
    ledger_path = pathlib.Path(project_dir) / "docs" / "SESSION_LEDGER.md"
    if ledger_path.exists():
        try:
            parts.append("\n### docs/SESSION_LEDGER.md — open-item ledger\n")
            parts.append(ledger_path.read_text(encoding="utf-8").rstrip() + "\n")
        except OSError:
            pass

    # Inject the ROADMAP "status at a glance" spine — the source of truth for
    # phase/block status. CURRENT_STATE's NEXT ACTION is cross-checked against
    # this (and the handoff line below) before the start report. If the project
    # has no ROADMAP.md or no spine yet, this block is silently skipped.
    roadmap_path = pathlib.Path(project_dir) / "ROADMAP.md"
    if roadmap_path.exists():
        try:
            rlines = roadmap_path.read_text(encoding="utf-8").splitlines()
            spine: list[str] = []
            capturing = False
            for ln in rlines:
                if "status at a glance" in ln.lower():
                    capturing = True
                elif capturing and ln.startswith("## "):
                    break
                if capturing:
                    spine.append(ln)
            if spine:
                parts.append(
                    "\n### ROADMAP.md — status-at-a-glance spine (SOURCE OF TRUTH for phase/block status)\n"
                )
                parts.append("\n".join(spine).rstrip() + "\n")
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
        "**Action requested — session start.** The blocks above auto-loaded "
        "CURRENT_STATE.md, the SESSION_LEDGER (if present), the ROADMAP status spine (if "
        "present), and the last HANDOFF lines (Steps 1–4 of /start). Now:\n"
        "1. **CROSS-CHECK (mandatory).** Does CURRENT_STATE's NEXT ACTION agree with the "
        "ROADMAP spine's CURRENT phase/block AND the last HANDOFF line's 'Next:', AND does "
        "no open `[ ]` ledger gate contradict it? "
        "**If they contradict, STOP and surface the contradiction to the user — do NOT "
        "pick one and proceed.** A stale CURRENT_STATE that leads with a minor loose end while "
        "the spine/handoff point at the real next work is exactly the failure this check catches.\n"
        "2. If they agree, give a 4-line status: where we are (phase/block **name + number** from "
        "the spine) / what last session accomplished / the single **NEXT ACTION** / open ledger "
        "items (count + gates).\n"
        "During the session, follow the ledger's moment-of-event rule (its header): queue and "
        "strike items THE MOMENT they arise or resolve — never wait for /end.\n"
        "Trust but verify — CURRENT_STATE is hand-written and CAN be stale; the ROADMAP spine "
        "wins on any status disagreement, and CURRENT_STATE gets fixed. Numbers are frozen "
        "(never renumber; a cut item stays a labeled gap). Don't re-read the docs above; don't "
        "run `/start` (this hook covered it). Run git status/log only if the user asks or the "
        "cross-check needs it."
    )

    emit("".join(parts))


if __name__ == "__main__":
    main()
