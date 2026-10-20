#!/usr/bin/env python3
"""
SessionStart hook: loads the session context so the user never types /start.

Order of operations (each one exists because skipping it once cost real time):

1. Worktree/branch guard — refuse to work from a `.claude/worktrees/` checkout,
   a `claude/*` branch, or a branch listed in `protected_branches` (a fork's
   read-only `main`).
2. Global-install check — the rules that govern every project live in the
   Knowledge Base and are imported from `~/.claude/CLAUDE.md`. If that import
   is missing on this machine, say so loudly: the session would otherwise run
   with only the project file and no process.
3. Sync guard — `git fetch` and refuse to inject state docs from a checkout
   that is behind origin. Stale docs are self-consistent, so nothing
   downstream can catch them.
3b. Upstream drift — if `upstream_ref` is set (a fork), fetch that remote too
   and report how many commits the ref has that HEAD lacks. Reported only:
   catching up rewrites or merges the branch, which is a session decision.
4. Build: the directive (track gate + cross-check) FIRST, then the declared
   tracks, CURRENT_STATE.md, the ledger (v2: a one-line manifest of every open
   item plus capped full text for the items each NEXT ACTION section cites;
   v1: every open item truncated), the ROADMAP status spine (bloat warning),
   the last handoff entries (per track) and a template-drift note.
5. Deliver it in PARTS. Claude Code caps every hook string (`additionalContext`,
   `systemMessage`, plain stdout) at 10,000 characters; over that, the model
   receives a 2,000-character preview plus a file path it is not asked to read.
   Measured live on one project: 38 session starts in a row delivered a
   2,000-char preview of a 160,000→48,000-char payload, and 7 of them read
   the file. The cap is per string, so `.claude/settings.json` wires this
   script N times with `--part 1..N`, and each invocation emits ONE slice
   under `payload.part_chars`. Invocation 1 builds the whole payload, packs
   it, and writes the slices to a per-session cache; the others wait for that
   cache and emit their slice, so every part reflects ONE fetch and ONE
   decision (a "behind origin" refusal is a single part, and the other
   invocations emit nothing). Without `--part` the script emits the old single
   string, for a settings.json that has not been resynced.
6. `--slim` (wired on the `compact` matcher) re-injects only the standing
   rules after a compaction: the project CLAUDE.md comes back by itself, the
   hook payload does not.

All project-specific values come from `.claude/protocol.json` via
protocol_config.py — never edit this script per project.

Silent on every failure path: exits 0 with no output rather than blocking a
session. A directory with neither protocol.json nor docs/CURRENT_STATE.md is
not a protocol project and gets nothing.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import (  # noqa: E402
    drift_report,
    global_installed,
    id_prefixes,
    template_currency,
    load_config,
    multi_track,
    prefix_map,
    project_dir,
    protocol_version,
    template_root,
    track_aliases,
    track_names,
)

ITEM_RE = re.compile(
    r"^- \[( |x|-)\] ([A-Za-z]{1,4})-(\d+)\s*(?:(?:→|->)\s*[\w-]+\s*)?\((\d{4}-\d{2}-\d{2})"
)
TAG_RE = re.compile(r"(?:→|->)\s*([\w-]+)")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def run(cmd: list[str], cwd: str, timeout: int = 5) -> tuple[int, str]:
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return 1, ""


# --- Flags -------------------------------------------------------------------

# --measure: build the payload exactly as the hook would, then print its size
# breakdown (sections AND parts) instead of emitting it. Measuring a
# RECONSTRUCTION of the payload would be the classic mistake (the artifact you
# measure is not the artifact you ship), so the budget checker drives this mode
# rather than re-deriving sizes from the files. Skips the fetch so it is
# offline-safe and instant.
MEASURE = "--measure" in sys.argv
# --v2 / --v1 force a document shape regardless of protocol.json. Only for
# previewing one shape's payload against another shape's real documents, so a
# migration can be sized before anything is migrated. The hook never passes it.
FORCE_VERSION = 2 if "--v2" in sys.argv else (1 if "--v1" in sys.argv else None)
# --slim: the compact-time reminder (see module doc, 6).
SLIM = "--slim" in sys.argv


def _arg_value(flag: str) -> str | None:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


try:
    # --part N: emit slice N of the packed payload (1-based). None = legacy single string.
    PART: int | None = int(_arg_value("--part") or 0) or None
except ValueError:
    PART = None

# Room left in every part for its header line (part n of m, payload size line).
PART_HEADER_RESERVE = 450
HARNESS_STRING_CAP = 10000


def hook_input() -> dict:
    """The JSON Claude Code pipes to a hook (session_id, source, cwd …). Read
    only when a hook flag is present and stdin is not a terminal: run by hand,
    a read would block; run by the budget checker, there is nothing to read."""
    if MEASURE or not (PART or SLIM):
        return {}
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (OSError, ValueError):
        return {}


# --- Delivery ----------------------------------------------------------------

def _write_context(text: str) -> None:
    payload = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}
    sys.stdout.write(json.dumps(payload))
    sys.exit(0)


def settings_part_count(proj: str) -> int:
    """How many `--part N` SessionStart entries `.claude/settings.json` wires —
    the number of slices that can actually be delivered. 0 = legacy wiring."""
    try:
        data = json.loads((pathlib.Path(proj) / ".claude" / "settings.json").read_text(encoding="utf-8"))
        n = 0
        for entry in (data.get("hooks") or {}).get("SessionStart") or []:
            for h in entry.get("hooks") or []:
                if "--part" in str(h.get("command", "")):
                    n += 1
        return n
    except (OSError, ValueError, AttributeError, TypeError):
        return 0


def split_long(sec: str, cap: int, first_room: int | None = None) -> list[str]:
    """Split one over-long section at line boundaries, repeating its heading
    with "(continued)". A single line longer than the cap is cut hard. With
    `first_room`, the first chunk is sized to fill the remaining room of the
    part being packed (it may come back empty when the first line alone does
    not fit there)."""
    lines = sec.split("\n")
    head = next((ln for ln in lines if ln.lstrip().startswith("#")), "")
    cont = (head + " (continued)\n") if head else ""
    room = max(cap - len(cont) - 1, 500)
    pieces: list[str] = []
    for ln in lines:
        while len(ln) > room:
            pieces.append(ln[:room])
            ln = ln[room:]
        pieces.append(ln)
    chunks: list[str] = []
    buf = ""
    limit = first_room if first_room else cap
    for ln in pieces:
        if len(buf) + len(ln) + 1 > limit:
            chunks.append(buf)
            buf = cont
            limit = cap
        buf += ln + "\n"
    if buf and buf != cont:
        chunks.append(buf)
    return chunks


def pack(sections: list[str], cap: int) -> list[str]:
    """Greedy packing of whole sections into slices of at most `cap` chars.
    A section that does not fit the current slice starts the next one; a
    section longer than a slice is split at line boundaries."""
    out: list[str] = []
    cur = ""
    for sec in sections:
        if not sec:
            continue
        if len(cur) + len(sec) <= cap:
            cur += sec
        elif len(sec) <= cap:
            if cur:
                out.append(cur)
            cur = sec
        else:
            # Start the split inside the current part's remaining room when
            # there is enough of it: a half-empty part is a wasted hook string.
            room = cap - len(cur)
            if cur and room >= 1500:
                chunks = split_long(sec, cap, first_room=room)
                cur += chunks[0]
                chunks = chunks[1:]
            else:
                chunks = split_long(sec, cap)
            if cur:
                out.append(cur)
            out.extend(chunks[:-1])
            cur = chunks[-1] if chunks else ""
    if cur:
        out.append(cur)
    return out


def _part_label(part: str) -> str:
    for ln in part.split("\n"):
        if ln.lstrip().startswith("#"):
            return ln.strip("# ").strip()[:70]
    return part.strip()[:60]


def fit_available(parts: list[str], available: int, cap: int) -> list[str]:
    """Parts beyond the wired hook entries cannot be delivered. Say so, loudly,
    in the last part that can — an absence produces no signal."""
    if len(parts) <= available:
        return parts
    dropped = parts[available:]
    kept = parts[:available]
    note = (
        f"\n\n🚨 **{len(dropped)} more part(s), {sum(len(p) for p in dropped):,} chars, did NOT fit the "
        f"{available} `--part` hook entries wired in `.claude/settings.json` and were NOT injected:** "
        + "; ".join(_part_label(p) for p in dropped)
        + ". The payload is over its deliverable ceiling. Read those documents yourself before the "
        "cross-check, say so in the status report, and run `python .claude/scripts/check-payload-budget.py` "
        "— shrink the largest contributor, never raise the budget.\n"
    )
    last = kept[-1]
    if len(last) + len(note) > cap:
        last = last[: max(cap - len(note), 0)].rstrip() + "\n…[cut to make room for the notice below]"
    kept[-1] = last + note
    return kept


def part_header(n: int, m: int, meta: str) -> str:
    if m == 1:
        return "## Auto-loaded session context (SessionStart hook)\n" + (meta + "\n" if meta else "")
    return (
        f"## Auto-loaded session context — part {n} of {m} (SessionStart hook)\n"
        f"_Claude Code caps one hook string at 10,000 characters, so this context arrives as {m} separate "
        f"strings, in any order. Read all {m} parts before acting; the directive is in part 1._\n"
        + (meta + "\n" if meta else "")
    )


def cache_path(key: str) -> pathlib.Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", key)[:80]
    return pathlib.Path(tempfile.gettempdir()) / "claude-session-start" / f"{safe}.json"


def session_key(hook: dict, proj: str) -> str:
    sid = str(hook.get("session_id") or "").strip()
    if sid:
        return sid
    # No id (run by hand): bucket by project and two-minute window so parallel
    # invocations still meet on one cache.
    return hashlib.sha1(proj.encode("utf-8")).hexdigest()[:12] + f"-{int(time.time() // 120)}"


def write_cache(path: pathlib.Path, parts: list[str], meta: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"parts": parts, "meta": meta}), encoding="utf-8")
        os.replace(tmp, path)
        # Tidy this script's own cache dir: slices from sessions older than
        # two days are unreachable (every reader insists on a fresh mtime).
        cutoff = time.time() - 2 * 86400
        for old in path.parent.glob("*.json"):
            try:
                if old.stat().st_mtime < cutoff:
                    old.unlink()
            except OSError:
                pass
    except OSError:
        pass


def wait_for_cache(path: pathlib.Path, started: float, wait_s: float) -> dict | None:
    """Poll for the cache part 1 writes. A `resume` fires this hook again with
    the SAME session id, so a cache from the earlier start may already exist:
    only one written since (about) this process started counts."""
    deadline = time.time() + wait_s
    while time.time() < deadline:
        try:
            if path.exists() and path.stat().st_mtime >= started - 5:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("parts"), list):
                    return data
        except (OSError, ValueError):
            pass
        time.sleep(0.25)
    return None


def deliver(sections: list[str], proj: str, cfg: dict, hook: dict, started: float) -> None:
    """Emit the payload — whole (legacy wiring), or as slice PART of the
    packed parts. Never returns."""
    pcfg = cfg.get("payload") or {}
    part_chars = int(pcfg.get("part_chars", 9000))
    cap = min(part_chars, HARNESS_STRING_CAP - 500) - PART_HEADER_RESERVE
    available = settings_part_count(proj)
    total = sum(len(s) for s in sections)
    target = int(pcfg.get("target_chars", 25000))
    if MEASURE:
        _emit_measurement(sections, pack(sections, cap), available, part_chars)
    if PART is None:
        _write_context("".join(sections))
    available = available or 1
    key = cache_path(session_key(hook, proj))
    if PART == 1:
        parts = fit_available(pack(sections, cap), available, cap)
        pct = round(total / max(target, 1) * 100)
        over = total > target * float(pcfg.get("warn_over", 1.0))
        meta = (
            f"_Payload: {total:,} chars in {len(parts)} part(s) — {pct}% of the {target:,}-char budget"
            + (" ⚠️ OVER BUDGET: shrink the largest contributor at /end" if over else "")
            + "._"
        )
        write_cache(key, parts, meta)
    else:
        data = wait_for_cache(key, started, float(pcfg.get("part_wait_seconds", 45)))
        if data is None:
            if PART == 2:  # one notice, not one per slot
                _write_context(
                    "## Auto-loaded session context — incomplete (SessionStart hook)\n"
                    "⚠️ The first hook invocation did not finish assembling the context in time, so the "
                    "remaining parts could not be delivered. Run `/start` to load the state docs by hand "
                    "before doing anything else.\n"
                )
            sys.exit(0)
        parts, meta = data["parts"], str(data.get("meta") or "")
    if PART > len(parts):
        sys.exit(0)  # nothing for this slot — fewer parts than wired entries
    _write_context(part_header(PART, len(parts), meta if PART == 1 else "") + parts[PART - 1])


def _emit_measurement(sections: list[str], parts: list[str], available: int, part_chars: int) -> None:
    """One line per injected section, then one per part, then the total, as
    `chars<TAB>label`. AVAILABLE_PARTS / PART_CAP carry the wiring."""
    text = "".join(sections)
    for chunk in re.split(r"\n(?=### )", text):
        label = chunk.split("\n", 1)[0].lstrip("# ").strip()
        sys.stdout.write(f"{len(chunk)}\t{label[:90]}\n")
    for i, p in enumerate(parts, 1):
        sys.stdout.write(f"{len(p) + PART_HEADER_RESERVE}\tPART {i}\n")
    sys.stdout.write(f"{available}\tAVAILABLE_PARTS\n")
    sys.stdout.write(f"{part_chars}\tPART_CAP\n")
    sys.stdout.write(f"{len(text)}\tTOTAL\n")
    sys.exit(0)


# --- Remote currency ---------------------------------------------------------

def remote_state(proj: str) -> tuple[int, int, bool, bool]:
    """(behind, ahead, dirty, fetch_ok). Fetches; never pulls — a dirty or
    diverged tree needs a human decision, and post-merge hooks can run installs.

    `fetch_ok` is only True when currency was actually PROVEN: the fetch
    succeeded AND the branch has an upstream to compare against. A branch with
    no tracking ref used to report "current" — the rev-list failed, both counts
    defaulted to 0, and the guard whose whole purpose is "a stale checkout looks
    complete, not broken" printed a green tick it had not earned."""
    if MEASURE:
        return 0, 0, False, True
    fetch_rc, _ = run(["git", "fetch", "origin", "--prune"], proj, timeout=20)
    rc, counts = run(["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"], proj)
    behind = ahead = 0
    tracked = False
    if rc == 0 and counts:
        try:
            a, b = counts.split()
            ahead, behind = int(a), int(b)
            tracked = True
        except ValueError:
            pass
    rc, porcelain = run(["git", "status", "--porcelain"], proj)
    return behind, ahead, rc == 0 and bool(porcelain), fetch_rc == 0 and tracked


