#!/usr/bin/env python3
"""
Statusline: shows phase + build status + branch + dirty count.

Format example:
  phase 3.2 | build: working | main | 4 dirty

Reads `Current phase:` and `Build status:` lines from
`docs/CURRENT_STATE.md`. Falls back gracefully when the file or fields
are missing.

Statusline contract:
- Receives a JSON object on stdin describing the session (workspace,
  model, version, etc.). We use `workspace.current_dir` to resolve
  the project root.
- Prints exactly ONE line to stdout. That line is the statusline.
- ANSI color codes are allowed but kept minimal here for portability.
- Must run in <300ms. We do at most three short subprocess calls.
"""

import json
import pathlib
import re
import subprocess
import sys


def run(cmd: list[str], cwd: str) -> str:
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=2
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def extract_phase(text: str) -> str:
    # Looks for: **Current phase:** Phase 3.2 — ...
    m = re.search(r"\*\*Current phase:\*\*\s*([^\n—-]+)", text, re.IGNORECASE)
    if not m:
        return "?"
    raw = m.group(1).strip()
    # Compact "Phase 3.2" → "phase 3.2", drop leading "Phase " for terseness.
    raw = re.sub(r"^Phase\s+", "phase ", raw, flags=re.IGNORECASE)
    return raw[:30]


def extract_build(text: str) -> str:
    # Looks for: **Build status:** **working** ... or any phrasing.
    m = re.search(r"\*\*Build status:\*\*\s*\*?\*?([a-zA-Z ]+?)\*?\*?[\.\n]", text)
    if not m:
        return "?"
    return m.group(1).strip().lower()[:20]


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = (
        payload.get("workspace", {}).get("current_dir")
        or payload.get("cwd")
        or "."
    )
    project_dir = pathlib.Path(cwd)

    state_path = project_dir / "docs" / "CURRENT_STATE.md"
    phase = "?"
    build = "?"
    if state_path.exists():
        try:
            text = state_path.read_text(encoding="utf-8")
            phase = extract_phase(text)
            build = extract_build(text)
        except OSError:
            pass

    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], str(project_dir)) or "no-git"

    dirty_count = 0
    porcelain = run(["git", "status", "--porcelain"], str(project_dir))
    if porcelain:
        dirty_count = len([ln for ln in porcelain.splitlines() if ln.strip()])

    dirty_part = f"{dirty_count} dirty" if dirty_count else "clean"

    sys.stdout.write(f"{phase} | build: {build} | {branch} | {dirty_part}")


if __name__ == "__main__":
    main()
