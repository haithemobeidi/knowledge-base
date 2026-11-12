#!/usr/bin/env python3
"""
The aggregate guard: how big is the payload a session actually receives at
start — can it be delivered at all — and, at `/end`, the GATE that stops a wrap
which would make it bigger than it is allowed to be.

Why this exists. Every other cap in this protocol measures ONE input on disk —
a ledger item, a spine cell, a handoff line. None of them measures the assembled
payload, and that turned out to be the only number that matters. On 2026-09-08
the ledger caps landed and worked: the ledger fell from 397KB to 259KB and
stayed down. The mass moved to the one adjacent document with no cap.
CURRENT_STATE.md was 5,968 characters that day; twelve days later it was 92,900,
and the session-start injection was 163,478 characters — about 41,000 tokens,
roughly five times a normal full Claude Code startup payload. Nobody saw it,
because the metric everyone was watching had improved.

So: a per-contributor cap relocates bloat, it does not remove it. Measure the
total the consumer receives.

Delivery is the second half, found 2026-10-19. Claude Code caps ONE hook string
at 10,000 characters; over it, the model gets a 2,000-character preview and a
file path it is not asked to read. The hook emits the payload in parts (one
`--part N` entry each in settings.json); this script reports the parts too, and
fails when a part is over the harness cap or more parts are needed than entries
are wired.

The gate is the third half, found 2026-11-12. This script REPORTED for seven
weeks and the payload on the live project went from 53,000 to 77,000 characters
against a 25,000 budget while it did: every wrap printed "OVER BUDGET", trimmed
a little by hand when delivery broke, and twice the number of wired parts was
raised instead. A check that cannot fail is a notice. So `/end` runs this with
`--strict`, and a wrap over its limit stops.

The limit is the budget (`payload.target_chars`) — or, for a payload that was
already over the budget on the day the gate arrived, a CEILING recorded in
`protocol.json` → `payload.ceiling_chars`. The ceiling is a ratchet: it is set
once at the current size (`--init-ceiling`, which works only on the day the
project adopts the gate), every wrap that ends smaller lowers it (`--ratchet`),
and nothing in this script ever raises it. A project that is
300% over is therefore not locked out of wrapping on day one; it is locked out
of growing, and it gets under the budget by never being allowed back up.

What is measured. A v2 project with two or more tracks loads BY TRACK (see
session-start-context.py, module doc 7), so each track's session has its own
payload — the hook's core plus that track's `--track` load — and its own limit.
Every other project has one payload, keyed "project".

It measures the REAL payload, not a reconstruction — it runs
session-start-context.py in `--measure` mode and reads back the sizes of the
sections and parts that script actually built. Re-deriving the numbers from
the files would be measuring a different artifact than the one that ships,
which is the mistake this whole check exists to catch.

Usage:
    python .claude/scripts/check-payload-budget.py                    # report
    python .claude/scripts/check-payload-budget.py --strict --ratchet # the /end gate
    python .claude/scripts/check-payload-budget.py --init-ceiling     # once, at adoption (check-template-drift.py runs it)
    python .claude/scripts/check-payload-budget.py --json             # machine-readable

Exits 0 unless --strict and a payload is over its limit or undeliverable.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import (  # noqa: E402
    CONFIG_REL_PATH,
    load_config,
    multi_track,
    payload_keys,
    payload_limit,
    project_dir,
    protocol_version,
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


DEFAULT_TARGET = 25000
HARNESS_STRING_CAP = 10000
HOOK = "session-start-context.py"
META_LABELS = ("TOTAL", "AVAILABLE_PARTS", "PART_CAP")


def _hook(proj: str, mode: str, key: str) -> str | None:
    """stdout of the hook in `--measure` or `--dump` mode for one payload."""
    script = pathlib.Path(__file__).resolve().parent / HOOK
    if not script.exists():
        return None
    env = dict(os.environ, CLAUDE_PROJECT_DIR=proj, PYTHONIOENCODING="utf-8")
    cmd = [sys.executable, str(script), mode] + ([] if key == "project" else ["--track", key])
    try:
        return subprocess.run(
            cmd, cwd=proj, capture_output=True, text=True, encoding="utf-8",
            timeout=30, check=False, env=env,
        ).stdout or None
    except (OSError, subprocess.SubprocessError):
        return None


def measure(proj: str, key: str) -> list[tuple[int, str]] | None:
    """[(chars, label)…] from the hook itself, or None if it could not run."""
    out = _hook(proj, "--measure", key)
    rows: list[tuple[int, str]] = []
    for ln in (out or "").splitlines():
        size, _, label = ln.partition("\t")
        if size.strip().isdigit() and label:
            rows.append((int(size), label.strip()))
    return rows or None


def handoff_probe(proj: str, key: str) -> str | None:
    """The LAST line of the newest handoff entry — normally its Confirm line —
    for one payload: the newest entry overall, or the newest for a track.

    Parsed here on purpose rather than imported from the hook: a check that
    reuses the reader under test agrees with it by construction. Found
    2026-10-28: every v2 payload measured fine on size while carrying only each
    entry's title line, because the size of a section says nothing about
    whether the right text is in it."""
    try:
        lines = (pathlib.Path(proj) / "docs" / "HANDOFF_LOG.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    titles: list[int] = []
    fenced = False
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("```"):
            fenced = not fenced
        elif not fenced and s.startswith("## ") and "|" in s:
            titles.append(i)

    def last_line(i: int) -> str:
        j = i + 1
        while j < len(lines) and not lines[j].startswith(("# ", "## ")):
            j += 1
        body = [ln.strip() for ln in lines[i + 1:j] if ln.strip() not in ("", "---")]
        return body[-1] if body else lines[i].strip()

    if key == "project":
        return last_line(titles[-1]) if titles else None
    for i in reversed(titles):
        fields = [f.strip() for f in lines[i].split("|")]
        if len(fields) >= 3 and fields[1].lower() == key.lower():
            return last_line(i)
    return None


def open_ledger_ids(proj: str) -> list[str]:
    """Every open item's ID, read straight from the ledger (independently of the
    hook's own parser, for the same reason as handoff_probe)."""
    try:
        text = (pathlib.Path(proj) / "docs" / "SESSION_LEDGER.md").read_text(encoding="utf-8")
    except OSError:
        return []
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return re.findall(r"^\s*- \[ \] ([A-Za-z]{1,4}-\d+)\b", text, flags=re.MULTILINE)