def upstream_state(proj: str, ref: str) -> tuple[int, str, bool]:
    """(commits on ref not in HEAD, latest subject on ref, fetch_ok). Fetches the
    ref's remote (the part before the first "/"); never merges or rebases."""
    remote = ref.split("/", 1)[0]
    fetch_rc, _ = run(["git", "fetch", remote, "--prune"], proj, timeout=20)
    rc, count = run(["git", "rev-list", "--count", f"HEAD..{ref}"], proj)
    behind = int(count) if rc == 0 and count.isdigit() else 0
    _, latest = run(["git", "log", "-1", "--format=%h %s (%cr)", ref], proj)
    return behind, latest, fetch_rc == 0


# --- Ledger ------------------------------------------------------------------

def ledger_blocks(text: str) -> tuple[list[str], list[list[str]]]:
    """Split the ledger into (header lines, item blocks). A block is the ID line
    plus its non-blank continuation lines."""
    header: list[str] = []
    blocks: list[list[str]] = []
    current: list[str] | None = None
    in_items = False
    in_comment = False
    for ln in text.splitlines():
        # HTML comment blocks (the header's example items live in one) are
        # never items and never injected — an example `- [ ] L-1 …` used to
        # be counted and shown as a real open loop at every session start.
        if in_comment:
            in_comment = "-->" not in ln
            continue
        if "<!--" in ln:
            in_comment = "-->" not in ln[ln.index("<!--"):]
            continue
        s = ln.lstrip()
        if s.startswith("- ["):
            in_items = True
            current = [ln]
            blocks.append(current)
        elif not in_items:
            header.append(ln)
        elif s and current is not None:
            current.append(ln)
    return header, blocks


