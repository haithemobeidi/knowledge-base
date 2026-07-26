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


def run(cmd: list[str], cwd: str, timeout: int = 5) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return 1, ""


def remote_state(project_dir: str) -> tuple[int, int, bool, bool]:
    """Fetch origin and report how this checkout stands against upstream.

    Returns (behind, ahead, dirty, fetch_ok).

    Why this must happen BEFORE the docs are read below: every file this
    hook injects is a tracked repo file. Reading them from a checkout
    that is behind origin loads a snapshot of the past that looks
    complete and self-consistent, so nothing downstream can detect it —
    the /start cross-check only tests whether the docs agree with EACH
    OTHER, and stale docs agree perfectly.

    `git status` reporting "up to date with 'origin/main'" is NOT
    evidence of currency: it compares HEAD against the local
    remote-tracking ref, which only moves on fetch/pull/push.

    (Learned 2026-07-25 on Playmoir: a session opened 8 commits / ~18
    hours behind because the prior work happened on a second machine,
    and reported a ledger item as the NEXT ACTION that had been closed
    five hours earlier.)

    This hook deliberately does NOT pull. Mutating the working tree from
    a session-start hook is the wrong place for it — post-merge hooks can
    run installs, and a dirty or diverged tree needs a human decision.
    It detects, and refuses to inject stale docs; the session does the
    pull where it is visible.
    """
    # Longer timeout than the other calls: this one touches the network.
    fetch_rc, _ = run(["git", "fetch", "origin", "--prune"], project_dir, timeout=20)
    fetch_ok = fetch_rc == 0

    rc, counts = run(
        ["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"], project_dir
    )
    behind = ahead = 0
    if rc == 0 and counts:
        try:
            ahead_s, behind_s = counts.split()
            ahead, behind = int(ahead_s), int(behind_s)
        except ValueError:
            pass

    rc, porcelain = run(["git", "status", "--porcelain"], project_dir)
    dirty = rc == 0 and bool(porcelain)

    return behind, ahead, dirty, fetch_ok


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

    # Sync guard — mirrors Step 0.5 of /start. Runs BEFORE the doc reads
    # below, because injecting a stale snapshot is worse than injecting
    # nothing: stale docs are self-consistent, so the cross-check clears
    # them and the session proceeds confidently on old facts.
    behind, ahead, dirty, fetch_ok = remote_state(project_dir)

    if behind > 0:
        _, incoming = run(
            ["git", "log", "--oneline", "--no-decorate", "-15", "HEAD..@{u}"],
            project_dir,
        )
        if ahead > 0:
            resolution = (
                f"The branch has DIVERGED ({ahead} ahead, {behind} behind). **Do NOT auto-merge "
                "or rebase.** Surface this to the user and let them decide."
            )
        elif dirty:
            resolution = (
                f"The tree is behind by {behind} AND has uncommitted changes. **Do NOT stash or "
                "merge.** Surface both to the user and let them decide."
            )
        else:
            resolution = (
                f"The tree is clean and strictly {behind} behind. Run `git pull --ff-only`, then "
                "read `docs/CURRENT_STATE.md`, `docs/SESSION_LEDGER.md`, the ROADMAP status "
                "spine, and the last 5 `docs/HANDOFF_LOG.md` lines YOURSELF before reporting."
            )
        emit(
            "## ⚠️ Session context NOT auto-loaded — this checkout is behind origin\n\n"
            f"`git fetch` found **{behind} commit(s) on the upstream branch that are not here** "
            "(commonly: the last session ran on another machine). The state docs were "
            "deliberately NOT injected, because a stale snapshot reads as complete and "
            "self-consistent — the /start cross-check compares the docs against EACH OTHER, "
            "so it clears stale-but-agreeing docs without complaint.\n\n"
            f"**Incoming commits:**\n```\n{incoming or '(unavailable)'}\n```\n\n"
            f"**Resolution:** {resolution}\n\n"
            "Then give the normal 4-line status plus a sync line naming the pulled commit count. "
            "Never report state read from a checkout you have not confirmed is current."
        )

    # Happy path: read state docs and inject them.
    sync_note = (
        "✅ Fetched origin — checkout is current.\n"
        if fetch_ok
        else "⚠️ **Could not reach origin** — the docs below are from the local checkout and "
        "their currency is UNVERIFIED, not confirmed. Say so in the status report.\n"
    )
    parts: list[str] = [
        "## Auto-loaded session context (SessionStart hook)\n",
        sync_note,
    ]

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
        "**Action requested — session start.** The hook fetched origin (Step 0.5) and "
        "auto-loaded CURRENT_STATE.md, the SESSION_LEDGER (if present), the ROADMAP status "
        "spine (if present), and the last HANDOFF lines (Steps 1–5 of /start). Now:\n"
        "1. **CROSS-CHECK (mandatory).** Does CURRENT_STATE's NEXT ACTION agree with the "
        "ROADMAP spine's CURRENT phase/block AND the last HANDOFF line's 'Next:', AND does "
        "no open `[ ]` ledger gate contradict it? "
        "**If they contradict, STOP and surface the contradiction to the user — do NOT "
        "pick one and proceed.** A stale CURRENT_STATE that leads with a minor loose end while "
        "the spine/handoff point at the real next work is exactly the failure this check catches.\n"
        "2. If they agree, give a 4-line status: where we are (phase/block **name + number** from "
        "the spine) / what last session accomplished / the single **NEXT ACTION** / open ledger "
        "items (count + gates), plus a **sync line** stating currency explicitly "
        "(fetched-and-current, or fetch-failed-so-unverified). Never let currency be assumed — "
        "`git status` saying 'up to date' without a fetch proves nothing.\n"
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
