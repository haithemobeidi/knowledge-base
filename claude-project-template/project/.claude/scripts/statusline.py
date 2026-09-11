#!/usr/bin/env python3
"""
Statusline: phase + build status + branch + dirty count (+ upstream drift in forks).

  phase 3.2 | build: working | main | 4 dirty
  B1 baseline | build: working | odin3-tuning | clean | upstream +7

Reads `**Current phase:**` and `**Build status:**` from docs/CURRENT_STATE.md
(falls back to `?` when absent). Receives the session JSON on stdin and uses
`workspace.current_dir` to find the project. Prints exactly one line. Must
run in <300ms — at most three short git calls, never a fetch: the upstream
count is against the local remote-tracking ref and is only as fresh as the
last fetch (the SessionStart hook does one).
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import load_config  # noqa: E402


def run(cmd: list[str], cwd: str) -> str:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=2)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def extract_phase(text: str) -> str:
    m = re.search(r"\*\*Current phase:\*\*\s*(Phase\s+[\w.]+)", text, re.IGNORECASE)
    if m:
        return re.sub(r"^Phase\s+", "phase ", m.group(1).strip(), flags=re.IGNORECASE)[:30]
    # Narrative phase descriptions: stop at the first sentence terminator.
    m = re.search(r"\*\*Current phase:\*\*\s*([^\n.,—]+)", text, re.IGNORECASE)
    return m.group(1).strip()[:30] if m else "?"


def extract_build(text: str) -> str:
    # First alpha word only — statuses are single words ("working", "broken", "untested").
    m = re.search(r"\*\*Build status:\*\*\s*\*?\*?([a-zA-Z]+)", text)
    return m.group(1).strip().lower() if m else "?"


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        payload = {}
    cwd = payload.get("workspace", {}).get("current_dir") or payload.get("cwd") or "."
    proj = pathlib.Path(cwd)

    phase = build = "?"
    state = proj / "docs" / "CURRENT_STATE.md"
    if state.exists():
        try:
            text = state.read_text(encoding="utf-8")
            phase, build = extract_phase(text), extract_build(text)
        except OSError:
            pass

    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], str(proj)) or "no-git"
    porcelain = run(["git", "status", "--porcelain"], str(proj))
    dirty = len([ln for ln in porcelain.splitlines() if ln.strip()]) if porcelain else 0
    line = f"{phase} | build: {build} | {branch} | {f'{dirty} dirty' if dirty else 'clean'}"

    cfg, _ = load_config(str(proj))
    ref = str(cfg.get("upstream_ref") or "").strip()
    if ref:
        n = run(["git", "rev-list", "--count", f"HEAD..{ref}"], str(proj))
        line += f" | upstream +{n}" if n.isdigit() and int(n) > 0 else " | upstream ok"
    sys.stdout.write(line)


if __name__ == "__main__":
    main()