def item_tag(first_line: str, aliases: dict[str, str]) -> str | None:
    """A →track / →all tag on the ID line, only for declared names or aliases.

    Two positions count, and nothing else does (an arrow inside the item's
    prose must not re-route it):
      1. right after the ID:            `- [ ] L-423 →mobile (2026-08-29, …)`   (canonical)
      2. right after the date paren:    `- [ ] D-2 (2026-09-08) →mobile …`
    Legacy ledgers can have very long date parentheses, so position 2 is found
    from the first ')' rather than a fixed prefix."""
    alts = "|".join(re.escape(a) for a in list(aliases) + ["all"])
    s = first_line.lstrip()
    m = re.match(r"- \[.\] [A-Za-z]{1,4}-\d+\s*(?:→|->)\s*(" + alts + r")\b", s, re.IGNORECASE)
    if not m:
        close = s.find(")")
        if close >= 0:
            m = re.match(r"\)\s*(?:→|->)\s*(" + alts + r")\b", s[close:], re.IGNORECASE)
    if not m:
        return None
    hit = m.group(1).lower()
    return "all" if hit == "all" else aliases.get(hit)


def truncate(block_text: str, cap: int) -> tuple[str, bool]:
    if len(block_text) <= cap:
        return block_text, False
    cut = block_text[:cap].rstrip()
    extra = len(block_text) - len(cut)
    return f"{cut} …[TRUNCATED at {cap} chars — {extra} more in docs/SESSION_LEDGER.md; the item is over the cap and should be shortened]", True


