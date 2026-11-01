#!/usr/bin/env python3
"""
The aggregate guard: how big is the payload the model actually receives at
session start — and can it be delivered at all?

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
file path it is not asked to read. A 25,000-char budget sat above that cap for
a month, and every session start on the live project delivered a preview. The
hook now emits the payload in parts (one `--part N` entry each in
settings.json); this script reports the parts too, and fails when a part is
over the harness cap or more parts are needed than entries are wired.

It measures the REAL payload, not a reconstruction — it runs
session-start-context.py in `--measure` mode and reads back the sizes of the
sections and parts that script actually built. Re-deriving the numbers from
the files would be measuring a different artifact than the one that ships,
which is the mistake this whole check exists to catch.

Usage:
    python .claude/scripts/check-payload-budget.py           # report
    python .claude/scripts/check-payload-budget.py --strict  # exit 1 when over or undeliverable
    python .claude/scripts/check-payload-budget.py --json    # machine-readable

Config: `.claude/protocol.json` → `payload.target_chars` (default 25000),
`payload.warn_over` (default 1.0), `payload.part_chars` (default 9000). 25KB
matches the ceiling Claude Code puts on its own auto-loaded MEMORY.md index.

Exits 0 unless --strict and over budget / undeliverable. Never blocks work by
accident.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import (  # noqa: E402
    load_config,
    multi_track,
    project_dir,
    protocol_version,
    track_names,
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


def measure(proj: str) -> list[tuple[int, str]] | None:
    """[(chars, label)…] from the hook itself, or None if it could not run."""
    script = pathlib.Path(__file__).resolve().parent / HOOK
    if not script.exists():
        return None
    env = dict(os.environ, CLAUDE_PROJECT_DIR=proj, PYTHONIOENCODING="utf-8")
    try:
        out = subprocess.run(
            [sys.executable, str(script), "--measure"],
            cwd=proj, capture_output=True, text=True, encoding="utf-8",
            timeout=30, check=False, env=env,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    rows: list[tuple[int, str]] = []
    for ln in out.splitlines():
        size, _, label = ln.partition("\t")
        if size.strip().isdigit() and label:
            rows.append((int(size), label.strip()))
    return rows or None


def dump(proj: str) -> str | None:
    """The assembled payload TEXT from the hook's --dump mode, or None."""
    script = pathlib.Path(__file__).resolve().parent / HOOK
    env = dict(os.environ, CLAUDE_PROJECT_DIR=proj, PYTHONIOENCODING="utf-8")
    try:
        return subprocess.run(
            [sys.executable, str(script), "--dump"],
            cwd=proj, capture_output=True, text=True, encoding="utf-8",
            timeout=30, check=False, env=env,
        ).stdout or None
    except (OSError, subprocess.SubprocessError):
        return None


