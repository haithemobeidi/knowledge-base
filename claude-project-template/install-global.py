#!/usr/bin/env python3
"""
Install the global layer of the session protocol on THIS machine.

What it does (idempotent — rerun after every Knowledge Base pull):

  1. Writes a managed block into ~/.claude/CLAUDE.md that @imports
        <KB>/claude-project-template/global/WORK_STYLE.md
        <KB>/claude-project-template/global/PROTOCOL.md
     and records the KB clone's path. Claude Code loads ~/.claude/CLAUDE.md
     into every session on this machine, so every project gets the rules
     without copying them — and because they are imports, a `git pull` of
     the KB updates them live. Anything you wrote in ~/.claude/CLAUDE.md
     outside the markers is left untouched.

  2. Copies global/commands/start.md and end.md into ~/.claude/commands/
     (slash commands cannot be imported, only copied). A project that ships
     its own .claude/commands/start.md keeps winning — Claude Code prefers
     project-level commands — which is what lets un-migrated projects keep
     their old commands untouched.

Usage:
    python install-global.py            # install / refresh
    python install-global.py --check    # report state, exit 1 if missing or stale
    python install-global.py --uninstall

Paths are written with forward slashes; Claude Code accepts absolute Windows
paths with spaces in @imports without quoting.
"""

from __future__ import annotations

import hashlib
import pathlib
import shutil
import sys

START = "<!-- kb-global:start — managed by claude-project-template/install-global.py; do not edit inside -->"
END = "<!-- kb-global:end -->"

TEMPLATE_DIR = pathlib.Path(__file__).resolve().parent
KB_ROOT = TEMPLATE_DIR.parent
CLAUDE_DIR = pathlib.Path.home() / ".claude"
CLAUDE_MD = CLAUDE_DIR / "CLAUDE.md"
IMPORTS = ("global/WORK_STYLE.md", "global/PROTOCOL.md")
COMMANDS = ("start.md", "end.md")


def fwd(p: pathlib.Path) -> str:
    return str(p).replace("\\", "/")


def managed_block() -> str:
    lines = [
        START,
        "# Global rules — imported live from the Knowledge Base clone on this machine",
        f"Knowledge Base clone on this machine: `{fwd(KB_ROOT)}` (pull it before writing lessons; it never rides a project commit).",
        "",
    ]
    lines += [f"@{fwd(TEMPLATE_DIR / rel)}" for rel in IMPORTS]
    lines.append(END)
    return "\n".join(lines) + "\n"


def sha(path: pathlib.Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    except OSError:
        return ""


def current_text() -> str:
    try:
        return CLAUDE_MD.read_text(encoding="utf-8")
    except OSError:
        return ""


def strip_block(text: str) -> str:
    if START in text and END in text:
        a = text.index(START)
        b = text.index(END) + len(END)
        text = text[:a].rstrip("\n") + ("\n\n" if text[:a].strip() else "") + text[b:].lstrip("\n")
    return text


def status() -> tuple[bool, list[str]]:
    problems: list[str] = []
    text = current_text()
    if START not in text or END not in text:
        problems.append("~/.claude/CLAUDE.md has no managed block")
    else:
        for rel in IMPORTS:
            if f"@{fwd(TEMPLATE_DIR / rel)}" not in text:
                problems.append(f"import missing or points elsewhere: {rel}")
    for rel in IMPORTS:
        if not (TEMPLATE_DIR / rel).exists():
            problems.append(f"template file missing: {rel}")
    for name in COMMANDS:
        src = TEMPLATE_DIR / "global" / "commands" / name
        dst = CLAUDE_DIR / "commands" / name
        if not dst.exists():
            problems.append(f"~/.claude/commands/{name} not installed")
        elif sha(src) != sha(dst):
            problems.append(f"~/.claude/commands/{name} is stale (rerun install)")
    return not problems, problems


def install() -> None:
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
    text = strip_block(current_text())
    new = (text.rstrip("\n") + "\n\n" if text.strip() else "") + managed_block()
    CLAUDE_MD.write_text(new, encoding="utf-8")
    print(f"wrote   {fwd(CLAUDE_MD)}  (managed block with {len(IMPORTS)} imports)")
    (CLAUDE_DIR / "commands").mkdir(parents=True, exist_ok=True)
    for name in COMMANDS:
        src = TEMPLATE_DIR / "global" / "commands" / name
        dst = CLAUDE_DIR / "commands" / name
        shutil.copyfile(src, dst)
        print(f"copied  {fwd(dst)}")
    print("\nInstalled. Restart any open Claude Code session to pick it up. After each `git pull` of the "
          "Knowledge Base, rerun this script so the command copies refresh (the imports are already live).")


def uninstall() -> None:
    text = current_text()
    if START in text:
        CLAUDE_MD.write_text(strip_block(text), encoding="utf-8")
        print(f"removed managed block from {fwd(CLAUDE_MD)}")
    for name in COMMANDS:
        dst = CLAUDE_DIR / "commands" / name
        if dst.exists():
            dst.unlink()
            print(f"removed {fwd(dst)}")
    print("Uninstalled. Projects that carry their own .claude/commands/ are unaffected.")


def main() -> None:
    if "--uninstall" in sys.argv:
        uninstall()
        return
    if "--check" in sys.argv:
        ok, problems = status()
        if ok:
            print(f"install-global: OK — global rules installed from {fwd(TEMPLATE_DIR)}")
            sys.exit(0)
        print("install-global: NOT current")
        for p in problems:
            print(f"  - {p}")
        print(f"Fix: python \"{fwd(TEMPLATE_DIR / 'install-global.py')}\"")
        sys.exit(1)
    install()


if __name__ == "__main__":
    main()
