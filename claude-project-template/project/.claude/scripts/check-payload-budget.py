#!/usr/bin/env python3
"""
The aggregate guard: how big is the payload the model actually receives at
session start?

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

It measures the REAL payload, not a reconstruction — it runs
session-start-context.py in `--measure` mode and reads back the sizes of the
sections that script actually built. Re-deriving the numbers from the files
would be measuring a different artifact than the one that ships, which is the
mistake this whole check exists to catch.

Usage:
    python .claude/scripts/check-payload-budget.py           # report
    python .claude/scripts/check-payload-budget.py --strict  # exit 1 when over
    python .claude/scripts/check-payload-budget.py --json    # machine-readable

Config: `.claude/protocol.json` → `payload.target_chars` (default 25000) and
`payload.warn_over` (default 1.0). 25KB matches the ceiling Claude Code puts on
its own auto-loaded MEMORY.md index.

Exits 0 unless --strict and over budget. Never blocks work by accident.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
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


DEFAULT_TARGET = 25000
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

    total = next((n for n, label in rows if label == "TOTAL"), 0)
    sections = sorted(((n, l) for n, l in rows if l != "TOTAL"), reverse=True)

    if "--json" in sys.argv:
        print(json.dumps({
            "total_chars": total, "approx_tokens": total // 4, "target_chars": target,
            "over": total > target * warn_over,
            "sections": [{"chars": n, "label": l} for n, l in sections],
        }, indent=2))
        sys.exit(1 if ("--strict" in sys.argv and total > target * warn_over) else 0)

    print(f"Session-start payload: {total:,} chars (~{total // 4:,} tokens) "
          f"against a {target:,}-char budget")
    print()
    for n, label in sections:
        bar = "#" * min(40, round(n / max(target, 1) * 40))
        print(f"  {n:8,}  {bar:<40}  {label}")
    print()

    if total > target * warn_over:
        worst = sections[0] if sections else (0, "?")
        pct = round(total / target * 100)
        print(f"OVER BUDGET — {pct}% of target. Largest contributor: {worst[1]} "
              f"({worst[0]:,} chars, {round(worst[0] / max(total, 1) * 100)}% of the payload).")
        print("Shrink the contributor, do not raise the budget: the budget is what stops "
              "the next document growing into the space a capped one vacated.")
        sys.exit(1 if "--strict" in sys.argv else 0)

    print(f"Within budget ({round(total / max(target, 1) * 100)}% of target).")
    sys.exit(0)


if __name__ == "__main__":
    main()
