#!/usr/bin/env python3
"""
/end Step 2 — keep the shared block of CURRENT_STATE inside its cap, by moving
its oldest facts to `docs/CURRENT_STATE_ARCHIVE.md`.

Why. In a multi-track project every section of CURRENT_STATE that is not a
NEXT ACTION section is loaded by every track's session, and a track may not
edit lines another track wrote. So each wrap added an "everyone should know"
bullet and nothing ever took one out: on 2026-11-18 the shared block was
15,600–18,500 characters of each of five tracks' 25,000-character budget, the
largest single contributor to every one of them. The budget gate held each
track at a ceiling but nothing made the block shrink. A rule that needs a
session to prune another track's lines is a rule nobody runs; a script that
does it by a mechanical test is one that does.

The rule. The untagged bullets of the shared sections — the ones every track
loads — may total at most `state.shared_max_chars` (default 5,000). Over it,
this moves the OLDEST of them, by the newest ISO date anywhere in the bullet
(the `(by <track>, <date>)` stamp, or a later date in its text; no date counts
as oldest), until the rest fits. Strictly by age: once one does not fit, it and
everything older move. Not counted and never moved:
  - a bullet that starts with a tag (`- →desktop **Desktop 1.8.0 — LIVE** …`):
    it is loaded only for its track, which keeps it current;
  - a section whose heading says "blocker" (a live blocker never ages out);
  - the `state.never_move` sections — Shipped, Build status: each track's
    status of record, old because it is stable, not because it is stale.
    Moving those by age would take every track's current status out of every
    session, its own included (found in review before this shipped);
  - the NEXT ACTION sections, and anything that is not a top-level bullet.

Moved, never deleted. The archive is append-only and never loaded; the start
payload carries one line pointing at it. A fact that still matters to every
track is either a ruling (DECISIONS.md, and the NEXT ACTION of the tracks it
constrains) or current state (put it back with today's stamp, shorter).

Safety:
  - Dry run by default. `--apply` is what writes.
  - Single-track or v1 projects: nothing to do (the whole file is one
    session's, and it may prune its own lines).
  - Refuses to write unless every moved bullet is in the archive, none is left
    in the state file, and the kept text is the original minus the moved
    bullets exactly. Line endings are kept as the file had them.

Usage:
    python .claude/scripts/state-archive.py            # what would move
    python .claude/scripts/state-archive.py --apply    # move it
    python .claude/scripts/state-archive.py --check    # exit 1 if over the cap (the budget gate's test)
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import (  # noqa: E402
    capped_bullets,
    load_config,
    multi_track,
    project_dir,
    protocol_version,
    seg_chars,
    state_segments,
)

# Windows consoles default to a legacy code page (cp1252 here), and every
# document this toolchain prints is full of arrows, em dashes and smart
# quotes. Without this the script dies with UnicodeEncodeError mid-report.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


ARCHIVE_HEADER = """# CURRENT_STATE archive — shared facts moved out of the start payload

