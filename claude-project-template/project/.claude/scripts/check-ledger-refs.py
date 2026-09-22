#!/usr/bin/env python3
"""
/end Step 1e — the copy-forward guard.

Every ledger ID cited in CURRENT_STATE.md and the ROADMAP spine, classified
against the ledger: open / struck / absent.

Why this exists. On a real project, CURRENT_STATE.md cited 146 ledger IDs and
65 of them were already struck — 45% of every ID reference in the file. One of
them said two items "still wait for the Android session" eight days after both
were closed. Nothing caught it: `/start`'s cross-check compares the state docs
against EACH OTHER, and documents that have all copied the same stale claim
agree perfectly. Copy-forward is the default editing action — every wrap
re-reads the file and rewrites the parts it was thinking about, so a line
nobody was thinking about survives untouched, forever.

This is a measured hazard class, not a nitpick: in clinical records, where the
same mechanism has been studied for two decades, copied exam findings persisted
a median of 56 days past the original note, and copy/paste mistakes contributed
to 35.7% of diagnostic errors in cases where copying had occurred.

Design constraints, each one earned:

  - **Only DECLARED prefixes match** (protocol.json → tracks, plus legacy `L`).
    A generic [A-Z]{1,4}-\\d+ also catches BUG-79 and AVX-512.
  - **Three classes, not two.** `absent` means the line has been moved to the
    closed file (or never existed) — on the same project 51 of 72 spine IDs were
    absent, nearly all of them legitimate history. Only `struck` is actionable.
  - **Report, never block.** A closed ID cited AS history is correct prose. This
    script cannot tell "D-8 is still pending" from "closed by D-8", so a human
    reads the line. It surfaces candidates; it does not rule.
  - **Multi-track scoping.** A stale ID inside another track's section is not
    this session's to edit — it is reported as theirs, for a tagged ledger line.
  - **Anchored matching.** Its sibling track-new-file.py decides "already
    indexed" with a bare substring test and therefore misses any path that
    appears inside another row's description. A check that can return a false
    all-clear is worse than no check: it converts an open question into
    unearned confidence.

Usage:
    python .claude/scripts/check-ledger-refs.py           # report
    python .claude/scripts/check-ledger-refs.py --strict  # exit 1 on struck refs
    python .claude/scripts/check-ledger-refs.py --json

Exits 0 unless --strict. Silent on failure.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import id_prefixes, load_config, multi_track, project_dir, track_aliases  # noqa: E402

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


# Anchored to the line start: only a real ledger row defines an ID's status.
# An ID merely mentioned inside another item's prose must never set status.
STATUS_RE = re.compile(r"^- \[( |x|-)\]\s+([A-Za-z]{1,4}-\d+)\b", re.MULTILINE)
STATUS = {" ": "open", "x": "struck", "-": "struck"}

SCANNED = ("docs/CURRENT_STATE.md", "ROADMAP.md")


def ledger_status(proj: pathlib.Path) -> dict[str, str]:
    """ID → open | struck, from the live ledger AND the closed archive."""
    out: dict[str, str] = {}
    for rel in ("docs/SESSION_LEDGER.md", "docs/SESSION_LEDGER_CLOSED.md"):
        p = proj / rel
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        for mark, item_id in STATUS_RE.findall(text):
            # An open line always wins: a concurrent session may have reopened
            # an item whose earlier closed copy is still in the archive.
            if out.get(item_id) != "open":
                out[item_id] = STATUS[mark]
    return out


def section_owner(line_no: int, headings: list[tuple[int, str]], aliases: dict[str, str]) -> str | None:
    """Which track's section a line sits in, by the nearest heading above it.

    A heading that names no track RESETS ownership to None rather than
    inheriting it. Carrying it forward made `## Shared` — which belongs to
    every track and to none — report as whichever track's NEXT ACTION heading
    happened to come last in the file, and then told the session it could not
    edit a block it owns jointly."""
    owner = None
    for pos, text in headings:
        if pos > line_no:
            break
        low = text.lower()
        owner = next((canon for word, canon in aliases.items() if word in low), None)
    return owner


def main() -> None:
    proj = pathlib.Path(project_dir() or pathlib.Path(__file__).resolve().parent.parent.parent)
    cfg, _ = load_config(str(proj))
    status = ledger_status(proj)
    if not status:
        print("check-ledger-refs: no ledger found, skipped")
        sys.exit(0)

    pat = re.compile(r"\b(?:" + "|".join(id_prefixes(cfg)) + r")-\d+\b")
    aliases = track_aliases(cfg)
    findings: list[dict] = []
    counts = {"open": 0, "struck": 0, "absent": 0}

    for rel in SCANNED:
        path = proj / rel
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        headings = [(i, ln) for i, ln in enumerate(lines) if ln.lstrip().startswith("#")]
        for i, ln in enumerate(lines):
            struck_here: list[str] = []
            for item_id in dict.fromkeys(pat.findall(ln)):
                klass = status.get(item_id, "absent")
                counts[klass] += 1
                if klass == "struck":
                    struck_here.append(item_id)
            # One finding per LINE, not per ID. A sentence citing three struck
            # items is one thing to read and one decision to make; three
            # findings quoting the same 160 characters is noise, and noise is
            # how a check earns the right to be ignored.
            if struck_here:
                findings.append({
                    "file": rel, "line": i + 1, "ids": struck_here,
                    "owner": section_owner(i, headings, aliases) if multi_track(cfg) else None,
                    "text": re.sub(r"\s+", " ", ln.strip())[:200],
                })

    if "--json" in sys.argv:
        print(json.dumps({"counts": counts, "struck_refs": findings}, indent=2))
        sys.exit(1 if ("--strict" in sys.argv and findings) else 0)

    print(f"Ledger references in {', '.join(SCANNED)}: "
          f"{counts['open']} open, {counts['struck']} struck, {counts['absent']} not in the ledger")
    print("  'not in the ledger' is usually a moved closed line cited as history — informational.")
    if not findings:
        print("\nNo struck item is cited. Nothing to reconcile.")
        sys.exit(0)

    print(f"\n{len(findings)} line(s) cite STRUCK items — read each and decide:")
    print("  still describes it as pending  -> fix it in this wrap")
    print("  describes it as done/history   -> correct as written, leave it\n")
    for f in findings:
        own = f" [{f['owner']}'s section]" if f.get("owner") else ""
        print(f"  {f['file']}:{f['line']}  cites {', '.join(f['ids'])}{own}")
        print(f"      {f['text']}")
    if multi_track(cfg):
        print("\nMulti-track: a line in another track's section is not yours to edit — "
              "put it on the ledger tagged for that track.")
    sys.exit(1 if "--strict" in sys.argv else 0)


if __name__ == "__main__":
    main()
