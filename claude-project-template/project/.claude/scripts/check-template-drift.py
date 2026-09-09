#!/usr/bin/env python3
"""
Template drift check — is this project's protocol machinery current?

The template in the Knowledge Base is canonical. Every project carries a
byte-identical copy of the scripts, settings.json and agents (project
differences live in `.claude/protocol.json`, never in the scripts). This
script diffs the two so "which projects are behind?" is a command, not a
memory.

Two halves:
  - PROJECT side: `<project>/.claude/...` vs `<template>/project/.claude/...`
  - GLOBAL side:  `~/.claude/commands/{start,end}.md` vs `<template>/global/commands/`
    (commands cannot be @imported, so the installer copies them; a KB pull
    does not refresh them until `install-global.py` is rerun).

Finding the template: the global install's @import line in ~/.claude/CLAUDE.md
points at `<KB>/claude-project-template/global/PROTOCOL.md`; else
$KB_TEMPLATE_DIR; else `--template <dir>`.

Usage:
    python .claude/scripts/check-template-drift.py            # report
    python .claude/scripts/check-template-drift.py --strict   # exit 1 on drift
    python .claude/scripts/check-template-drift.py --template "<path>/claude-project-template"
    python .claude/scripts/check-template-drift.py --sync     # copy template → project (asks nothing; use after the user says resync)

Never blocks work: exits 0 unless --strict.
"""

from __future__ import annotations

import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import (  # noqa: E402
    GLOBAL_COPIED,
    TEMPLATE_MANAGED,
    drift_report,
    global_installed,
    project_dir,
    template_root,
)


def main() -> None:
    args = sys.argv[1:]
    proj = project_dir()
    if not proj:
        # Manual run outside a hook: script lives at <root>/.claude/scripts/
        proj = str(pathlib.Path(__file__).resolve().parent.parent.parent)

    tmpl: pathlib.Path | None = None
    if "--template" in args:
        i = args.index("--template")
        if i + 1 < len(args):
            tmpl = pathlib.Path(args[i + 1])
    tmpl = tmpl or template_root()
    if not tmpl or not (tmpl / "project").is_dir():
        print("check-template-drift: template not found. Install the global rules "
              "(install-global.py) or pass --template <path to claude-project-template>.")
        sys.exit(0)

    pdiff, gdiff = drift_report(proj, tmpl)
    if not global_installed():
        print("WARNING: global rules are NOT installed on this machine (~/.claude/CLAUDE.md has no template import). "
              "Run: python \"" + str(tmpl / "install-global.py") + "\"")

    if "--sync" in args:
        for rel in pdiff:
            src = tmpl / "project" / rel
            dst = pathlib.Path(proj) / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            print(f"synced  {rel}")
        if gdiff:
            print("Global copies are stale too — rerun install-global.py to refresh ~/.claude/commands/.")
        if not pdiff:
            print("Project already matches the template.")
        sys.exit(0)

    if not pdiff and not gdiff:
        print(f"check-template-drift: up to date with {tmpl}")
        sys.exit(0)

    print(f"TEMPLATE DRIFT vs {tmpl}")
    if pdiff:
        print(f"  Project files differing or missing ({len(pdiff)} of {len(TEMPLATE_MANAGED)} managed):")
        for rel in pdiff:
            exists = (pathlib.Path(proj) / rel).exists()
            print(f"    {'DIFFERS' if exists else 'MISSING'}  {rel}")
        print("  Fix: `python .claude/scripts/check-template-drift.py --sync` (after the user agrees), "
              "or upstream the change into the template if it is a real improvement.")
    if gdiff:
        print(f"  Global copies stale ({len(gdiff)} of {len(GLOBAL_COPIED)}): " + ", ".join(gdiff))
        print("  Fix: rerun `python \"" + str(tmpl / "install-global.py") + "\"`")
    sys.exit(1 if "--strict" in args else 0)


if __name__ == "__main__":
    main()
