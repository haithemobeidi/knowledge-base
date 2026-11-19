#!/usr/bin/env python3
"""
In-place edits to named ledger items — the half of `ledger-archive.py` that
changes an item where it stands instead of moving it out of the file. The CLI
is still `ledger-archive.py` (`--park`, `--unpark`, `--parked`, `--retag`);
this module holds the work.

Why a separate file: the two halves have different safety contracts. The
moves (closed lines to SESSION_LEDGER_CLOSED.md, kbdoc items to the lessons
queue) refuse a ledger with uncommitted changes and balance their line count,
because they rewrite the whole file. These edits touch named lines only and
must run during /end, when the ledger always has this session's own changes.

Parking. An open loop no session can act on until a named event (a lock
lifting, a release) is PARKED: `[~]` plus a line `→ PARKED <date> until
<event>`. Parked items are not listed at session start — they are counted,
grouped by the event — so they stop costing every session a title. When the
event happens, the session that sees it unparks them. One project had most of
its 122 open items waiting on a single ruling, every one of them loaded by
every session for six weeks.

Retagging. `--retag IDS --to TRACKS` rewrites who acts on open or parked
items: the `→` tag right after the ID (or after the provenance parenthetical,
where the start hook also reads it) becomes `→<tracks>`, and one dated line
under the ID records what it was. Track names are checked against
protocol.json — strictly, unlike the start hook, which reads an unknown word
as "all" so nothing is ever hidden; a typo here would silently send an item to
everyone. `all` is refused: naming the tracks is the point (an item every
track loads is what put one project 30% over its budget). Checkpoint's
2026-11-18 cleanup retagged 35 `→all` items with a one-off script; this is
that script.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import item_targets, prefix_map, track_aliases, track_names  # noqa: E402


def _item_end(lines: list[str], i: int) -> int:
    """One past the last line of the item starting at `i` — the same extent the
    start hook reads as one item — without its trailing blank lines."""
    j = i + 1
    while j < len(lines) and not lines[j].startswith(("- [", "#", "<!--", "```", "~~~")):
        j += 1
    while j > i + 1 and not lines[j - 1].strip():
        j -= 1
    return j


PARKED_LINE = re.compile(r"(?:→|->)\s*PARKED\b[^\n]*?\buntil\b\s*(\S.*)", re.IGNORECASE)
# The notes this script writes under an item's ID line; a new one goes after them.
NOTE_LINE = re.compile(r"\s*(?:→|->)\s*(?:(?:UN)?PARKED|RETAGGED)\b")


def list_parked(ledger: pathlib.Path) -> None:
    lines = ledger.read_text(encoding="utf-8").split("\n")
    groups: dict[str, list[str]] = {}
    for i, ln in enumerate(lines):
        m = re.match(r"- \[~\] ([A-Za-z]{1,4}-\d+)", ln)
        if not m:
            continue
        hits = [p.group(1) for p in (PARKED_LINE.search(x) for x in lines[i:_item_end(lines, i)]) if p]
        event = re.split(r"[.;](?:\s|$)", hits[-1].strip())[0] if hits else "(no event named — name one)"
        title = re.search(r"\*\*(.+?)\*\*", ln)
        groups.setdefault(event, []).append(f"{m.group(1)}  {(title.group(1) if title else ln[6:])[:100]}")
    if not groups:
        print("No parked items.")
        sys.exit(0)
    for event, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(f"until {event} — {len(items)}:")
        for it in items:
            print(f"  {it}")
    print("\nUnpark the items whose event has happened: --unpark ID,ID --because \"…\" --apply")
    sys.exit(0)


def park(ledger: pathlib.Path, ids: str, unpark: bool, apply: bool,
         until: str = "", because: str = "") -> None:
    """`--park IDS --until EVENT` / `--unpark IDS [--because WHY]`: flip the
    checkbox and add one dated line saying why. Nothing else in the item is
    touched.

    The note goes right under the ID line (after any earlier PARKED/UNPARKED
    notes), not at the end of the item: the start hook reads an item only up
    to its first nested `- [ ]` child, so a note after the children was
    invisible to it while the gate saw it. `--park` on an item that is already
    parked adds a fresh note — that is how one parked without an event gets
    one. Unlike the archive move, this does not refuse a ledger with
    uncommitted changes: during /end it always has them (this session's own),
    and the edit is to named lines only."""
    until, because = until.strip(), because.strip()
    if not unpark and not until:
        print('ledger-archive --park: say what the items wait for: --until "<event>". A parked item that names '
              "no event is never woken up, and the budget gate stops a wrap on one.")
        sys.exit(1)
    want = {x.strip().upper() for x in ids.split(",") if x.strip()}
    src, dst = ("- [~]", "- [ ]") if unpark else ("- [ ]", "- [~]")
    today = _dt.date.today().isoformat()
    raw = ledger.read_bytes()
    lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
    out: list[str] = []
    done: list[str] = []
    other: list[str] = []
    in_comment = False
    i = 0
    while i < len(lines):
        ln = lines[i]
        if in_comment:
            in_comment = "-->" not in ln
        elif "<!--" in ln and "-->" not in ln[ln.rindex("<!--"):]:
            in_comment = True
        m = None if in_comment else re.match(r"- \[(.)\] ([A-Za-z]{1,4}-\d+)\b", ln)
        if m and m.group(2).upper() in want:
            if ln.startswith(src) or (not unpark and ln.startswith("- [~]")):
                j = _item_end(lines, i)
                block = lines[i:j]
                block[0] = dst + block[0][5:]
                k = 1
                while k < len(block) and NOTE_LINE.match(block[k]):
                    k += 1
                note = (f"  → UNPARKED {today}" + (f": {because}" if because else "")) if unpark \
                    else f"  → PARKED {today} until {until}"
                out.extend(block[:k] + [note] + block[k:])
                done.append(m.group(2))
                i = j
                continue
            other.append(f"{m.group(2)} is [{m.group(1)}]")
        out.append(ln)
        i += 1
    missing = sorted(want - {d.upper() for d in done} - {o.split()[0].upper() for o in other})
    verb = "unpark" if unpark else "park"
    print(f"{len(done)} item(s) would {verb}: {', '.join(done) or 'none'}"
          + ("" if unpark else f" — until {until}"))
    if other:
        print("  left alone (not " + ("parked" if unpark else "open or parked") + "): " + ", ".join(other))
    if missing:
        print("  not found in the ledger: " + ", ".join(missing))
    if not apply or not done:
        print("\nDry run. Pass --apply to write it." if done else "\nNothing to do.")
        sys.exit(0)
    nl = "\r\n" if b"\r\n" in raw else "\n"
    ledger.write_bytes(nl.join(out).encode("utf-8"))
    print(f"\nDone. Commit docs/SESSION_LEDGER.md.")
    sys.exit(0)


def _tag_end(s: str, k: int, aliases: dict[str, str]) -> int:
    """Where the tag list that starts at s[k] (just past the arrow) ends — the
    same names and separators `protocol_config.resolve_tags` reads. A word that
    is no track (`→both`) is taken whole, since it is the tag being replaced; a
    word after "and" is left alone, since that is more likely the title."""
    names = sorted(list(aliases) + ["all"], key=len, reverse=True)
    j = k
    while True:
        hit = next((a for a in names if re.match(re.escape(a) + r"(?![\w-])", s[j:], re.IGNORECASE)), None)
        if hit is None:
            word = re.match(r"[\w-]+", s[j:])
            return j + (word.end() if word else 0)
        j += len(hit)
        more = re.match(r"\s*(?:[/,+&]|and\b)\s*(?:→|->)?\s*", s[j:])
        if not more:
            return j
        if "and" in more.group(0) and not any(
                re.match(re.escape(a) + r"(?![\w-])", s[j + more.end():], re.IGNORECASE) for a in names):
            return j
        j += more.end()


def retag_line(line: str, tag: str, aliases: dict[str, str]) -> tuple[str, str | None]:
    """The item's first line with its tag replaced by `→<tag>`, and the old
    tag (None when it had none). Reads the tag where `item_targets` does:
    right after the ID, else right after the provenance parenthetical. With
    no tag, the new one goes right after the ID, the documented place."""
    head = re.match(r"(- \[.\] [A-Za-z]{1,4}-\d+)(\s*)", line)
    assert head
    rest_at = head.end()
    spans: list[int] = []
    arrow = re.match(r"(?:→|->)\s*", line[rest_at:])
    if arrow:
        spans = [rest_at, rest_at + arrow.end()]
    elif line[rest_at:].startswith("("):
        depth = 0
        for p in range(rest_at, len(line)):
            depth += line[p] == "("
            depth -= line[p] == ")"
            if depth == 0:
                q = p + 1
                q += len(line[q:]) - len(line[q:].lstrip())
                arrow = re.match(r"(?:→|->)\s*", line[q:])
                if arrow:
                    spans = [q, q + arrow.end()]
                break
    if spans:
        end = _tag_end(line, spans[1], aliases)
        return line[:spans[0]] + "→" + tag + line[end:], line[spans[0]:end].strip()
    rest = line[rest_at:]
    return head.group(1) + " →" + tag + (" " + rest if rest else ""), None


def retag(ledger: pathlib.Path, cfg: dict, ids: str, apply: bool,
          to: str = "", because: str = "") -> None:
    """`--retag IDS --to TRACKS [--because WHY]`: give open or parked items a
    new `→` tag and one dated note under the ID line saying what it was.
    Like parking, it does not refuse a ledger with uncommitted changes — it
    edits named lines only."""
    aliases = track_aliases(cfg)
    if len(track_names(cfg)) < 2:
        print("ledger-archive --retag: this project declares fewer than two tracks, so there is no one else to "
              "hand an item to. Tags only mean something in a multi-track project.")
        sys.exit(1)
    raw_to = to.strip()
    words = [w for w in re.split(r"\s*(?:[/,+&]|\band\b)\s*", raw_to.lstrip("→->").strip()) if w]
    if not words:
        print('ledger-archive --retag: say who acts on them: --to desktop  (several: --to android/ios). '
              "Declared tracks: " + ", ".join(track_names(cfg)))
        sys.exit(1)
    if any(w.lower() == "all" for w in words):
        print("ledger-archive --retag: name the tracks that must act, not `all` — an item every track loads is "
              "what this replaces. If every track really must act, name them all: --to " + "/".join(track_names(cfg)))
        sys.exit(1)
    unknown = [w for w in words if w.lower() not in aliases]
    if unknown:
        print(f"ledger-archive --retag: not a declared track: {', '.join(unknown)}. "
              "Declared (protocol.json → tracks): " + ", ".join(track_names(cfg)))
        sys.exit(1)
    chosen = {aliases[w.lower()] for w in words}
    tag = "/".join(n for n in track_names(cfg) if n in chosen)
    because = because.strip()
    writers = prefix_map(cfg)
    want = {x.strip().upper() for x in ids.split(",") if x.strip()}
    today = _dt.date.today().isoformat()
    raw = ledger.read_bytes()
    lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
    out: list[str] = []
    done: list[str] = []
    same: list[str] = []
    unsure: list[str] = []
    other: list[str] = []
    in_comment = False
    i = 0
    while i < len(lines):
        ln = lines[i]
        if in_comment:
            in_comment = "-->" not in ln
        elif "<!--" in ln and "-->" not in ln[ln.rindex("<!--"):]:
            in_comment = True
        m = None if in_comment else re.match(r"- \[(.)\] ([A-Za-z]{1,4})-(\d+)\b", ln)
        item_id = f"{m.group(2)}-{m.group(3)}".upper() if m else ""
        if m and item_id in want:
            if m.group(1) not in (" ", "~"):
                other.append(f"{item_id} is [{m.group(1)}]")
            else:
                now = item_targets(ln, aliases)
                if now is None:
                    writer = writers.get(m.group(2)) or writers.get(m.group(2).upper())
                    now = {writer} if writer else {"all"}
                new_first, old = retag_line(ln, tag, aliases)
                if now == chosen:
                    same.append(item_id)
                elif item_targets(new_first, aliases) != chosen:
                    # e.g. "→desktop and then …": the start hook reads the word
                    # after "and" as a track, fails open to all, and would go
                    # on doing so whatever this wrote.
                    unsure.append(item_id)
                else:
                    j = _item_end(lines, i)
                    block = lines[i:j]
                    block[0] = new_first
                    k = 1
                    while k < len(block) and NOTE_LINE.match(block[k]):
                        k += 1
                    note = (f"  → RETAGGED {today} from {old or 'no tag'} to →{tag}"
                            + (f": {because}" if because else ""))
                    out.extend(block[:k] + [note] + block[k:])
                    done.append(f"{item_id} {old or '(no tag)'} → →{tag}")
                    i = j
                    continue
        out.append(ln)
        i += 1
    found = {d.split()[0] for d in done} | set(same) | set(unsure) | {o.split()[0] for o in other}
    missing = sorted(want - found)
    print(f"{len(done)} item(s) would be retagged:" if done else "No item would be retagged.")
    for d in done:
        print(f"  {d}")
    if same:
        print("  already for exactly that: " + ", ".join(same))
    if unsure:
        print("  left alone — the start hook would not read the new tag as written, because of the words after it; "
              "edit the first line by hand (tag right after the ID, then the parenthetical): " + ", ".join(unsure))
    if other:
        print("  left alone (closed): " + ", ".join(other))
    if missing:
        print("  not found in the ledger: " + ", ".join(missing))
    if not apply or not done:
        print("\nDry run. Pass --apply to write it." if done else "\nNothing to do.")
        sys.exit(0)
    nl = "\r\n" if b"\r\n" in raw else "\n"
    ledger.write_bytes(nl.join(out).encode("utf-8"))
    print("\nDone. Commit docs/SESSION_LEDGER.md.")
    sys.exit(0)