def truncate_expanded(block_text: str, cap: int, item_id: str) -> tuple[str, bool]:
    """v2: the item stays whole in the ledger; only its INJECTED expansion is
    cut. The ledger has no per-item cap by design (the manifest protects the
    injection), so an uncapped expansion was the one hole left in the budget —
    four cited items came to 9,800 of a 19,700-char manifest on 2026-10-19."""
    if len(block_text) <= cap:
        return block_text, False
    cut = block_text[:cap].rstrip()
    extra = len(block_text) - len(cut)
    return f"{cut} …[expanded text cut at {cap} chars — {extra} more under {item_id} in docs/SESSION_LEDGER.md]", True


def _matching_paren(s: str, start: int) -> int:
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _clean(s: str) -> str:
    s = re.sub(r"\*\*|`", "", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def _cut(s: str, cap: int) -> str:
    if len(s) <= cap:
        return s
    head = s[:cap].rsplit(" ", 1)[0]
    return (head if len(head) > cap // 2 else s[:cap]).rstrip(" ,;:—-") + " …"


def item_title(block: list[str], cap: int) -> str:
    """One manifest line for an item: `- ID →tag (date) TITLE`.

    A live item's first line is `- [ ] D-84 →desktop (2026-09-29, 172nd, a
    tester's screenshot: "…") **THE TITLE.** rest…`, and that provenance
    parenthetical runs to hundreds of characters. The earlier rule — cut the
    first line at `cap` — therefore cut INSIDE the provenance: on one 89-item
    ledger, 24 manifest lines never reached the title and 20 more showed under
    40 characters of it. Now: ID, tag and date are kept; the parenthetical is
    dropped (it is history, and the whole item is one grep away); the title is
    the bold span that follows it, or the plain text after it when the item has
    no bold; and only the title is cut to `cap`, at a word boundary. A line
    that is not a dated item falls back to the old behaviour."""
    s = re.sub(r"\s+", " ", block[0].lstrip()).strip()
    m = ITEM_RE.match(s)
    if not m:
        return "- " + _cut(_clean(s[6:] if s.startswith("- [") else s), cap)
    item_id = f"{m.group(2)}-{m.group(3)}"
    date = m.group(4)
    paren_open = s.find("(" + date)
    paren_close = _matching_paren(s, paren_open) if paren_open >= 0 else -1
    if paren_close < 0:
        return "- " + _cut(_clean(s[6:]), cap)
    tag_m = TAG_RE.search(s[m.end(3):paren_open])
    tag = tag_m.group(1) if tag_m else None
    tail = s[paren_close + 1:].strip()
    t2 = re.match(r"(?:→|->)\s*([\w-]+)\s*", tail)
    if t2:
        tag = tag or t2.group(1)
        tail = tail[t2.end():]
    b = BOLD_RE.match(tail)
    title = b.group(1) if b else tail
    return f"- {item_id}{' →' + tag if tag else ''} ({date}) {_cut(_clean(title), cap)}"


def gating_ids(state_text: str, cfg: dict, per_section: int) -> dict[str, str]:
    """ID → the NEXT ACTION section that cites it — the items v2 gives (capped)
    full text to, up to `per_section` per section, in document order. The NEXT
    ACTION line is the selector: the choice is derived from something already
    maintained rather than being a second marker to keep in sync. Only DECLARED
    prefixes match, so `BUG-79` and `AVX-512` do not.

    Per SECTION, not per document. Taken as one list across the file, the cap
    went entirely to the first track's section: on a five-track project every
    expanded item was desktop's and four tracks got none (2026-10-19)."""
    pat = re.compile(r"\b(?:" + "|".join(id_prefixes(cfg)) + r")-\d+\b")
    out: dict[str, str] = {}
    section: str | None = None
    taken = 0
    for ln in state_text.splitlines():
        if ln.lstrip().startswith("#"):
            label = re.sub(r"^[^A-Za-z0-9]+", "", ln.lstrip("#").strip())
            section = label if "next action" in ln.lower() else None
            taken = 0
            continue
        if section is None or taken >= per_section:
            continue
        for hit in pat.findall(ln):
            if hit not in out and taken < per_section:
                out[hit] = section
                taken += 1
    return out


def open_ledger_view(text: str, cfg: dict, version: int = 1, gating: dict[str, str] | None = None) -> dict:
    """v1 injects every open item's text, truncated per item. v2 injects a
    complete one-line manifest plus the (capped) full text of the items the
    NEXT ACTION sections cite — rank for depth, never for presence. An item
    dropped from the manifest would be an absence, and absences produce no
    signal."""
    gating = gating or {}
    header, blocks = ledger_blocks(text)
    pcfg = cfg.get("payload") or {}
    cap = int(cfg["ledger"]["item_max_chars"])
    title_cap = int(pcfg.get("manifest_title_chars", 110))
    expand_cap = int(pcfg.get("gating_item_max_chars", 1200))
    stale_days = int(cfg["ledger"]["stale_after_days"])
    today = _dt.date.today()
    names = track_names(cfg)
    aliases = track_aliases(cfg)
    pmap = prefix_map(cfg)
    open_blocks = [b for b in blocks if b[0].lstrip().startswith("- [ ]")]
    closed = len(blocks) - len(open_blocks)

    groups: dict[str, list[str]] = {}
    order: list[str] = []
    stale: list[str] = []
    truncated = 0
    expanded: list[str] = []
    for b in open_blocks:
        first = b[0]
        m = ITEM_RE.match(first.lstrip())
        item_id = f"{m.group(2)}-{m.group(3)}" if m else "?"
        if m:
            try:
                d = _dt.date.fromisoformat(m.group(4))
                if (today - d).days > stale_days:
                    stale.append(item_id)
            except ValueError:
                pass
        if version >= 2:
            if item_id in gating:
                text_block, was_cut = truncate_expanded("\n".join(b), expand_cap, item_id)
                text_block = f"▶ {item_id} expanded — cited in “{gating[item_id]}”:\n" + text_block
                expanded.append(item_id)
            else:
                text_block, was_cut = item_title(b, title_cap), False
        else:
            text_block, was_cut = truncate("\n".join(b), cap)
        truncated += int(was_cut)
        if multi_track(cfg):
            writer = pmap.get(m.group(2).upper()) if m else None
            tag = item_tag(first, aliases)
            if tag == "all":
                key = "SHARED (→all)"
            elif tag:
                key = tag.upper()
            elif writer:
                key = writer.upper()
            else:
                key = "UNASSIGNED (legacy L-* / no tag)"
            if tag and writer and writer != tag:
                head_line, _, rest = text_block.partition("\n")
                text_block = head_line + f"   ⟵ from {writer}, for {tag}" + ("\n" + rest if rest else "")
        else:
            key = "OPEN"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(text_block)

    # Stable group order: tracks in declared order, then shared, then unassigned.
    if multi_track(cfg):
        wanted = [n.upper() for n in names] + ["SHARED (→all)", "UNASSIGNED (legacy L-* / no tag)"]
        order = [k for k in wanted if k in groups] + [k for k in order if k not in wanted]

    # v1 injected the ledger's whole header block — 3,071 chars of authoring
    # rules on the live project — at every session start. Those rules are
    # already in PROTOCOL.md, which is @imported every session, so it was a
    # second copy of the same text competing for the same budget. v2 drops it.
    parts = [] if version >= 2 else ["\n".join(header).rstrip()]
    for key in order:
        parts.append(f"\n#### {key} — {len(groups[key])} open\n" + "\n".join(groups[key]))
    return {
        "text": "\n".join(parts),
        "open": len(open_blocks),
        "closed": closed,
        "truncated": truncated,
        "stale": stale,
        "expanded": expanded,
    }


# --- Spine -------------------------------------------------------------------

def spine_view(roadmap_text: str, heading: str) -> tuple[str, list[str]]:
    lines = roadmap_text.splitlines()
    spine: list[str] = []
    capturing = False
    for ln in lines:
        if not capturing and heading.lower() in ln.lower() and ln.startswith("#"):
            capturing = True
        elif capturing and ln.startswith("## "):
            break
        if capturing:
            spine.append(ln)
    bloated: list[str] = []
    for ln in spine:
        if ln.startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) >= 3 and len(cells[-1]) > 1500:
                bloated.append(f"{cells[1][:40]} ({len(cells[-1])} chars)")
    return "\n".join(spine).rstrip(), bloated


# --- Slim (compact) ----------------------------------------------------------

def slim_text(cfg: dict) -> str:
    """What must survive a compaction. The project CLAUDE.md is re-injected by
    Claude Code itself; this hook's payload is not, and the compaction summary
    is prose written under pressure — the track rules are the first thing it
    drops. Deliberately under 2,000 characters."""
    out = [
        "## Context compacted — standing rules re-injected (SessionStart hook, `compact`)\n",
        "The state docs were injected at session start and are NOT re-injected here; the compaction summary "
        "carries where you were. Rules that must survive it:\n",
    ]
    if multi_track(cfg):
        out.append(
            f"- This repo runs parallel tracks ({' / '.join(track_names(cfg))}). You declared one at session "
            "start — stay on it: edit only its owned paths plus `shared_paths`, mint ledger IDs with its prefix "
            "only, never stage another track's files, never `git add -A`; another track's uncommitted files in "
            "the tree are theirs.\n"
        )
    out.append(
        "- If the summary does not state your NEXT ACTION and its open gates, re-read your track's NEXT ACTION "
        "section of `docs/CURRENT_STATE.md` and grep your ID prefix in `docs/SESSION_LEDGER.md` before "
        "continuing. Do not work from memory of a payload you no longer have.\n"
    )
    out.append(
        "- Ledger moment-of-event rule still applies: queue and strike items as they arise or resolve. "
        "`/end` still closes the session, and the index gate is not optional.\n"
    )
    check = str(cfg.get("check_command") or "").strip()
    if check:
        out.append(f"- `/end` Step 0c runs `{check}` before anything is committed; a red check stops the wrap.\n")
    return "".join(out)


# --- Main --------------------------------------------------------------------

def main() -> None:
    started = time.time()
    proj = project_dir()
    if not proj or not pathlib.Path(proj).is_dir():
        sys.exit(0)
    cfg, cfg_exists = load_config(proj)
    state_path = pathlib.Path(proj) / "docs" / "CURRENT_STATE.md"
    if not cfg_exists and not state_path.exists():
        sys.exit(0)  # not a protocol project
    hook = hook_input()

    if SLIM:
        _write_context(slim_text(cfg))

    # 1. Worktree/branch guard — mirrors /start Step 0 so the warning is identical.
    cwd_norm = proj.replace("\\", "/")
    rc, branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], proj)
    protected = [str(b).strip().lower() for b in cfg.get("protected_branches") or []]
    on_protected = rc == 0 and branch.lower() in protected
    if ".claude/worktrees/" in cwd_norm or (rc == 0 and branch.startswith("claude/")) or on_protected:
        why = (
            f"`{branch}` is listed in `protocol.json` → `protected_branches` and must never receive commits"
            if on_protected
            else "violates the workflow"
        )
        deliver([
            "⚠️ **Worktree/branch guard tripped at session start.** "
            f"cwd `{proj}` on branch `{branch or '(unknown)'}` — {why}. "
            "Tell the user verbatim from `/start` Step 0 and DO NOT proceed with reading state, "
            "editing files, or running other commands until they resolve it."
        ], proj, cfg, hook, started)

    # 2. Global install check.
    global_ok = global_installed()
    global_note = (
        ""
        if global_ok
        else "🚨 **GLOBAL RULES NOT INSTALLED ON THIS MACHINE.** `~/.claude/CLAUDE.md` does not import "
        "`claude-project-template/global/PROTOCOL.md`, so this session has the project file but NO "
        "work-style rules and NO session protocol. Before any work: locate the Knowledge Base clone "
        "on this machine (`git remote -v` → github.com/haithemobeidi/knowledge-base; usually under "
        "~/Documents), run `python \"<KB>/claude-project-template/install-global.py\"`, then restart "
        "the session. Tell the user this first.\n"
    )
    cfg_note = (
        ""
        if cfg_exists
        else "⚠️ `.claude/protocol.json` is missing — running with template defaults (single track, no "
        "check command, push policy = ask). Copy it from the template's `project/.claude/` and fill it in.\n"
    )

    # 3. Sync guard.
    behind, ahead, dirty, fetch_ok = remote_state(proj)
    if behind > 0:
        _, incoming = run(["git", "log", "--oneline", "--no-decorate", "-15", "HEAD..@{u}"], proj)
        if ahead > 0:
            resolution = (
                f"The branch has DIVERGED ({ahead} ahead, {behind} behind). **Do NOT auto-merge or "
                "rebase.** Surface this to the user and let them decide."
            )
        elif dirty:
            resolution = (
                f"The tree is behind by {behind} AND has uncommitted changes. **Do NOT stash or merge.** "
                "Surface both to the user and let them decide. (In a multi-track repo the dirty files may "
                "be the other session's — say so, still do not pull over them without the user's call.)"
            )
        else:
            resolution = (
                f"The tree is clean and strictly {behind} behind. Run `git pull --ff-only`, then read "
                "`docs/CURRENT_STATE.md`, the OPEN `[ ]` lines of `docs/SESSION_LEDGER.md` (grep `- [ ]`; "
                "closed lines are history), the ROADMAP status spine, and the last 5 `docs/HANDOFF_LOG.md` "
                "lines YOURSELF before reporting."
            )
        deliver([
            global_note
            + "## ⚠️ Session context NOT auto-loaded — this checkout is behind origin\n\n"
            f"`git fetch` found **{behind} commit(s) on the upstream branch that are not here** "
            "(commonly: the last session ran on another machine). The state docs were deliberately NOT "
            "injected: a stale snapshot reads as complete and self-consistent, and the cross-check only "
            "compares the docs against EACH OTHER.\n\n"
            f"**Incoming commits:**\n```\n{incoming or '(unavailable)'}\n```\n\n"
            f"**Resolution:** {resolution}\n\n"
            "Then give the normal status plus a sync line naming the pulled commit count. Never report "
            "state read from a checkout you have not confirmed is current."
        ], proj, cfg, hook, started)

    # 4. Happy path — build the sections. Each section is one string; the
    # packer never splits inside one unless it is longer than a whole part.
    version = FORCE_VERSION or protocol_version(cfg)
    notes: list[str] = [global_note, cfg_note]
    notes.append(
        "✅ Fetched origin — checkout is current.\n"
        if fetch_ok
        else "⚠️ **Currency UNVERIFIED** — either origin could not be reached, or this branch has no "
        "upstream to compare against (`git status -sb` says which). The docs below are the local "
        "checkout's copy and may be a snapshot of the past. Say so explicitly in the status report.\n"
    )

    # Upstream drift (forks): reported, never acted on.
    ref = str(cfg.get("upstream_ref") or "").strip()
    if ref:
        up_behind, up_latest, up_ok = upstream_state(proj, ref)
        if not up_ok:
            notes.append(f"⚠️ Could not fetch `{ref.split('/', 1)[0]}` — upstream drift is unknown this session.\n")
        elif up_behind == 0:
            notes.append(f"✅ This branch contains everything on `{ref}`.\n")
        else:
            notes.append(
                f"📥 **`{ref}` has {up_behind} commit(s) not in this branch** (latest: {up_latest}). "
                "Reported only: bringing the branch up to date (merge or rebase, per the project's "
                "DECISIONS.md) is a session decision at a quiet point, never part of session start. "
                "State the count in the status report.\n"
            )

    # Template drift (informational, one line).
    tmpl = template_root()
    if tmpl and tmpl.is_dir():
        # A drift report is only as current as the clone it compares against,
        # and nothing in a session pulls the Knowledge Base. Say so when this
        # machine's clone has gone quiet, BEFORE the report it qualifies.
        fetched_days, head_days = template_currency(tmpl)
        if (fetched_days is not None and fetched_days >= 3) or (fetched_days is None and (head_days or 0) >= 7):
            when = f"last fetched {fetched_days} day(s) ago" if fetched_days is not None else "never fetched here"
            notes.append(
                f"📚 **The Knowledge Base clone on this machine is {when}** (newest commit "
                f"{head_days if head_days is not None else '?'} day(s) old). The template-drift line below "
                "compares against THAT copy, so it can report 'up to date' while the real template has moved. "
                "`git pull --ff-only` the KB and rerun `install-global.py` before trusting a drift result, "
                "or before syncing a project.\n"
            )
        pdiff, gdiff = drift_report(proj, tmpl)
        if pdiff or gdiff:
            bits = []
            if pdiff:
                bits.append(f"{len(pdiff)} project file(s) differ from the template ({', '.join(pdiff)})")
            if gdiff:
                bits.append(f"global copies stale ({', '.join(gdiff)}) → rerun install-global.py")
            notes.append(
                "🔄 **Template drift:** " + "; ".join(bits)
                + ". Run `python .claude/scripts/check-template-drift.py` for details. Mention it in the "
                "status report; resync only when the user says so.\n"
            )

    # Document shape. PROTOCOL.md is imported live and always describes the
    # NEWEST shape, so a project that has not migrated would otherwise read
    # rules its own documents and scripts do not implement — two sources
    # disagreeing, which is the failure this protocol exists to prevent.
    if version < 2:
        notes.append(
            "\n📄 **This project is on document shape v1** (`protocol.json` → `protocol_version`), while "
            "the imported `PROTOCOL.md` describes v2. **Follow v1**: CURRENT_STATE as it is, the ledger "
            "items as injected below, one-line handoff entries. Do NOT write I-PASS handoff entries or "
            "title-first ledger items into a v1 project. v2 (a measured session-start payload, a ledger "
            "manifest, I-PASS handoffs) is available — the path is `MIGRATION.md` §6b in the Knowledge "
            "Base template, as its own session, never mid-work. Mention it once if it comes up; do not "
            "start it unasked.\n"
        )

    # Tracks.
    if multi_track(cfg):
        rows = []
        for t in cfg["tracks"]:
            owns = ", ".join(f"`{p}`" for p in t["owns"]) or "(no owned paths declared)"
            check = t.get("check_command")
            check_note = (
                f" — check: `{check}`" if check
                else (" — check: none for this track" if check is not None else "")
            )
            rows.append(f"- **{t['name']}** — IDs `{t['prefix']}-N` — owns {owns}{check_note}")
        shared = ", ".join(f"`{p}`" for p in cfg["shared_paths"]) or "(none declared)"
        notes.append(
            "\n### 🛤️ Parallel tracks declared in `.claude/protocol.json`\n"
            + "\n".join(rows)
            + f"\n- **shared** (any track, announce changes with a →all / →<track> ledger line): {shared}\n"
        )

    # Directive — built now, placed FIRST (part 1 always arrives; the parts
    # after it arrive in any order), referenced as "this context", not "above".
    audit = cfg.get("audit_command") or ""
    audit_line = (
        f"Run the project audit `{audit}` and mention it ONLY if it reports findings. " if audit else ""
    )
    if multi_track(cfg):
        names = " / ".join(track_names(cfg))
        gate = (
            f"0. **TRACK GATE (before anything else).** This repo runs parallel tracks ({names}). If the "
            "user's first message names the track this session is on, adopt it. Otherwise ASK which track "
            "with the AskUserQuestion picker (one option per track, never a plain-text question) "
            "and WAIT — do not read, edit, or report until you know. Everything in this context is scoped to "
            "YOUR track: your NEXT ACTION section, your ledger prefix, your last handoff line, your owned paths.\n"
        )
        crosscheck = (
            "1. **CROSS-CHECK (mandatory).** Does YOUR track's NEXT ACTION in CURRENT_STATE agree with the "
            "spine's CURRENT marker for your track, with your track's last HANDOFF line's 'Next:', and with "
            "no open gate tagged for your track or →all? **If they contradict, STOP and surface it — do not "
            "pick one and proceed.**\n"
            "2. If they agree, report: **Track:** <name> / where we are (name + number from the spine) / what "
            "your track's last session did / your single NEXT ACTION / open ledger items (yours + →all + "
            "unassigned, with gates) / a **sync line** stating currency explicitly / the payload size line "
            "from part 1.\n"
            "3. Standing rules for this session: edit only your owned paths and the shared paths; never "
            "touch the other track's owned paths or its ledger lines; stage explicit paths (never `git add "
            "-A`); the other track's uncommitted files in the tree are THEIRS — leave them and say so at "
            "wrap; a push publishes the whole branch, so name any commits that are not yours.\n"
        )
    else:
        gate = ""
        crosscheck = (
            "1. **CROSS-CHECK (mandatory).** Does CURRENT_STATE's NEXT ACTION agree with the spine's CURRENT "
            "phase/block AND the last HANDOFF line's 'Next:', AND does no open `[ ]` ledger gate contradict "
            "it? **If they contradict, STOP and surface the contradiction to the user — do NOT pick one and "
            "proceed.**\n"
            "2. If they agree, give a 4-line status: where we are (phase/block **name + number** from the "
            "spine) / what last session accomplished / the single **NEXT ACTION** / open ledger items (count + "
            "gates), plus a **sync line** stating currency explicitly (fetched-and-current, or "
            "fetch-failed-so-unverified) and, if an upstream ref is configured, its drift count, and the "
            "payload size line from part 1.\n"
        )
    directive = (
        "\n### Action requested — session start (the directive)\n"
        "The hook fetched origin and auto-loaded the state docs into this context (closed ledger lines are "
        "omitted by design — never read them at start). Now:\n"
        + gate
        + crosscheck
        + audit_line
        + "During the session, follow the ledger's moment-of-event rule: queue and strike items THE MOMENT "
        "they arise or resolve — never wait for /end. Trust but verify: CURRENT_STATE is hand-written and CAN "
        "be stale; the spine wins on any status disagreement. Numbers are frozen (never renumber). Don't "
        "re-read the docs injected here; don't run `/start` (this hook covered it). Run git status/log only "
        "if the user asks or the cross-check needs it.\n"
    )

    docs: list[str] = []

    # CURRENT_STATE.
    state_text = ""
    if state_path.exists():
        try:
            state_text = state_path.read_text(encoding="utf-8")
        except OSError:
            state_text = ""
    if state_text:
        docs.append("\n### docs/CURRENT_STATE.md\n" + state_text.rstrip() + "\n")

    # Ledger — v1: every open item's text, truncated. v2: a complete manifest
    # plus capped full text for the items the NEXT ACTION sections cite.
    ledger_path = pathlib.Path(proj) / "docs" / "SESSION_LEDGER.md"
    pcfg = cfg.get("payload") or {}
    if ledger_path.exists():
        try:
            gate_ids = (
                gating_ids(state_text, cfg, int(pcfg.get("max_gating_items", 4)))
                if version >= 2 else {}
            )
            ledger_info = open_ledger_view(ledger_path.read_text(encoding="utf-8"), cfg, version, gate_ids)
            cap = cfg["ledger"]["item_max_chars"]
            soft = cfg["ledger"]["open_soft_max"]
            extras = []
            if ledger_info["truncated"]:
                if version >= 2:
                    extras.append(
                        f"{ledger_info['truncated']} expanded item(s) cut at {pcfg.get('gating_item_max_chars', 1200)} "
                        "chars for injection (the ledger keeps them whole)"
                    )
                else:
                    extras.append(f"{ledger_info['truncated']} item(s) over the {cap}-char cap were truncated")
            if ledger_info["open"] > soft:
                extras.append(f"{ledger_info['open']} open > soft target {soft} — offer a triage pass")
            if ledger_info["stale"]:
                extras.append(
                    f"{len(ledger_info['stale'])} older than {cfg['ledger']['stale_after_days']} days: "
                    + ", ".join(ledger_info["stale"][:12])
                    + (" …" if len(ledger_info["stale"]) > 12 else "")
                )
            if version >= 2:
                exp = ledger_info["expanded"]
                head = (
                    f"\n### docs/SESSION_LEDGER.md — MANIFEST of all {ledger_info['open']} open items "
                    f"({ledger_info['closed']} closed omitted — history)\n"
                    "Each line is `ID →tag (date) TITLE` — the item's title, not the item; its provenance "
                    "parenthetical is dropped here. "
                    + (f"Full text is expanded in place for {', '.join(exp)} (cited by a NEXT ACTION section). "
                       if exp else "No item is expanded — no NEXT ACTION cites one. ")
                    + "To read any other item in full, grep its ID in `docs/SESSION_LEDGER.md` — "
                    "do that when you work on it, not before.\n"
                )
            else:
                head = (
                    f"\n### docs/SESSION_LEDGER.md — OPEN items only ({ledger_info['open']} open; "
                    f"{ledger_info['closed']} closed line(s) omitted — closed items are history)\n"
                )
            docs.append(
                head
                + ("⚠️ " + "; ".join(extras) + "\n" if extras else "")
                + ledger_info["text"].rstrip()
                + "\n"
            )
        except OSError:
            pass

    # Spine.
    roadmap_path = pathlib.Path(proj) / "ROADMAP.md"
    if roadmap_path.exists():
        try:
            spine, bloated = spine_view(roadmap_path.read_text(encoding="utf-8"), cfg["spine_heading"])
            if spine:
                warn = (
                    "⚠️ Spine cell(s) over 1,500 chars — history belongs in HANDOFF_LOG, not the cell: "
                    + "; ".join(bloated)
                    + "\n"
                    if bloated
                    else ""
                )
                docs.append(
                    "\n### ROADMAP.md — status spine (SOURCE OF TRUTH for phase/block status)\n" + warn + spine + "\n"
                )
        except OSError:
            pass

    # Handoff — last 5 overall, plus the last line per track.
    handoff_path = pathlib.Path(proj) / "docs" / "HANDOFF_LOG.md"
    if handoff_path.exists():
        try:
            entries = [ln for ln in handoff_path.read_text(encoding="utf-8").splitlines() if "|" in ln]
            if entries:
                # v1 injected the last 5 as a scannable index, which is why the
                # summary had to be capped at ~300 chars. v2 injects ONE entry —
                # yours — so it can be as long as the next session needs, and
                # the cap goes away. Reading further back is a deliberate act.
                if version < 2:
                    docs.append("\n### Last 5 lines of docs/HANDOFF_LOG.md\n" + "\n".join(entries[-5:]) + "\n")
                elif not multi_track(cfg):
                    docs.append("\n### docs/HANDOFF_LOG.md — last entry (the handoff you are accepting)\n"
                                + entries[-1] + "\n")
                if multi_track(cfg):
                    per: list[str] = []
                    for name in track_names(cfg):
                        last = None
                        for ln in reversed(entries):
                            fields = [f.strip() for f in ln.split("|")]
                            if len(fields) >= 3 and fields[1].lower() == name.lower():
                                last = ln
                                break
                        if last is None:
                            # Legacy lines (before the track field existed) name the track in
                            # free text, e.g. "(120th, desktop)" or "Android (86th)". Match the
                            # track name or any declared alias so the first post-migration
                            # cross-check has something to check against.
                            # Only the AREA field counts, and only where the name is used as a
                            # label — followed by "(", ",", ";", ")", "track", or the end —
                            # so "(120th, desktop; Android session concurrent)" matches desktop,
                            # not mobile.
                            words = [a for a, n in track_aliases(cfg).items() if n == name]
                            pat = (
                                r"(?:^|[\s(,;/])(?:" + "|".join(re.escape(w) for w in words)
                                + r")(?=\s*(?:\(|,|;|\)|track\b|$))"
                            )
                            for ln in reversed(entries):
                                fields = [f.strip() for f in ln.split("|")]
                                area = fields[1] if len(fields) >= 3 else ln
                                if re.search(pat, area, re.IGNORECASE):
                                    last = ln + "   ⟵ matched by text (legacy line, no track field)"
                                    break
                        per.append(f"- **{name}:** {last or '(no handoff line yet for this track)'}")
                    docs.append("\n### Last handoff line PER TRACK (cross-check against YOUR track's line)\n" + "\n".join(per) + "\n")
        except OSError:
            pass

    deliver(["".join(notes), directive] + docs, proj, cfg, hook, started)


if __name__ == "__main__":
    main()