def ceiling_for(total: int) -> int:
    """Where a ceiling sits for a payload of this size: 500 to 1,000 characters
    above it. That is two to four ledger titles of room — enough that a wrap
    which queued one real item is not stopped at the door, small enough that
    the payload cannot drift."""
    return ((total + 500 + 499) // 500) * 500


def write_ceilings(proj: str, ceilings: dict[str, int]) -> bool:
    """Set `payload.ceiling_chars` in protocol.json and touch nothing else.

    The file is hand-edited and laid out for reading (blank lines between key
    groups, long `$comment` strings), so the value is spliced into the TEXT and
    the result is accepted only if it parses to exactly the old content plus
    the new value. A full JSON re-serialisation — which drops the blank lines
    and normalises line endings — is the fallback, not the default. The key is
    always written, even empty: its presence is what records that this project
    has adopted the gate (see --init-ceiling)."""
    path = pathlib.Path(proj) / CONFIG_REL_PATH
    try:
        text = path.read_bytes().decode("utf-8")
        raw = json.loads(text)
    except (OSError, ValueError):
        return False
    if not isinstance(raw, dict):
        return False
    want = json.loads(json.dumps(raw))
    if not isinstance(want.get("payload"), dict):
        want["payload"] = {}
    want["payload"]["ceiling_chars"] = ceilings
    nl = "\r\n" if "\r\n" in text else "\n"

    def render(indent: str) -> str:
        if not ceilings:
            return "{}"
        rows = [f"{indent}  {json.dumps(k, ensure_ascii=False)}: {int(v)}" for k, v in ceilings.items()]
        return "{" + nl + ("," + nl).join(rows) + nl + indent + "}"

    new_text = None
    existing = re.search(
        r'^([ \t]*)"ceiling_chars"\s*:\s*(\{[^{}]*\}|null|\[[^\[\]]*\]|"[^"]*"|-?\d+)', text, re.MULTILINE
    )
    if existing:
        new_text = text[:existing.start(2)] + render(existing.group(1)) + text[existing.end(2):]
    else:
        block = re.search(r'^([ \t]*)"payload"\s*:\s*\{([^{}]*)\}', text, re.MULTILINE)
        if block:
            indent = block.group(1) + "  "
            body = block.group(2).rstrip()
            comma = "," if body.strip() else ""
            new_text = (text[:block.start(2)] + body + comma + nl + indent + '"ceiling_chars": '
                        + render(indent) + nl + block.group(1) + text[block.end(2):])
    try:
        if new_text is None or json.loads(new_text) != want:
            new_text = json.dumps(want, indent=2, ensure_ascii=False) + "\n"
        path.write_bytes(new_text.encode("utf-8"))
        return True
    except (OSError, ValueError):
        return False


def main() -> None:
    proj = project_dir() or str(pathlib.Path(__file__).resolve().parent.parent.parent)
    cfg, cfg_exists = load_config(proj)
    payload_cfg = cfg.get("payload") or {}
    target = int(payload_cfg.get("target_chars", DEFAULT_TARGET))
    # `payload.warn_over` softens the hook's printed warning only. The gate
    # does not read it: a multiplier on the limit would be a way to raise the
    # budget that leaves no trace in `ceiling_chars`.
    strict = "--strict" in sys.argv
    v2 = protocol_version(cfg) >= 2
    by_track = v2 and multi_track(cfg)

    payloads: list[dict] = []
    for key in payload_keys(cfg):
        rows = measure(proj, key)
        if rows is None:
            # A gate that cannot measure has not passed. (Reporting mode stays
            # quiet, as every script here does on a failure path.)
            print("check-payload-budget: could not run the session-start hook"
                  + (f" for {key}" if key != "project" else "")
                  + (" — the payload is UNMEASURED, so the gate does not pass." if strict else ", skipped"))
            sys.exit(1 if strict else 0)
        total = next((n for n, label in rows if label == "TOTAL"), 0)
        payloads.append({
            "key": key,
            "total": total,
            "limit": payload_limit(cfg, key),
            "available": next((n for n, label in rows if label == "AVAILABLE_PARTS"), 0),
            "part_cap": next((n for n, label in rows if label == "PART_CAP"),
                             int(payload_cfg.get("part_chars", 9000))),
            "parts": [(n, l) for n, l in rows if l.startswith("PART ")],
            "sections": sorted(
                ((n, l) for n, l in rows if l not in META_LABELS and not l.startswith("PART ")), reverse=True
            ),
        })
    for p in payloads:
        p["over_target"] = p["total"] > target
        p["over_limit"] = p["total"] > p["limit"]

    # Delivery — the hook's own strings. Identical for every track (the hook
    # delivers the same core whichever track the session turns out to be on).
    first = payloads[0]
    parts, available, part_cap = first["parts"], first["available"], first["part_cap"]
    hook_total = sum(n for n, _ in parts) if by_track else first["total"]
    oversize_parts = [(n, l) for n, l in parts if n > HARNESS_STRING_CAP]
    legacy_wiring = available == 0
    undelivered = max(len(parts) - available, 0) if not legacy_wiring else 0
    problems: list[str] = []
    if v2:
        dumps = {p["key"]: _hook(proj, "--dump", p["key"]) for p in payloads}
        missing = [
            p["key"] for p in payloads
            if (probe := handoff_probe(proj, p["key"])) and dumps[p["key"]] is not None
            and probe not in dumps[p["key"]]
        ]
        if missing:
            problems.append(
                "the newest handoff entry is not loaded whole (" + ", ".join(missing) + ") — the next "
                "session would get its title without Next / If it fails / Confirm"
            )
        if by_track and all(d is not None for d in dumps.values()):
            # Presence across the views: a session sees only its own track's
            # items, so an item no view shows has vanished from every session.
            # Only the ledger sections count: a `- D-24 …` bullet quoted in
            # CURRENT_STATE or a handoff entry is not the item being loaded.
            seen = "\n".join(
                sec for d in dumps.values() for sec in re.split(r"\n(?=### )", d or "")
                if sec.startswith("### docs/SESSION_LEDGER.md")
            )
            lost = [
                i for i in open_ledger_ids(proj)
                if not re.search(r"(?m)^(?:- |▶ )" + re.escape(i) + r"\b", seen)
            ]
            if lost:
                problems.append(
                    f"{len(lost)} open ledger item(s) are loaded by NO track's session: "
                    + ", ".join(lost[:15]) + (" …" if len(lost) > 15 else "")
                )
    if oversize_parts:
        problems.append(
            "part(s) over the harness's 10,000-char string cap: " + ", ".join(l for _, l in oversize_parts)
        )
    if legacy_wiring and hook_total > HARNESS_STRING_CAP:
        problems.append(
            f"settings.json wires the hook ONCE (no `--part` entries), so a {hook_total:,}-char hook payload "
            "arrives as a 2,000-char preview — resync .claude/settings.json from the template "
            "(check-template-drift.py --sync)"
        )
    elif undelivered:
        problems.append(
            f"{len(parts)} parts needed but only {available} `--part` entries wired in settings.json — "
            f"{undelivered} part(s) would not be injected"
        )

    # The ratchet. Ceilings are created only by --init-ceiling, lowered only by
    # --ratchet, and never raised here.
    raw_ceilings = payload_cfg.get("ceiling_chars")
    ceilings: dict[str, int] = {}
    for k, v in (raw_ceilings.items() if isinstance(raw_ceilings, dict) else []):
        try:
            ceilings[str(k)] = int(v)
        except (TypeError, ValueError):
            pass  # an unreadable ceiling is no ceiling: that payload is held to the budget
    changes: list[str] = []
    new_ceilings = dict(ceilings)
    # --init-ceiling works ONCE per project: on the day it adopts the gate,
    # which is the day protocol.json gains the `ceiling_chars` key. After that
    # a payload with no ceiling is held to the budget itself, and running this
    # again cannot hand an over-budget payload a fresh ceiling at its new size.
    # Presence of the key, whatever its value: a hand-edited `null` or `[]` is
    # still an adopted project, not an invitation to adopt again at a new size.
    adopted = "ceiling_chars" in payload_cfg
    init = "--init-ceiling" in sys.argv and not adopted
    if "--init-ceiling" in sys.argv and adopted:
        print("--init-ceiling: this project adopted the gate already (`payload.ceiling_chars` exists in "
              "protocol.json); nothing set. A ceiling is never created or raised after that day except by "
              "the user's decision, by hand, with a DECISIONS.md entry.")
        print()
    if init:
        for p in payloads:
            if p["over_target"] and p["key"] not in new_ceilings:
                new_ceilings[p["key"]] = ceiling_for(p["total"])
                changes.append(f"{p['key']}: ceiling set at {new_ceilings[p['key']]:,} (payload {p['total']:,})")
    if "--ratchet" in sys.argv or init:
        live = {p["key"] for p in payloads}
        for k in [k for k in new_ceilings if k not in live]:
            # A renamed or removed track: its ceiling must not wait for some
            # later track of the same name to inherit.
            changes.append(f"{k}: no such payload any more — ceiling of {new_ceilings.pop(k):,} dropped")
        for p in payloads:
            had = new_ceilings.get(p["key"])
            if had is None or p["key"] not in ceilings:
                continue
            if not p["over_target"]:
                del new_ceilings[p["key"]]
                changes.append(f"{p['key']}: inside the budget — ceiling of {had:,} removed")
            elif ceiling_for(p["total"]) < had:
                new_ceilings[p["key"]] = ceiling_for(p["total"])
                changes.append(f"{p['key']}: ceiling lowered {had:,} → {new_ceilings[p['key']]:,}")
    wrote = False
    if (new_ceilings != ceilings or init) and cfg_exists:
        wrote = write_ceilings(proj, new_ceilings)
        if wrote:
            for p in payloads:
                p["limit"] = max(target, int(new_ceilings.get(p["key"], 0)))
                p["over_limit"] = p["total"] > p["limit"]

    over_limit = [p for p in payloads if p["over_limit"]]
    failed = bool(problems or over_limit)

    if "--json" in sys.argv:
        worst = max(payloads, key=lambda p: p["total"])
        print(json.dumps({
            "total_chars": worst["total"], "approx_tokens": worst["total"] // 4, "target_chars": target,
            "over": worst["over_target"], "over_limit": bool(over_limit),
            "payloads": [
                {"key": p["key"], "total_chars": p["total"], "limit_chars": p["limit"],
                 "over_target": p["over_target"], "over_limit": p["over_limit"],
                 "sections": [{"chars": n, "label": l} for n, l in p["sections"]]}
                for p in payloads
            ],
            "parts": [{"chars": n, "label": l} for n, l in parts],
            "available_parts": available, "part_chars": part_cap,
            "deliverable_ceiling": available * part_cap,
            "undeliverable": bool(problems), "problems": problems,
            "ceiling_changes": changes if wrote else [],
            "sections": [{"chars": n, "label": l} for n, l in worst["sections"]],
        }, indent=2))
        sys.exit(1 if (strict and failed) else 0)

    def show_sections(p: dict) -> None:
        for n, label in p["sections"]:
            bar = "#" * min(40, round(n / max(target, 1) * 40))
            print(f"  {n:8,}  {bar:<40}  {label}")

    def state(p: dict) -> str:
        if p["over_limit"]:
            return "OVER ITS LIMIT"
        if p["over_target"]:
            return "over budget, inside its ceiling"
        return "ok"

    if by_track:
        print(f"Session-start payload per track (the start hook + that track's `--track` load), "
              f"against a {target:,}-char budget:")
        print()
        for p in payloads:
            lim = f"limit {p['limit']:,}" if p["limit"] > target else "limit = budget"
            print(f"  {p['total']:8,}  {round(p['total'] / max(target, 1) * 100):4}%  {p['key']:<14} {lim:<16} {state(p)}")
        print()
        # One breakdown, not one per track: the largest that is over its limit
        # (else the largest). `--all` prints every track's.
        pick = max(over_limit or payloads, key=lambda q: q["total"])
        for p in (payloads if "--all" in sys.argv else [pick]):
            print(f"What track {p['key']} loads:")
            show_sections(p)
            print()
    else:
        p = payloads[0]
        print(f"Session-start payload: {p['total']:,} chars (~{p['total'] // 4:,} tokens) "
              f"against a {target:,}-char budget"
              + (f" (ceiling {p['limit']:,})" if p["limit"] > target else ""))
        print()
        show_sections(p)
        print()
    if legacy_wiring:
        print("Delivery: settings.json wires the hook once (legacy) — one string, capped at 10,000 by Claude Code.")
    else:
        print(f"Delivery: {len(parts)} hook part(s) of at most {part_cap:,} chars; {available} entries wired "
              f"(deliverable ceiling {available * part_cap:,}).")
        for n, label in parts:
            flag = "  <-- OVER 10,000" if n > HARNESS_STRING_CAP else ""
            print(f"  {n:8,}  {label}{flag}")
    print()
    for c in changes if wrote else []:
        print(f"Ceiling: {c}  (.claude/protocol.json — commit it with the wrap)")
    if changes and not wrote:
        print("Ceiling: could not write .claude/protocol.json — nothing recorded.")

    if problems:
        print("UNDELIVERABLE — " + "; ".join(problems) + ".")
    for p in payloads:
        if not p["over_target"]:
            continue
        worst = p["sections"][0] if p["sections"] else (0, "?")
        who = f"track {p['key']}" if by_track else "the payload"
        pct = round(p["total"] / target * 100)
        if p["over_limit"]:
            if p["limit"] > target:
                why = f"it has grown past its ceiling of {p['limit']:,} by {p['total'] - p['limit']:,} chars"
            else:
                why = f"it is {p['total'] - target:,} chars over the budget" + (
                    "" if adopted else
                    " and this project has not adopted the gate yet (check-template-drift.py --adopt sets a "
                    "ceiling at today's size, once)")
            print(f"OVER ITS LIMIT — {who}: {p['total']:,} chars, {pct}% of the budget; {why}. "
                  f"Largest contributor: {worst[1]} ({worst[0]:,} chars).")
        else:
            print(f"OVER BUDGET, inside its ceiling — {who}: {p['total']:,} chars, {pct}% of the budget, "
                  f"ceiling {p['limit']:,}. Largest contributor: {worst[1]} ({worst[0]:,} chars).")
    if over_limit:
        print()
        print("A wrap must not leave a payload over its limit. Shrink what this session added, then rerun:")
        print("  - ledger: close what is done; move ideas to the backlog, lessons to docs/LESSONS_QUEUE.md,")
        print("    standing facts to DECISIONS.md or CURRENT_STATE — an open loop is the only thing that earns an ID")
        print("  - CURRENT_STATE: app state only; narrative belongs in the handoff entry, which costs nothing here")
        print("  - never by raising target_chars or a ceiling: that is the user's decision, recorded in DECISIONS.md")
    elif not failed and not any(p["over_target"] for p in payloads):
        worst = max(payloads, key=lambda q: q["total"])
        print(f"Within budget ({round(worst['total'] / max(target, 1) * 100)}% of target"
              + (" at the largest track" if by_track else "") + ") and deliverable.")
    sys.exit(1 if (strict and failed) else 0)


if __name__ == "__main__":
    main()
