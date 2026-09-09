#!/usr/bin/env python3
"""
Stop hook: enforces /end Step 4a (clean-tree guarantee) as a fail-safe.

Fires whenever Claude finishes a turn. Silent during normal work — it only
intervenes when this exact protocol-violation pattern is detected:

  1. The most recent commit subject starts with "Session" (i.e. `Session:`,
     `Session followup:`, or the multi-track forms `Session (desktop):` /
     `Session followup (mobile):`) AND was made within the last 5 minutes,
     AND
  2. `git status --porcelain` still lists files that this session is
     responsible for.

Multi-track repos (`.claude/protocol.json` declares 2+ tracks): the tree
legitimately holds the OTHER session's uncommitted work. A dirty file is
tolerated only when it sits inside another track's declared `owns` paths.
Dirty files in this track's paths, in `shared_paths`, or anywhere undeclared
still block — the wrap has to categorise them explicitly (commit as
followup, or state in the report that they belong to the other session).

Outside that pattern the hook exits 0 and Claude stops normally. Silent on
every failure path.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import load_config, multi_track, project_dir, track_of_path  # noqa: E402

SUBJECT_RE = re.compile(r"^Session(?: followup)?(?:\s*\((?P<track>[^)]+)\))?\s*:")


def run(cmd: list[str], cwd: str) -> tuple[int, str]:
    # rstrip only: `git status --porcelain` lines start with a status column
    # that can be a SPACE (" M path"), and strip() would eat it and shift the
    # path by one character.
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=5)
        return r.returncode, r.stdout.rstrip()
    except (subprocess.SubprocessError, OSError):
        return 1, ""


def porcelain_paths(status: str) -> list[str]:
    paths: list[str] = []
    for ln in status.splitlines():
        if len(ln) < 4:
            continue
        p = ln[3:]  # "XY " then the path
        if " -> " in p:
            p = p.split(" -> ", 1)[1]
        p = p.strip().strip('"')
        if p:
            paths.append(p.replace("\\", "/"))
    return paths


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    if data.get("stop_hook_active"):
        sys.exit(0)  # already fired once this turn cycle — never loop

    proj = project_dir()
    if not proj or not pathlib.Path(proj).is_dir():
        sys.exit(0)
    rc, _ = run(["git", "rev-parse", "--git-dir"], proj)
    if rc != 0:
        sys.exit(0)

    rc, info = run(["git", "log", "-1", "--format=%s|%ct"], proj)
    if rc != 0 or "|" not in info:
        sys.exit(0)
    subject, _, ts = info.rpartition("|")
    try:
        age = int(time.time()) - int(ts)
    except ValueError:
        sys.exit(0)
    m = SUBJECT_RE.match(subject)
    if not m or age > 300:
        sys.exit(0)

    rc, status = run(["git", "status", "--porcelain"], proj)
    if rc != 0 or not status:
        sys.exit(0)

    cfg, _ = load_config(proj)
    dirty = porcelain_paths(status)
    my_track = (m.group("track") or "").strip()
    blockers: list[str] = []
    tolerated: list[str] = []
    if multi_track(cfg) and my_track:
        for p in dirty:
            kind, owner = track_of_path(cfg, p)
            if kind == "track" and owner.lower() != my_track.lower():
                tolerated.append(f"{p} (owned by {owner})")
            else:
                blockers.append(p)
    else:
        blockers = dirty

    if not blockers:
        sys.exit(0)

    tol = (
        "\nTolerated (another track's owned paths, left for that session): " + ", ".join(tolerated)
        if tolerated
        else ""
    )
    hint = (
        " In a multi-track repo, put your track in the subject — `Session (<track>): …` — so the other "
        "session's files can be told apart."
        if multi_track(cfg) and not my_track
        else ""
    )
    payload = {
        "decision": "block",
        "reason": (
            "PROTOCOL VIOLATION: /end Step 4a (clean-tree guarantee) was skipped. The most recent commit "
            f"is a Session commit but these paths are still dirty: {', '.join(blockers)}.{tol} You must NOT "
            "stop here. Categorise each per /end Step 4a (real in-scope work → `Session followup` commit; "
            "another session's work in SHARED or undeclared paths → say so explicitly in the report and "
            "leave it; out-of-scope → ask the user: commit, stash, or discard), then push again. Only stop "
            "once every remaining dirty path is accounted for." + hint
        ),
    }
    sys.stdout.write(json.dumps(payload))
    sys.exit(0)


if __name__ == "__main__":
    main()
