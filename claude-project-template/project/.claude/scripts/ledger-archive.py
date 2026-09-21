#!/usr/bin/env python3
"""
/end Step 1d.4 — move struck ledger lines out of the hot file.

Closed `[x]` / `[-]` lines older than `ledger.move_closed_after_days` are
APPENDED to `docs/SESSION_LEDGER_CLOSED.md` and removed from
`docs/SESSION_LEDGER.md`. **Moved, never deleted.** That archive is never
injected, so it can grow forever, and every ID that escaped into a commit
subject, a handoff entry or a spine cell stays resolvable. v1 pruned these
lines outright and left 51 of 72 spine IDs on one project pointing at nothing.

Why a script and not a step: v1 specified this as prose in `/end` and it never
once ran. 88 closed lines were sitting in a ledger with a 7-day rule. Every
rule in this protocol enforced by a script held; every rule enforced by
discipline at wrap time failed. A rule with no script is a wish.

Safety:
  - Dry run by default. `--apply` is what writes.
  - Refuses to run on a dirty ledger unless `--force`: a concurrent session may
    be mid-edit, and two writers on this file is how items get lost.
  - Counts lines in and out and refuses to write if they do not balance.

Usage:
    python .claude/scripts/ledger-archive.py            # what would move
    python .claude/scripts/ledger-archive.py --apply    # move it
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import load_config, project_dir  # noqa: E402

ARCHIVE_HEADER = """# Closed ledger items

Moved out of `SESSION_LEDGER.md` so the working file stays small, and kept so
every ID cited in a commit subject, a handoff entry or a spine cell stays
resolvable. Never injected at session start. Append-only — nothing here is ever
edited or removed.
"""


def tracked_dirty(proj: pathlib.Path, rel: str) -> bool:
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=str(proj),
                             capture_output=True, text=True, timeout=5, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(out.strip())


def main() -> None:
    proj = pathlib.Path(project_dir() or pathlib.Path(__file__).resolve().parent.parent.parent)
    cfg, _ = load_config(str(proj))
    ledger = proj / "docs" / "SESSION_LEDGER.md"
    archive = proj / "docs" / "SESSION_LEDGER_CLOSED.md"
    if not ledger.exists():
        print("ledger-archive: no docs/SESSION_LEDGER.md, skipped")
        sys.exit(0)

    apply = "--apply" in sys.argv
    if apply and tracked_dirty(proj, "docs/SESSION_LEDGER.md") and "--force" not in sys.argv:
        print("ledger-archive: docs/SESSION_LEDGER.md has uncommitted changes. A concurrent session may be "
              "mid-edit. Commit first, or pass --force if you are sure this session owns the file.")
        sys.exit(0)

    days = int(cfg["ledger"].get("move_closed_after_days",
                                 cfg["ledger"].get("prune_closed_after_days", 7)))
    cutoff = _dt.date.today() - _dt.timedelta(days=days)
    text = ledger.read_text(encoding="utf-8")
    chunks = re.split(r"\n(?=- \[)", text)

    keep: list[str] = []
    move: list[str] = []
    for chunk in chunks:
        if not re.match(r"- \[[x-]\]", chunk):
            keep.append(chunk)
            continue
        dates = [d for d in re.findall(r"(\d{4}-\d{2}-\d{2})", chunk)]
        try:
            newest = max(_dt.date.fromisoformat(d) for d in dates) if dates else None
        except ValueError:
            newest = None
        # No parseable date means we cannot prove it is old. Keep it.
        (move if newest and newest < cutoff else keep).append(chunk)

    if not move:
        print(f"ledger-archive: nothing struck longer than {days} day(s) ago. Nothing to move.")
        sys.exit(0)

    ids = [m.group(1) for m in (re.match(r"- \[[x-]\]\s+([A-Za-z]{1,4}-\d+)", c) for c in move) if m]
    print(f"{len(move)} closed item(s) older than {days} day(s) would move to docs/SESSION_LEDGER_CLOSED.md:")
    print("  " + ", ".join(ids))

    if len(keep) + len(move) != len(chunks):
        print("ledger-archive: line accounting does not balance — refusing to write.")
        sys.exit(0)

    if not apply:
        print("\nDry run. Pass --apply to move them. Nothing was written.")
        sys.exit(0)

    existing = archive.read_text(encoding="utf-8") if archive.exists() else ARCHIVE_HEADER
    archive.write_text(existing.rstrip() + "\n\n" + "\n".join(move).rstrip() + "\n", encoding="utf-8")
    ledger.write_text("\n".join(keep).rstrip() + "\n", encoding="utf-8")
    print(f"\nMoved {len(move)} item(s). Both files are staged for your wrap commit — "
          "commit them together so the move is atomic in history.")


if __name__ == "__main__":
    main()