def handoff_probes(proj: str, cfg: dict) -> list[tuple[str, str]]:
    """(whose, line) pairs a v2 payload must contain: the LAST line of the newest
    handoff entry — normally its Confirm line — per track in a multi-track repo.

    Parsed here on purpose rather than imported from the hook: a check that
    reuses the reader under test agrees with it by construction. Found
    2026-10-28: every v2 payload measured fine on size while carrying only each
    entry's title line, because the size of a section says nothing about
    whether the right text is in it."""
    try:
        lines = (pathlib.Path(proj) / "docs" / "HANDOFF_LOG.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
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

    if not multi_track(cfg):
        return [("newest entry", last_line(titles[-1]))] if titles else []
    probes: list[tuple[str, str]] = []
    for name in track_names(cfg):
        for i in reversed(titles):
            fields = [f.strip() for f in lines[i].split("|")]
            if len(fields) >= 3 and fields[1].lower() == name.lower():
                probes.append((name, last_line(i)))
                break
    return probes


def main() -> None:
    proj = project_dir() or str(pathlib.Path(__file__).resolve().parent.parent.parent)
    cfg, _ = load_config(proj)
    payload_cfg = cfg.get("payload") or {}
    target = int(payload_cfg.get("target_chars", DEFAULT_TARGET))
    warn_over = float(payload_cfg.get("warn_over", 1.0))

    rows = measure(proj)
    if rows is None:
        print("check-payload-budget: could not run the session-start hook, skipped")
        sys.exit(0)

    meta_labels = ("TOTAL", "AVAILABLE_PARTS", "PART_CAP")
    total = next((n for n, label in rows if label == "TOTAL"), 0)
    available = next((n for n, label in rows if label == "AVAILABLE_PARTS"), 0)
    part_cap = next((n for n, label in rows if label == "PART_CAP"), int(payload_cfg.get("part_chars", 9000)))
    parts = [(n, l) for n, l in rows if l.startswith("PART ")]
    sections = sorted(
        ((n, l) for n, l in rows if l not in meta_labels and not l.startswith("PART ")), reverse=True
    )

    over = total > target * warn_over
    oversize_parts = [(n, l) for n, l in parts if n > HARNESS_STRING_CAP]
    legacy_wiring = available == 0
    undelivered = max(len(parts) - available, 0) if not legacy_wiring else 0
    problems: list[str] = []
    if protocol_version(cfg) >= 2:
        probes = handoff_probes(proj, cfg)
        text = dump(proj) if probes else None
        missing = [who for who, line in probes if text is not None and line not in text]
        if missing:
            problems.append(
                "the newest handoff entry is not injected whole (" + ", ".join(missing) + ") — the next "
                "session would get its title without Next / If it fails / Confirm"
            )
    if oversize_parts:
        problems.append(
            "part(s) over the harness's 10,000-char string cap: " + ", ".join(l for _, l in oversize_parts)
        )
    if legacy_wiring and total > HARNESS_STRING_CAP:
        problems.append(
            f"settings.json wires the hook ONCE (no `--part` entries), so a {total:,}-char payload arrives as a "
            "2,000-char preview — resync .claude/settings.json from the template (check-template-drift.py --sync)"
        )
    elif undelivered:
        problems.append(
            f"{len(parts)} parts needed but only {available} `--part` entries wired in settings.json — "
            f"{undelivered} part(s) would not be injected"
        )

    if "--json" in sys.argv:
        print(json.dumps({
            "total_chars": total, "approx_tokens": total // 4, "target_chars": target,
            "over": over,
            "parts": [{"chars": n, "label": l} for n, l in parts],
            "available_parts": available, "part_chars": part_cap,
            "deliverable_ceiling": available * part_cap,
            "undeliverable": bool(problems), "problems": problems,
            "sections": [{"chars": n, "label": l} for n, l in sections],
        }, indent=2))
        sys.exit(1 if ("--strict" in sys.argv and (over or problems)) else 0)

    print(f"Session-start payload: {total:,} chars (~{total // 4:,} tokens) "
          f"against a {target:,}-char budget")
    print()
    for n, label in sections:
        bar = "#" * min(40, round(n / max(target, 1) * 40))
        print(f"  {n:8,}  {bar:<40}  {label}")
    print()
    if legacy_wiring:
        print("Delivery: settings.json wires the hook once (legacy) — one string, capped at 10,000 by Claude Code.")
    else:
        print(f"Delivery: {len(parts)} part(s) of at most {part_cap:,} chars; {available} entries wired "
              f"(deliverable ceiling {available * part_cap:,}).")
        for n, label in parts:
            flag = "  <-- OVER 10,000" if n > HARNESS_STRING_CAP else ""
            print(f"  {n:8,}  {label}{flag}")
    print()

    status = 0
    if problems:
        print("UNDELIVERABLE — " + "; ".join(problems) + ".")
        status = 1
    if over:
        worst = sections[0] if sections else (0, "?")
        pct = round(total / target * 100)
        print(f"OVER BUDGET — {pct}% of target. Largest contributor: {worst[1]} "
              f"({worst[0]:,} chars, {round(worst[0] / max(total, 1) * 100)}% of the payload).")
        print("Shrink the contributor, do not raise the budget: the budget is what stops "
              "the next document growing into the space a capped one vacated.")
        status = 1
    if not status:
        print(f"Within budget ({round(total / max(target, 1) * 100)}% of target) and deliverable.")
    sys.exit(status if "--strict" in sys.argv else 0)


if __name__ == "__main__":
    main()
