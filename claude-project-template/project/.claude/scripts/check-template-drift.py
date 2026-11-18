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

import json
import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import (  # noqa: E402
    GLOBAL_COPIED,
    TEMPLATE_MANAGED,
    drift_report,
    global_installed,
    project_dir,
    template_currency,
    template_root,
)

# Windows consoles default to a legacy code page (cp1252 here), and every
# document this toolchain prints is full of arrows, em dashes and smart
# quotes. Without this the script dies with UnicodeEncodeError mid-report, or
# silently mangles characters — both seen live on 2026-09-22, which is what
# prompted this. stdout may be a pipe with no reconfigure(), hence the guard.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass



def _run(proj: pathlib.Path, script: str, *flags: str) -> str:
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(proj), PYTHONIOENCODING="utf-8")
    try:
        return subprocess.run(
            [sys.executable, str(proj / ".claude" / "scripts" / script), *flags], cwd=str(proj),
            capture_output=True, text=True, encoding="utf-8", timeout=60, check=False, env=env,
        ).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def adopt(proj: pathlib.Path, tmpl: pathlib.Path) -> None:
    """What a sync has to do besides copying files, so that bringing a project
    onto a newer template is ONE command. Each step is safe to repeat and
    touches nothing a session wrote:

    - a new project document the template gained is added when it is missing
      (never overwritten — it is project-owned from then on);
    - the day the `/end` budget gate arrives (protocol.json has no
      `payload.ceiling_chars` key yet), a payload that is already over the
      budget gets its ceiling, so the first wrap after the sync is not stopped
      for the size the project had before the rule existed. The key is written
      even when empty, which is what makes this happen exactly once;
    - anything left for a person to decide is printed as the exact command."""
    todo: list[str] = []
    did = False
    # A script the template GAINED. `--sync` is run by the project's OLD copy
    # of this file, whose list of managed files predates the new one, so it
    # copies everything it knows about and hands over to the new copy with
    # `--adopt` — which is here. Without this, state-archive.py (2026-11-18)
    # arrived only on a second `--sync`, and the adoption below could not see
    # it to run. Missing files only: a file that exists is --sync's to replace.
    for rel in TEMPLATE_MANAGED:
        src, dst = tmpl / "project" / rel, proj / rel
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            did = True
            print(f"added   {rel} (new in the template)")
    queue = proj / "docs" / "LESSONS_QUEUE.md"
    src = tmpl / "project" / "docs" / "LESSONS_QUEUE.md"
    if (proj / "docs").is_dir() and not queue.exists() and src.exists():
        shutil.copyfile(src, queue)
        did = True
        print("added   docs/LESSONS_QUEUE.md (lessons waiting to be written up live here, not on the ledger)")
    try:
        raw = json.loads((proj / ".claude" / "protocol.json").read_text(encoding="utf-8"))
        gate_is_new = "ceiling_chars" not in (raw.get("payload") or {})
    except (OSError, ValueError, AttributeError):
        gate_is_new = False  # no readable protocol.json: nothing to record a ceiling in
    if gate_is_new:
        did = True
        out = _run(proj, "check-payload-budget.py", "--init-ceiling")
        ceilings = [ln for ln in out.splitlines() if ln.startswith("Ceiling:")]
        print("\nThe /end budget gate arrives with this sync (PROTOCOL.md 'The injection budget').")
        if ceilings:
            print("This project is over the budget today, so its payload gets a ceiling at today's size.")
            print("It only moves down, and a wrap that would exceed it stops:")
            for ln in ceilings:
                print("  " + ln)
        else:
            print("This project is inside the budget; no ceiling was needed.")
    lessons = _run(proj, "ledger-archive.py", "--lessons")
    if "would move" in lessons:
        ids = next((ln.strip() for ln in lessons.splitlines() if ln.startswith("  ")), "")
        todo.append(
            "Lesson reminders are sitting on the ledger as open items (" + ids + "). Move them to the "
            "lessons queue:\n      python .claude/scripts/ledger-archive.py --lessons --apply"
        )
    state = _run(proj, "state-archive.py")
    if "would move" in state:
        todo.append(
            "CURRENT_STATE's shared block is over its cap (protocol.json → state.shared_max_chars), and the "
            "next /end gate stops on that. First tag each bullet that is ONE track's state — Build status and "
            "Shipped rows above all — as `- →<track> …`, so only that track loads it; then move the oldest "
            "of the rest out (it prints what it moves first):\n      python .claude/scripts/state-archive.py --apply"
        )
    if todo:
        print("\nLeft for you (nothing below was done):")
        for t in todo:
            print("  - " + t)
    if did or todo:
        print("\nThen commit .claude/ and docs/LESSONS_QUEUE.md, and start a fresh session to see the new start.")


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

    # Fetch the KB clone before comparing against it. This script is the tool
    # you run to decide whether to sync, and it was comparing against whatever
    # copy happened to be on this machine's disk — so on a clone twenty commits
    # behind it printed "up to date" about the source of truth for the rules
    # themselves. An internal-consistency check cannot detect staleness: stale
    # copies agree with each other perfectly. `--no-fetch` to skip (offline).
    if "--no-fetch" not in args:
        try:
            subprocess.run(["git", "fetch", "origin", "--prune"], cwd=str(tmpl.parent),
                           capture_output=True, timeout=20, check=False)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        behind = subprocess.run(["git", "rev-list", "--count", "HEAD..@{u}"], cwd=str(tmpl.parent),
                                capture_output=True, text=True, timeout=5, check=False).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        behind = ""
    if behind.isdigit() and int(behind) > 0:
        print(f"⚠️  The Knowledge Base clone at {tmpl.parent} is {behind} commit(s) BEHIND its remote.")
        print("   Everything below compares against that stale copy. `git pull --ff-only` there,")
        print("   rerun install-global.py, then run this again before syncing anything.\n")
    elif not behind:
        fetched, head = template_currency(tmpl)
        print(f"(Could not verify the KB clone against its remote — last fetched "
              f"{fetched if fetched is not None else '?'} day(s) ago. Drift results are unverified.)\n")

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
        me = ".claude/scripts/check-template-drift.py"
        if me in pdiff:
            # This process is the OLD copy of this script; the adoption steps
            # belong to the one it just installed.
            sys.stdout.flush()
            subprocess.run([sys.executable, str(pathlib.Path(proj) / me), "--adopt", "--template", str(tmpl),
                            "--no-fetch"], cwd=proj, check=False,
                           env=dict(os.environ, CLAUDE_PROJECT_DIR=proj))
        else:
            adopt(pathlib.Path(proj), tmpl)
        sys.exit(0)

    if "--adopt" in args:
        adopt(pathlib.Path(proj), tmpl)
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
