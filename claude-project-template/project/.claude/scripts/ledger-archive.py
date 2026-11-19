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

Parking and retagging (`--park`, `--unpark`, `--parked`, `--retag`) edit
named items in place; that half lives in `ledger_items.py`, with its own
safety rules.

Usage:
    python .claude/scripts/ledger-archive.py            # what would move
    python .claude/scripts/ledger-archive.py --apply    # move it
    python .claude/scripts/ledger-archive.py --park D-28,M-67 --until "the iOS prototype works" [--apply]
    python .claude/scripts/ledger-archive.py --unpark D-28,M-67 [--because "iOS prototype passed"] [--apply]
    python .claude/scripts/ledger-archive.py --parked   # list parked items by the event they wait on
    python .claude/scripts/ledger-archive.py --retag D-12,M-3 --to desktop [--because "why"] [--apply]
    python .claude/scripts/ledger-archive.py --retag SO-9 --to android/ios --apply
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import load_config, project_dir  # noqa: E402
from ledger_items import list_parked, park, retag  # noqa: E402

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


QUEUE_HEADER = """# Lessons queue — transferable lessons waiting to be written up

Lessons flagged `*kbdoc` that have not been written into the Knowledge Base yet.
One entry per lesson, appended at the moment it is flagged or at `/end` Step 1f;
the first line says what the lesson is, anything worth keeping for the write-up
goes on continuation lines. When the article is written, change `[ ]` to `[x]`
and add `→ WRITTEN <date>: <article file>`.

Never loaded at session start, so it costs nothing and may grow. Lessons do NOT
take ledger IDs: the ledger is for open loops a session must act on, and a
write-up the user asks for when they want it is not one.
"""

def lesson_id(line: str) -> str | None:
    """The ID of an open item whose TITLE starts `kbdoc:`, else None.

    The title is what follows the ID, an optional →tag, the provenance
    parenthetical (which may itself contain parentheses) and an optional →tag —
    with or without bold. `kbdoc:` anywhere later on the line is NOT a lesson
    item: "**Real work.** Found the cause — kbdoc: worth a write-up" is a real
    open loop that mentions a lesson, and moving it would hide it from every
    session."""
    m = re.match(r"- \[ \] ([A-Za-z]{1,4}-\d+)\s*(?:(?:→|->)\s*[\w-]+\s*)?", line)
    if not m:
        return None
    rest = line[m.end():]
    if rest.startswith("("):
        depth = 0
        for k, ch in enumerate(rest):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0:
                rest = rest[k + 1:]
                break
        else:
            return None
    rest = re.sub(r"^\s*(?:(?:→|->)\s*[\w-]+)?\s*(?:\*\*)?\s*", "", rest)
    return m.group(1) if re.match(r"kbdoc\s*:", rest, re.IGNORECASE) else None