Moved here by `.claude/scripts/state-archive.py` when the untagged bullets of
CURRENT_STATE's shared sections went over `state.shared_max_chars` — oldest
first. Never loaded at session start; grep it when a topic comes up.
Append-only: nothing here is edited or removed. A fact that turns out to still
matter to every track goes back into CURRENT_STATE with today's stamp (shorter),
or into DECISIONS.md if it is a ruling.
"""


def plan(segs: list[dict], cap: int) -> tuple[list[dict], int, int]:
    """(bullets to move, chars of capped bullets now, chars after the move)."""
    pool = capped_bullets(segs)
    total = sum(seg_chars(s) for s in pool)
    if total <= cap:
        return [], total, total
    # Newest first; within one date, later in the file first.
    order = sorted(range(len(pool)), key=lambda k: (pool[k]["newest"], k), reverse=True)
    kept = 0
    cut_at = len(order)
    for rank, k in enumerate(order):
        size = seg_chars(pool[k])
        if kept + size > cap:
            cut_at = rank
            break
        kept += size
    move_idx = set(order[cut_at:])
    return [pool[k] for k in sorted(move_idx)], total, kept


def status(proj: pathlib.Path) -> dict | None:
    """What the gate needs: the capped size, the cap, what would move. None
    when this project has no shared block to cap."""
    cfg, _ = load_config(str(proj))
    if protocol_version(cfg) < 2 or not multi_track(cfg):
        return None
    state = proj / "docs" / "CURRENT_STATE.md"
    if not state.exists():
        return None
    cap = int((cfg.get("state") or {}).get("shared_max_chars", 5000))
    text = state.read_text(encoding="utf-8")
    segs = state_segments(text, cfg)
    move, total, kept = plan(segs, cap)
    return {"cfg": cfg, "cap": cap, "text": text, "segs": segs, "move": move, "total": total, "kept": kept}


def main() -> None:
    proj = pathlib.Path(project_dir() or pathlib.Path(__file__).resolve().parent.parent.parent)
    st = status(proj)
    if st is None:
        print("state-archive: not a multi-track v2 project (or no docs/CURRENT_STATE.md) — nothing to do.")
        sys.exit(0)
    cap, move, total, kept = st["cap"], st["move"], st["total"], st["kept"]

    if "--check" in sys.argv:
        if total > cap:
            print(f"state-archive: the shared block's untagged bullets are {total:,} chars, over the cap of "
                  f"{cap:,}. Run `python .claude/scripts/state-archive.py --apply`.")
            sys.exit(1)
        sys.exit(0)

    if not move:
        print(f"state-archive: the shared block's untagged bullets are {total:,} chars, inside the cap of "
              f"{cap:,}. Nothing to move.")
        sys.exit(0)

    moved_chars = total - kept
    print(f"The shared block's untagged bullets are {total:,} chars, over the cap of {cap:,} "
          f"(state.shared_max_chars). {len(move)} bullet(s), {moved_chars:,} chars, oldest first, "
          f"would move to docs/CURRENT_STATE_ARCHIVE.md:")
    for s in move:
        first = " ".join(s["lines"][0].split())
        print(f"  {s['newest'] or 'no date':10}  [{s['section'][:24]}]  {first[2:110]}")
    print("\nBefore applying, read the list: a bullet that is ONE track's state should be tagged for it "
          "instead — `- →<track> …` — then rerun. A standing ruling belongs in DECISIONS.md, and a hazard "
          "warning (\"never rotate X\") in the project CLAUDE.md's rules, which every session loads.")
    if "--apply" not in sys.argv:
        print("\nDry run. Pass --apply to move them. Nothing was written.")
        sys.exit(0)

    state_path = proj / "docs" / "CURRENT_STATE.md"
    archive_path = proj / "docs" / "CURRENT_STATE_ARCHIVE.md"
    crlf = b"\r\n" in state_path.read_bytes()
    moving = {id(s) for s in move}
    kept_lines: list[str] = []
    for s in st["segs"]:
        if id(s) not in moving:
            kept_lines.extend(s["lines"])
    new_state = "\n".join(kept_lines)

    today = _dt.date.today().isoformat()
    by_section: dict[str, list[dict]] = {}
    for s in move:
        by_section.setdefault(s["section"] or "(top of file)", []).append(s)
    block = "\n\n".join(
        f"## Moved {today} from “{sec}”\n\n" + "\n".join("\n".join(s["lines"]).rstrip() for s in segs)
        for sec, segs in by_section.items()
    )
    existing = archive_path.read_text(encoding="utf-8") if archive_path.exists() else ARCHIVE_HEADER
    new_archive = existing.rstrip() + "\n\n" + block + "\n"

    # Conservation, by lines: what the state file kept plus what moved is the
    # original, line for line, and every moved line is in the new archive.
    # (Not a substring test on the state file: a moved bullet's text can
    # legitimately appear inside a kept one, and that refused real moves.)
    moved_lines = [ln for s in move for ln in s["lines"]]
    archive_lines = Counter(ln.rstrip() for ln in new_archive.split("\n"))
    ok = Counter(kept_lines) + Counter(moved_lines) == Counter(st["text"].split("\n"))
    ok = ok and all(archive_lines[ln] >= c for ln, c in Counter(ln.rstrip() for ln in moved_lines).items())
    if not ok:
        print("state-archive: accounting does not balance — refusing to write. Nothing was changed.")
        sys.exit(1)

    nl = "\r\n" if crlf else "\n"
    archive_path.write_text(new_archive, encoding="utf-8", newline=nl)
    state_path.write_text(new_state, encoding="utf-8", newline=nl)
    print(f"\nMoved {len(move)} bullet(s). The shared block is now {kept:,} chars. Commit "
          "docs/CURRENT_STATE.md and docs/CURRENT_STATE_ARCHIVE.md together with the wrap.")


if __name__ == "__main__":
    main()
