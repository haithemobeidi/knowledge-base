#!/usr/bin/env python3
"""
One-time content migration from the v1 document shapes to v2.

**Every verb here is append or move. Nothing is deleted, rewritten or
summarized.** A cap that can lose your words is a cap you have to argue with;
this one cannot, so there is nothing to argue about. Output goes to `.new`
files (or `--out <dir>`) and the originals are never touched — you read the
result, then replace by hand.

What it does, and what it deliberately refuses to do:

  MECHANICAL (the script does it)
  - CURRENT_STATE's session narrative -> HANDOFF_LOG entries, joined on the
    session ordinal ("153rd"). Verified on the live project: all 30 narrative
    blocks had a matching handoff line. An unmatched block is REPORTED and left
    in place, never guessed at and never summarized.
  - Closed ledger lines older than `move_closed_after_days` -> a new
    SESSION_LEDGER_CLOSED.md, appended in file order.
  - A v2 CURRENT_STATE skeleton carrying the sections that transfer verbatim.

  JUDGEMENT (handed to the user as one table)
  - Every "Shared" and "Things to watch" bullet: still a live loop / a standing
    fact about the app / obsolete. A script cannot tell these apart, and
    guessing would be the copy-forward mistake in the other direction.

Usage:
    python .claude/scripts/migrate-docs-v2.py                 # writes *.new.md in docs/
    python .claude/scripts/migrate-docs-v2.py --out <dir>     # writes elsewhere (safe for a live checkout)
    python .claude/scripts/migrate-docs-v2.py --report        # triage table only, writes nothing

Never sets `protocol_version`. Flip that by hand once the documents are in place.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import load_config, project_dir  # noqa: E402

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


ORDINAL = re.compile(r"\*\*(\d+)(?:st|nd|rd|th)\b")
KEEP_SECTIONS = ("next action", "build status", "active blocker")
TRIAGE_SECTIONS = ("shared", "things to watch", "loose end")
NARRATIVE_SECTIONS = ("what the last session", "what the last sessions")


def split_sections(text: str) -> list[tuple[str, str]]:
    """[(heading, body)…]; the preamble comes back under heading ''."""
    out: list[tuple[str, str]] = []
    head, buf = "", []
    for ln in text.splitlines():
        if ln.startswith("## "):
            out.append((head, "\n".join(buf)))
            head, buf = ln[3:].strip(), []
        else:
            buf.append(ln)
    out.append((head, "\n".join(buf)))
    return out


def narrative_blocks(body: str) -> list[tuple[str | None, str]]:
    """[(ordinal or None, block text)…] split on bold session markers."""
    blocks: list[tuple[str | None, str]] = []
    cur: list[str] = []
    for ln in body.splitlines():
        if ORDINAL.match(ln.lstrip()) and cur and any(c.strip() for c in cur):
            blocks.append((ORDINAL.match("\n".join(cur).lstrip()) and
                           ORDINAL.search("\n".join(cur)).group(1), "\n".join(cur).strip()))
            cur = []
        cur.append(ln)
    if any(c.strip() for c in cur):
        m = ORDINAL.search("\n".join(cur))
        blocks.append((m.group(1) if m else None, "\n".join(cur).strip()))
    return [(o, b) for o, b in blocks if b.strip()]


def bullets(body: str) -> list[str]:
    """Top-level '- ' bullets, each with its continuation lines."""
    out: list[str] = []
    cur: list[str] = []
    for ln in body.splitlines():
        if ln.startswith("- "):
            if cur:
                out.append("\n".join(cur).rstrip())
            cur = [ln]
        elif cur:
            cur.append(ln)
    if cur:
        out.append("\n".join(cur).rstrip())
    return [b for b in out if b.strip()]


def main() -> None:
    proj = pathlib.Path(project_dir() or pathlib.Path(__file__).resolve().parent.parent.parent)
    cfg, _ = load_config(str(proj))
    docs = proj / "docs"
    report_only = "--report" in sys.argv
    out = pathlib.Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else docs
    out.mkdir(parents=True, exist_ok=True)

    state_p, handoff_p, ledger_p = docs / "CURRENT_STATE.md", docs / "HANDOFF_LOG.md", docs / "SESSION_LEDGER.md"
    if not state_p.exists():
        print("migrate-docs-v2: no docs/CURRENT_STATE.md — nothing to migrate")
        sys.exit(0)
    state = state_p.read_text(encoding="utf-8")
    handoff = handoff_p.read_text(encoding="utf-8") if handoff_p.exists() else ""
    sections = split_sections(state)

    # --- 1. narrative -> handoff, joined on ordinal -----------------------
    matched: list[tuple[str, str]] = []
    unmatched: list[str] = []
    for head, body in sections:
        if not any(k in head.lower() for k in NARRATIVE_SECTIONS):
            continue
        for ordinal, block in narrative_blocks(body):
            if ordinal and re.search(r"\b" + ordinal + r"(?:st|nd|rd|th)\b", handoff):
                matched.append((ordinal, block))
            else:
                unmatched.append(block)

    # --- 2. closed ledger lines -> the archive ----------------------------
    moved: list[str] = []
    kept_ledger: list[str] = []
    if ledger_p.exists():
        days = int(cfg["ledger"].get("move_closed_after_days", cfg["ledger"].get("prune_closed_after_days", 7)))
        cutoff = _dt.date.today() - _dt.timedelta(days=days)
        for chunk in re.split(r"\n(?=- \[)", ledger_p.read_text(encoding="utf-8")):
            m = re.match(r"- \[([x-])\]", chunk)
            if not m:
                kept_ledger.append(chunk)
                continue
            dates = re.findall(r"(\d{4}-\d{2}-\d{2})", chunk)
            try:
                newest = max(_dt.date.fromisoformat(d) for d in dates) if dates else None
            except ValueError:
                newest = None
            (moved if newest and newest < cutoff else kept_ledger).append(chunk)

    # --- 3. the triage table (judgement, not the script's) ----------------
    triage: list[tuple[str, str]] = []
    for head, body in sections:
        if any(k in head.lower() for k in TRIAGE_SECTIONS):
            for b in bullets(body):
                triage.append((head, re.sub(r"\s+", " ", b)[:220]))

    print(f"MIGRATION PLAN for {proj.name}")
    print(f"  narrative blocks matched to a handoff line : {len(matched)}")
    print(f"  unmatched (left in place, never guessed)   : {len(unmatched)}")
    print(f"  closed ledger lines to move                : {len(moved)}")
    print(f"  bullets needing YOUR ruling                : {len(triage)}")
    print()
    print("NEEDS A RULING — for each: (K) keep as a standing fact in CURRENT_STATE,")
    print("(L) it is a live loop, make it a ledger item, or (A) archive it to the handoff.")
    print()
    for i, (head, b) in enumerate(triage, 1):
        print(f"{i:3d}. [{head[:18]:<18}] {b}")

    if report_only:
        print("\n--report: nothing written.")
        sys.exit(0)

    # --- 4. write, never replace -----------------------------------------
    keep = [(h, b) for h, b in sections
            if h == "" or any(k in h.lower() for k in KEEP_SECTIONS)]
    new_state = "\n".join(
        (f"## {h}\n{b}".rstrip() if h else b.rstrip()) for h, b in keep
    ).rstrip() + (
        "\n\n## Shipped\n\n<TODO: version per track and where it is — this is new in v2 "
        "and has no v1 source to migrate from.>\n"
        "\n## Shared services\n\n<TODO: from the triage table above, the (K) bullets.>\n"
        "\n## Open loops\n\nSee `docs/SESSION_LEDGER.md`.\n"
    )
    (out / "CURRENT_STATE.new.md").write_text(new_state, encoding="utf-8")

    # Everything leaving CURRENT_STATE lands here VERBATIM — including the
    # sections awaiting a ruling. A bullet that exists only as a truncated line
    # in a console listing has been deleted, whatever the listing calls it.
    # (The first run of this script lost 26,338 characters exactly that way; the
    # conservation check below is what caught it, which is why it is not
    # optional.)
    parked = [(h, b) for h, b in sections if any(k in h.lower() for k in TRIAGE_SECTIONS)]
    archive = handoff.rstrip() + "\n\n---\n\n# Migrated from CURRENT_STATE (v1 → v2)\n\n" + \
        "## Session narrative\n\n" + \
        "\n\n".join(f"<!-- session {o} -->\n{b}" for o, b in matched) + \
        ("\n\n## Parked pending a ruling\n\nMoved out of CURRENT_STATE verbatim. Each bullet is "
         "(K) a standing fact that goes back into CURRENT_STATE, (L) a live loop that becomes a "
         "ledger item, or (A) history that stays here. Until they are ruled on they live here, "
         "because the alternative is that they live nowhere.\n\n"
         + "\n\n".join(f"### {h}\n{b}".rstrip() for h, b in parked) if parked else "") + "\n"
    (out / "HANDOFF_LOG.new.md").write_text(archive, encoding="utf-8")

    # Conservation check. Every character that left CURRENT_STATE must be
    # accounted for in what was written. This is the whole promise of the
    # migration, so it is asserted rather than assumed.
    moved_out = len(state) - len(new_state)
    moved_in = len(archive) - len(handoff)
    slack = moved_out - moved_in
    print(f"\nCONSERVATION: {moved_out:,} chars left CURRENT_STATE, {moved_in:,} arrived in the "
          f"archive (delta {slack:+,}; headers and the v2 skeleton account for a small negative).")
    if slack > 500:
        print(f"  ⚠️  {slack:,} characters are UNACCOUNTED FOR. Do not use this output — "
              "something was dropped rather than moved. Report it.")

    if moved:
        (out / "SESSION_LEDGER_CLOSED.new.md").write_text(
            "# Closed ledger items\n\nMoved out of `SESSION_LEDGER.md` so the file stays "
            "small, kept so every ID cited in a commit subject, a handoff entry or a spine "
            "cell stays resolvable. Never injected. Append-only.\n\n"
            + "\n".join(moved).rstrip() + "\n", encoding="utf-8")
        (out / "SESSION_LEDGER.new.md").write_text("\n".join(kept_ledger).rstrip() + "\n", encoding="utf-8")

    print(f"\nWrote to {out}:")
    for f in sorted(out.glob("*.new.md")):
        print(f"  {f.name}  ({f.stat().st_size:,} bytes)")
    print("\nOriginals untouched. Read these, apply the rulings above, then replace by hand")
    print("and set protocol_version: 2. This script never flips it.")
    if unmatched:
        print(f"\n⚠️  {len(unmatched)} narrative block(s) had no matching handoff line and were "
              "NOT migrated — they are still in the original CURRENT_STATE. Move them by hand; "
              "do not summarize them.")


if __name__ == "__main__":
    main()