def move_lessons(proj: pathlib.Path, ledger: pathlib.Path, apply: bool) -> None:
    """`--lessons`: move open `kbdoc:` items out of the ledger into
    `docs/LESSONS_QUEUE.md`. One-time, for a ledger written under the old /end
    Step 1f, which turned every unwritten lesson into a ledger item (11 of 124
    open items on one project). The item's whole text goes to the queue; a
    struck one-line stub stays in the ledger so its ID still resolves."""
    queue = proj / "docs" / "LESSONS_QUEUE.md"
    today = _dt.date.today().isoformat()
    lines = ledger.read_text(encoding="utf-8").split("\n")
    out: list[str] = []
    moved: list[tuple[str, list[str]]] = []
    in_comment = fenced = False
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith(("```", "~~~")):
            fenced = not fenced
        elif in_comment:
            in_comment = "-->" not in ln
        elif "<!--" in ln and "-->" not in ln[ln.rindex("<!--"):]:
            in_comment = True
        item_id = None if (in_comment or fenced) else lesson_id(ln)
        if not item_id:
            out.append(ln)
            i += 1
            continue
        # The WHOLE item: its ID line and everything under it up to the next
        # item or section heading at the start of a line — blank-separated
        # paragraphs, indented `#` lines and nested checkboxes included, which
        # is the same extent the start hook reads as one item.
        j = i + 1
        while j < len(lines) and not lines[j].startswith(("- [", "#", "<!--", "```", "~~~")):
            j += 1
        while j > i + 1 and not lines[j - 1].strip():
            j -= 1  # trailing blank lines stay in the ledger as spacing
        block = lines[i:j]
        moved.append((item_id, block))
        title = re.search(r"\*\*(.+?)\*\*", ln)
        cut = ln.index(title.group(0)) + len(title.group(0)) if title else len(ln)
        stub = ln[:cut].replace("- [ ]", "- [-]", 1)
        out.append(f"{stub} → MOVED {today} to docs/LESSONS_QUEUE.md (lessons wait there, not on the ledger)")
        i = j

    if not moved:
        print("ledger-archive --lessons: no open `kbdoc:` items in the ledger. Nothing to move.")
        sys.exit(0)
    print(f"{len(moved)} open lesson item(s) would move to docs/LESSONS_QUEUE.md "
          "(whole text; a struck stub keeps each ID resolvable):")
    print("  " + ", ".join(i for i, _ in moved))
    for _, block in moved:
        print("    " + re.sub(r"\s+", " ", block[0])[6:150])
    if not apply:
        print("\nDry run. Pass --apply to move them. Nothing was written.")
        sys.exit(0)
    existing = queue.read_text(encoding="utf-8") if queue.exists() else QUEUE_HEADER
    new_queue = existing.rstrip() + "\n\n" + "\n".join("\n".join(b) for _, b in moved).rstrip() + "\n"
    new_ledger = "\n".join(out)
    # Conservation: every moved ID is in both files, and every moved line is in the queue.
    for item_id, block in moved:
        if not re.search(r"(?m)^- \[-\] " + re.escape(item_id) + r"\b", new_ledger) or any(
            b not in new_queue for b in block
        ):
            print(f"ledger-archive --lessons: accounting does not balance for {item_id} — refusing to write.")
            sys.exit(0)
    queue.write_text(new_queue, encoding="utf-8", newline="\n")
    ledger.write_text(new_ledger, encoding="utf-8", newline="\n")
    print(f"\nMoved {len(moved)} item(s). Commit docs/SESSION_LEDGER.md and docs/LESSONS_QUEUE.md together.")
    sys.exit(0)


def _arg(flag: str) -> str | None:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
            return sys.argv[i + 1]
    return None


def main() -> None:
    proj = pathlib.Path(project_dir() or pathlib.Path(__file__).resolve().parent.parent.parent)
    cfg, _ = load_config(str(proj))
    ledger = proj / "docs" / "SESSION_LEDGER.md"
    archive = proj / "docs" / "SESSION_LEDGER_CLOSED.md"
    if not ledger.exists():
        print("ledger-archive: no docs/SESSION_LEDGER.md, skipped")
        sys.exit(0)

    if "--parked" in sys.argv:
        list_parked(ledger)

    apply = "--apply" in sys.argv
    for flag, unpark in (("--park", False), ("--unpark", True)):
        if flag in sys.argv:
            ids = _arg(flag)
            if not ids:
                print(f"ledger-archive {flag}: give the IDs, comma-separated: {flag} D-28,M-67")
                sys.exit(1)
            park(ledger, ids, unpark, apply, _arg("--until") or "", _arg("--because") or "")
    if "--retag" in sys.argv:
        ids = _arg("--retag")
        if not ids:
            print("ledger-archive --retag: give the IDs, comma-separated: --retag D-28,M-67 --to desktop")
            sys.exit(1)
        retag(ledger, cfg, ids, apply, _arg("--to") or "", _arg("--because") or "")

    if apply and tracked_dirty(proj, "docs/SESSION_LEDGER.md") and "--force" not in sys.argv:
        print("ledger-archive: docs/SESSION_LEDGER.md has uncommitted changes. A concurrent session may be "
              "mid-edit. Commit first, or pass --force if you are sure this session owns the file.")
        sys.exit(0)

    if "--lessons" in sys.argv:
        move_lessons(proj, ledger, apply)

    days = int(cfg["ledger"].get("move_closed_after_days",
                                 cfg["ledger"].get("prune_closed_after_days", 7)))
    cutoff = _dt.date.today() - _dt.timedelta(days=days)
    text = ledger.read_text(encoding="utf-8")
    chunks = re.split(r"\n(?=- \[)", text)

    keep: list[str] = []
    move: list[str] = []
    in_comment = False
    for chunk in chunks:
        # The header's example items live inside an HTML comment, and they look
        # exactly like real closed lines. Moving them would cut lines out of the
        # comment and archive fiction; seen on a fresh v2 ledger, 2026-10-02.
        # The start hook already skips comment blocks; this keeps the two agreeing.
        started_in_comment = in_comment
        opened, closed = chunk.rfind("<!--"), chunk.rfind("-->")
        if opened > closed:
            in_comment = True
        elif closed > opened:
            in_comment = False
        if started_in_comment or not re.match(r"- \[[x-]\]", chunk):
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
