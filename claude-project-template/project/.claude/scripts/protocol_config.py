#!/usr/bin/env python3
"""
Shared loader for `.claude/protocol.json` — the per-project settings file that
every protocol script reads instead of being edited by hand.

Why this exists: the scripts used to be customised per project (skip paths
pasted into one, the project's check command into another, the spine heading
into a third). Six projects later there were six divergent copies of each
script and no way to tell a bug fix from a local hack. Now the scripts are
identical in every repo — byte-for-byte, checkable — and everything that
legitimately differs between projects lives in one small JSON file.

Every reader falls back to DEFAULTS for any missing key, so a project with
no protocol.json at all still behaves like the original single-track template.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
import re
import subprocess

CONFIG_REL_PATH = ".claude/protocol.json"

# The document shape THIS template ships. A project's own `protocol_version`
# is compared against it, so "is this project behind?" is a number comparison
# rather than a hardcoded mention of whichever version happens to be newest.
# Bump this when a new shape lands, and add its hop to UPGRADE_SCRIPTS.
CURRENT_PROTOCOL_VERSION = 2

# target version -> the script that migrates a project INTO it, one hop each.
# A project two versions behind runs them in order.
UPGRADE_SCRIPTS = {
    2: ".claude/scripts/migrate-docs-v2.py",
}

# Paths never indexed and never scanned — protocol bookkeeping and build output.
DEFAULT_SKIP_PREFIXES = (
    ".claude/",
    "node_modules/",
    "dist/",
    "build/",
    "target/",
    ".next/",
    "__pycache__/",
)

DEFAULTS: dict = {
    # Which DOCUMENT SHAPE this project is on. 1 = the original (CURRENT_STATE
    # injected whole, ledger items injected as truncated full text, last 5
    # handoff lines). 2 = the budgeted shape (CURRENT_STATE is app state only,
    # the ledger injects a one-line-per-item manifest plus full text for the
    # items the NEXT ACTION cites, one handoff entry per track). The scripts
    # read this so a migrated and an unmigrated project can both work.
    "protocol_version": 1,
    # The session-start injection budget. The total is what is measured and
    # reported (check-payload-budget.py); per-part caps are hints. 25000 matches
    # the ceiling Claude Code puts on its own auto-loaded MEMORY.md index.
    # Every other cap in this protocol measures one input; this one measures
    # what the model actually receives, which is the only number that stays
    # true when the mass moves from one document to another.
    #
    # Delivery is a separate constraint from the budget: Claude Code caps ONE
    # hook string at 10,000 characters (over it, the model gets a 2,000-char
    # preview and a file path it is not asked to read). The hook therefore
    # emits the payload as several strings — one `--part N` entry each in
    # settings.json — of at most part_chars apiece. The deliverable ceiling is
    # (entries wired) × part_chars; the budget stays the smaller target.
    "payload": {
        "target_chars": 25000,
        "warn_over": 1.0,
        # How much of a ledger item's TITLE becomes its manifest entry (the
        # ID, tag and date are always shown; the provenance parenthetical never is).
        "manifest_title_chars": 110,
        # How many items PER NEXT ACTION SECTION get full text because that
        # section cites them. Per section, so every track's citations expand.
        "max_gating_items": 4,
        # Cap on one expanded item's INJECTED text. The ledger keeps the item
        # whole; only the injection is cut.
        "gating_item_max_chars": 1200,
        # Size of one delivered part. Must stay under the harness's 10,000-char
        # string cap with room for the part header; the hook clamps it.
        "part_chars": 9000,
        # How long parts 2..N wait for part 1's cache before giving up.
        "part_wait_seconds": 45,
        # Load by track (v2, two or more tracks): the size of one page of
        # `session-start-context.py --track <name>` output. Under the limit a
        # single tool result can carry, so a page always arrives whole.
        "page_chars": 24000,
        # The ratchet. {"<track>" | "project": chars} — written by
        # `check-payload-budget.py --init-ceiling` for a payload that is over
        # target_chars on the day the gate arrives, lowered by `--ratchet` at
        # every /end, removed once the payload is inside the budget. Raising a
        # number here by hand is raising the budget: the user's decision, and
        # a DECISIONS.md entry. Absent (not even {}) = this project has not
        # adopted the gate yet; a template sync adopts it, exactly once.
        # "ceiling_chars": {},
    },
    # The heading (case-insensitive substring) that opens the ROADMAP status spine.
    "spine_heading": "status at a glance",
    # Shell command run at /end Step 0c (build/drift/typecheck guard). "" = none.
    "check_command": "",
    # Shell command run at /start (dependency audit). "" = none.
    "audit_command": "",
    # "ask" = never push without asking; "standing" = session-end push pre-authorised
    # (record that authorisation in DECISIONS.md before setting this).
    "push_policy": "ask",
    # Run scan-secrets.py at /end Step 0c.
    "secret_scan": True,
    # Branches a session must never work on, e.g. ["main"] in a fork whose
    # main mirrors upstream. The start hook trips the branch guard on them.
    "protected_branches": [],
    # A remote-tracking ref this branch is periodically brought up to date
    # with, e.g. "upstream/main" in a fork. The start hook fetches its remote
    # and reports how many commits it has that HEAD lacks (never acts on it);
    # the statusline shows "upstream +N". "" = off.
    "upstream_ref": "",
    # Extra project-relative prefixes (POSIX form) the index tracker ignores,
    # e.g. generated icons, native gen/ dirs. Merged with DEFAULT_SKIP_PREFIXES.
    "index_skip_prefixes": [],
    # Extra file suffixes the index tracker ignores (binaries and media are
    # built in: images, video, audio, archives, fonts, compiled output).
    "index_skip_suffixes": [],
    "ledger": {
        # v1 ONLY: hard cap on one item's text (ID line + continuation lines);
        # the v1 hook truncates at injection. v2 has no per-item cap — the
        # manifest protects the injection and gating_item_max_chars caps an
        # expansion — so a v2 project may drop this key.
        "item_max_chars": 600,
        # Soft target for the open-item count; /end reports when exceeded.
        "open_soft_max": 30,
        # Open items older than this are listed at /end as "route or close".
        "stale_after_days": 45,
        # Closed [x]/[-] lines older than this MOVE to SESSION_LEDGER_CLOSED.md
        # at /end. Never deleted: an ID that escaped into a commit subject, a
        # handoff entry or a spine cell must stay resolvable forever.
        "move_closed_after_days": 7,
    },
    # CURRENT_STATE in a multi-track v2 project. Everything outside the NEXT
    # ACTION sections is loaded by every track's session, and no track may
    # prune a line another track wrote — so nothing ever left (2026-11-18: the
    # shared block was 15,600–18,500 chars of every track's 25,000). A bullet
    # tagged `- →<track> …` is loaded only for that track; the UNTAGGED bullets
    # may total at most shared_max_chars, and state-archive.py moves the oldest
    # (by the newest date in each) to docs/CURRENT_STATE_ARCHIVE.md at /end.
    # Never moved or counted: blocker sections, and the never_move sections.
    "state": {
        "shared_max_chars": 5000,
        # Sections (heading substring, any case) whose bullets are each
        # track's status of record. Neither counted nor moved; a row that is
        # one track's is tagged `- →<track>` so only that track loads it.
        "never_move": ["shipped", "build status"],
    },
    # Parallel tracks. [] = single track (IDs are L-N, no ownership rules).
    # /end Step 0d (check-file-caps.py): line caps on the code files a session
    # touched, and the same-basename twin check for new files. Extensions are
    # the code the caps apply to; docs and data are never counted.
    "file_caps": {
        "soft": 500,
        "hard": 800,
        "extensions": [
            ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".kt", ".kts", ".rs", ".py",
            ".swift", ".java", ".go", ".css", ".scss", ".html", ".vue", ".svelte",
        ],
        # Project-relative prefixes the caps ignore on top of index_skip_prefixes
        # (design prototypes, vendored code).
        "skip_prefixes": [],
    },
    # Each: {"name": "desktop", "prefix": "D", "owns": ["apps/desktop/", ...],
    #        "check_command": "pnpm check:desktop"}  (check_command optional: a
    # track whose work never touches the build — a marketing kit, docs — sets
    # "" and skips the repo-wide check; absent = the repo-wide check_command).
    "tracks": [],
    # Paths every track may edit. A change there that another track must act
    # on gets a ledger line tagged for exactly those tracks, by name.
    "shared_paths": [],
    # Who owns an open problem found on a shared path (a server advisory, a
    # shared script's bug): a track name for all of them, or {"apps/server/":
    # "desktop", …} by path. "" = the track that writes the item. One owner,
    # never →all: 40 of 122 open items on one project were →all because a
    # shared path had no owner, and each one rode in all five tracks' payloads.
    "shared_owner": "",
}


def project_dir() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR", "")


def _norm_prefix(p: str) -> str:
    p = p.replace("\\", "/").lstrip("./")
    return p if p.endswith("/") else p + "/"


def load_config(proj: str | None = None) -> tuple[dict, bool]:
    """Return (config merged over DEFAULTS, file_exists)."""
    proj = proj or project_dir()
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    path = pathlib.Path(proj) / CONFIG_REL_PATH if proj else None
    exists = bool(path and path.exists())
    if exists:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
        for key, value in raw.items():
            if key.startswith("$"):
                continue  # $comment keys
            if key in ("ledger", "file_caps", "payload", "state") and isinstance(value, dict):
                cfg[key].update({k: v for k, v in value.items() if not k.startswith("$")})
            else:
                cfg[key] = value
    # Normalise track shapes so callers never guess.
    tracks = []
    for t in cfg.get("tracks") or []:
        if not isinstance(t, dict) or not t.get("name"):
            continue
        name = str(t["name"]).strip()
        prefix = str(t.get("prefix") or name[:1]).strip().upper()
        owns = [_norm_prefix(str(p)) for p in (t.get("owns") or []) if str(p).strip()]
        aliases = [str(a).strip() for a in (t.get("aliases") or []) if str(a).strip()]
        # None = key absent (use the repo-wide check_command); "" = this track
        # declares it has no check. Callers must keep the two apart.
        check = str(t["check_command"]).strip() if "check_command" in t and t["check_command"] is not None else None
        tracks.append({"name": name, "prefix": prefix, "owns": owns, "aliases": aliases, "check_command": check})
    cfg["tracks"] = tracks
    cfg["shared_paths"] = [_norm_prefix(str(p)) for p in (cfg.get("shared_paths") or []) if str(p).strip()]
    return cfg, exists


def track_check_command(cfg: dict, track: str | None) -> str:
    """The check command a session on `track` runs at /end Step 0c: the
    track's own if its entry declares one (including "" for none), else the
    repo-wide `check_command`. Single-track projects pass None."""
    for t in cfg.get("tracks") or []:
        if track and t["name"].lower() == track.lower() and t.get("check_command") is not None:
            return t["check_command"]
    return str(cfg.get("check_command") or "")


def multi_track(cfg: dict) -> bool:
    return len(cfg.get("tracks") or []) > 1


def protocol_version(cfg: dict) -> int:
    """Document-shape generation. Unparseable or absent = 1 (the original)."""
    try:
        return int(cfg.get("protocol_version") or 1)
    except (TypeError, ValueError):
        return 1


def payload_keys(cfg: dict) -> list[str]:
    """What the budget is measured per. A v2 project with two or more tracks
    loads by track, so each track's session has its own payload; everything
    else has one, keyed "project"."""
    if protocol_version(cfg) >= 2 and multi_track(cfg):
        return track_names(cfg)
    return ["project"]


def payload_limit(cfg: dict, key: str) -> int:
    """The size `/end`'s budget gate holds a payload to: `payload.target_chars`,
    or — for a project that was already over the budget when the gate arrived —
    the ceiling recorded for it in `payload.ceiling_chars`, which
    check-payload-budget.py only ever lowers."""
    pcfg = cfg.get("payload") or {}
    target = int(pcfg.get("target_chars", 25000))
    ceilings = pcfg.get("ceiling_chars")
    try:
        ceiling = int(ceilings.get(key, 0)) if isinstance(ceilings, dict) else 0
    except (TypeError, ValueError):
        ceiling = 0
    return max(target, ceiling)


def id_prefixes(cfg: dict) -> list[str]:
    """Declared track prefixes plus the legacy `L`, for matching ledger IDs in
    prose. Using the DECLARED set rather than a generic [A-Z]{1,4}-\\d+ pattern
    is what keeps `BUG-79` and `AVX-512` out of the results."""
    seen: list[str] = []
    for t in cfg.get("tracks") or []:
        p = t.get("prefix")
        if p and p.upper() not in seen:
            seen.append(p.upper())
    if "L" not in seen:
        seen.append("L")
    return seen


def prefix_map(cfg: dict) -> dict[str, str]:
    """ID prefix → track name. Single-track projects use the legacy 'L'."""
    return {t["prefix"]: t["name"] for t in cfg.get("tracks") or []}


def track_names(cfg: dict) -> list[str]:
    return [t["name"] for t in cfg.get("tracks") or []]


def track_aliases(cfg: dict) -> dict[str, str]:
    """lower-cased name-or-alias → canonical track name. The name itself is
    always included, so `{"android": "mobile", "mobile": "mobile"}` for a
    track named mobile with alias android. Used for →tags and for matching
    legacy handoff lines that name the track in prose."""
    out: dict[str, str] = {}
    for t in cfg.get("tracks") or []:
        out[t["name"].lower()] = t["name"]
        for a in t.get("aliases") or []:
            out[a.lower()] = t["name"]
    return out


def track_of_path(cfg: dict, rel_posix: str) -> tuple[str, str | None]:
    """Classify a project-relative POSIX path.

    Returns ("track", name) if inside a track's owned paths,
            ("shared", None) if inside shared_paths,
            ("unowned", None) otherwise (docs, root files, anything undeclared).
    """
    rel = rel_posix.replace("\\", "/")
    for t in cfg.get("tracks") or []:
        if any(rel.startswith(p) for p in t["owns"]):
            return "track", t["name"]
    if any(rel.startswith(p) for p in cfg.get("shared_paths") or []):
        return "shared", None
    return "unowned", None


def shared_owner(cfg: dict, rel_posix: str = "") -> str | None:
    """The track that owns an open problem on a shared path (`shared_owner`):
    the one name, or the longest matching path prefix. None = not declared."""
    raw = cfg.get("shared_owner")
    aliases = track_aliases(cfg)
    if isinstance(raw, str):
        return aliases.get(raw.strip().lower())
    if isinstance(raw, dict):
        rel = rel_posix.replace("\\", "/")
        hits = sorted(((_norm_prefix(str(p)), str(t)) for p, t in raw.items() if not str(p).startswith("$")),
                      key=lambda pt: -len(pt[0]))
        for prefix, name in hits:
            if not rel or rel.startswith(prefix):
                return aliases.get(name.strip().lower())
    return None


# --- Tags: who a ledger item or a CURRENT_STATE bullet is for ------------------

def resolve_tags(rest: str, aliases: dict[str, str]) -> set[str]:
    """The track names in a tag list at the start of `rest` (the text right
    after the arrow): `desktop`, `android/ios`, `desktop, steamos`, `all`.

    Fails OPEN: a word that is not a declared track name or alias (`both`,
    `backend`) makes the whole tag "all", because a misread tag must never
    hide a line from the track it was written for. Longest alias first, so a
    multi-word alias ("steam deck") is one name."""
    names = sorted(list(aliases.items()) + [("all", "all")], key=lambda kv: -len(kv[0]))
    targets: set[str] = set()
    while True:
        hit = next(
            ((a, n) for a, n in names if re.match(re.escape(a) + r"(?![\w-])", rest, re.IGNORECASE)), None
        )
        if hit is None:
            return {"all"}
        targets.add(hit[1])
        rest = rest[len(hit[0]):]
        more = re.match(r"\s*(?:[/,+&]|and\b)\s*(?:→|->)?\s*", rest)
        if not more:
            return targets
        rest = rest[more.end():]


def item_targets(first_line: str, aliases: dict[str, str]) -> set[str] | None:
    """Who a ledger item is FOR, from its first line: the `→` tag right after
    the ID, or right after the provenance parenthetical (which may itself
    contain parentheses). None = no tag (the writer's track acts on it). The
    start hook scopes by it and the budget gate checks it, so both read it
    here."""
    s = first_line.lstrip()
    head = re.match(r"- \[.\] [A-Za-z]{1,4}-\d+\s*", s)
    if not head:
        return None
    rest = s[head.end():]
    if not re.match(r"(?:→|->)", rest):
        if not rest.startswith("("):
            return None
        depth = 0
        for k, ch in enumerate(rest):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0:
                rest = rest[k + 1:].lstrip()
                break
        else:
            return None
        if not re.match(r"(?:→|->)", rest):
            return None
    return resolve_tags(re.sub(r"^(?:→|->)\s*", "", rest), aliases)


# --- The shared block of CURRENT_STATE (multi-track) ---------------------------
# One parser for the start hook (which bullets a track loads), state-archive.py
# (which bullets may move) and the budget gate (how big the shared block is).
# Three readers with three definitions of "a bullet" would drift apart, and the
# drift would show up as a fact one track loads and the archive never moves.

DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def next_action_owner(heading: str, cfg: dict) -> str | None:
    """The track whose `## … NEXT ACTION — <track>` section this heading opens:
    the name or an alias as the LABEL, the first words after "NEXT ACTION". A
    track word further along does not count ("NEXT ACTION — all tracks: fix
    the site copy" is shared although "site" is an alias). None for any other
    heading."""
    low = heading.lower()
    if not heading.startswith("## ") or "next action" not in low:
        return None
    label = re.sub(r"^[^a-z0-9]+", "", low.split("next action", 1)[1])
    for a, n in sorted(track_aliases(cfg).items(), key=lambda kv: -len(kv[0])):
        if re.match(re.escape(a) + r"(?![\w-])", label):
            return n
    return None


# A line indented less than a list item's content that starts a block of its
# own: a list item of any kind, a quote, a table row, a thematic break, a
# heading, a fence, a comment. Markdown renders it as a new block, so it ends
# the bullet above it — reading it as that bullet's continuation would scope
# it to the bullet's track and hide it from every other one.
BLOCK_START = re.compile(
    r"^ ?(?:[-*+](?:\s|$)|\d{1,9}[.)](?:\s|$)|>|\||#|```|~~~|<!--|(?:-\s*){3,}$|(?:\*\s*){3,}$|(?:_\s*){3,}$)"
)


def _opens_comment(s: str) -> bool:
    return "<!--" in s and "-->" not in s[s.rindex("<!--"):]


def bullet_end(lines: list[str], i: int) -> int:
    """Index one past the last line of the top-level bullet starting at `i`.

    Part of the bullet: a line indented two or more spaces (or a tab) — its
    content or a nested list — also after blank lines; a plain line right
    under it with no blank between (lazy continuation); and everything from an
    indented fence or comment opener to its closer, wherever the closer sits
    (so a fence inside a bullet never flips the parity of the document's
    fences). Not part of it: a line that starts a block of its own
    (BLOCK_START), or anything after a blank line that is not indented."""
    n = len(lines)
    fenced = False
    comment = _opens_comment(lines[i].strip())
    j = i + 1
    while j < n:
        ln = lines[j]
        s = ln.strip()
        if fenced:
            fenced = not s.startswith(("```", "~~~"))
            j += 1
            continue
        if comment:
            comment = "-->" not in s
            j += 1
            continue
        if not s:
            k = j
            while k < n and not lines[k].strip():
                k += 1
            if k < n and lines[k].startswith(("  ", "\t")):
                j = k
                continue
            break
        if ln.startswith(("  ", "\t")):
            if s.startswith(("```", "~~~")):
                fenced = True
            elif _opens_comment(s):
                comment = True
            j += 1
            continue
        if BLOCK_START.match(ln):
            break
        comment = _opens_comment(s)
        j += 1
    return j


def state_segments(text: str, cfg: dict) -> list[dict]:
    """CURRENT_STATE as segments, in order, joining back to the text exactly:
    {"lines", "section", "kind", "bullet", "targets", "newest"}.

    kind: "next" (a track's NEXT ACTION section; "owner" says whose),
    "blocker" (a section whose heading says blocker), "record" (a section
    whose heading names one of `state.never_move` — Shipped, Build status:
    each track's current status of record), or "shared" (everything else,
    the preamble included). A segment is either one top-level bullet of a
    section other than NEXT ACTION ("bullet": True) or a run of other lines.
    targets: None for an untagged bullet, else resolve_tags of its `→` tag.
    newest: the latest ISO date in a bullet that is not in the future, or ""
    when it has none. Fenced blocks and HTML comments are never bullets and
    never headings; a heading line that opens a comment is still a heading."""
    lines = text.split("\n")
    aliases = track_aliases(cfg)
    never_move = [str(w).lower() for w in (cfg.get("state") or {}).get("never_move", []) if str(w).strip()]
    segs: list[dict] = []
    section, kind, owner = "", "shared", None
    fenced = comment = False
    run: list[str] = []

    def flush() -> None:
        if run:
            segs.append({"lines": list(run), "section": section, "kind": kind, "owner": owner,
                         "bullet": False, "targets": None, "newest": ""})
            run.clear()

    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if fenced or comment:
            if fenced and s.startswith(("```", "~~~")):
                fenced = False
            elif comment and "-->" in s:
                comment = False
            run.append(ln)
            i += 1
            continue
        if s.startswith(("```", "~~~")):
            fenced = True
            run.append(ln)
            i += 1
            continue
        if ln.startswith(("# ", "## ")):
            flush()
            section = ln.lstrip("#").strip()
            owner = next_action_owner(ln, cfg)
            low = ln.lower()
            kind = ("next" if owner else "blocker" if "blocker" in low
                    else "record" if any(w in low for w in never_move) else "shared")
            comment = _opens_comment(s)
            run.append(ln)
            i += 1
            continue
        if _opens_comment(s):
            comment = True
            run.append(ln)
            i += 1
            continue
        if kind != "next" and ln.startswith("- "):
            flush()
            j = bullet_end(lines, i)
            body = lines[i:j]
            tag = re.match(r"- (?:→|->)\s*", ln)
            # A date in the future ("deadline 2027-01-15") is not when the
            # fact was written; counting it would make the bullet immortal.
            today = _dt.date.today().isoformat()
            dates = [d for d in DATE_RE.findall("\n".join(body)) if d <= today]
            segs.append({"lines": body, "section": section, "kind": kind, "owner": owner, "bullet": True,
                         "targets": resolve_tags(ln[tag.end():], aliases) if tag else None,
                         "newest": max(dates) if dates else ""})
            i = j
            continue
        run.append(ln)
        i += 1
    flush()
    return segs


def capped_bullets(segs: list[dict]) -> list[dict]:
    """The bullets the cap counts and state-archive.py may move: untagged (or
    tagged `→all`) bullets of the "shared" sections — the ones that only ever
    accumulate. Per-track bullets cost only their track. Exempt: blocker
    sections (a live blocker must never age out of view) and "record"
    sections (Shipped, Build status): a track's row there is old because it is
    stable, not because it is stale, and moving it by age would take each
    track's current status out of every session, its own included (found in
    review, 2026-11-18). Those rows are one per track and rewritten in place;
    the way to stop every track paying for them is the tag."""
    return [s for s in segs if s["bullet"] and s["kind"] == "shared"
            and (s["targets"] is None or "all" in s["targets"])]


def seg_chars(seg: dict) -> int:
    return len("\n".join(seg["lines"])) + 1


def skip_prefixes(cfg: dict) -> tuple[str, ...]:
    extra = tuple(_norm_prefix(p) for p in cfg.get("index_skip_prefixes") or [])
    return DEFAULT_SKIP_PREFIXES + extra


# --- Global install discovery -------------------------------------------------

GLOBAL_IMPORT_RE = re.compile(
    r"^@(?P<path>.*claude-project-template[\\/]global[\\/]PROTOCOL\.md)\s*$", re.MULTILINE
)


def home_claude_md() -> pathlib.Path:
    return pathlib.Path.home() / ".claude" / "CLAUDE.md"


def global_protocol_path() -> pathlib.Path | None:
    """The PROTOCOL.md the global install points at, or None if not installed."""
    try:
        text = home_claude_md().read_text(encoding="utf-8")
    except OSError:
        return None
    m = GLOBAL_IMPORT_RE.search(text)
    if not m:
        return None
    return pathlib.Path(m.group("path").strip())


def global_installed() -> bool:
    p = global_protocol_path()
    return bool(p and p.exists())


def template_root() -> pathlib.Path | None:
    """<KB>/claude-project-template — from the global install, else $KB_TEMPLATE_DIR."""
    p = global_protocol_path()
    if p and p.exists():
        return p.parent.parent  # global/PROTOCOL.md → claude-project-template/
    env = os.environ.get("KB_TEMPLATE_DIR", "")
    if env and pathlib.Path(env).is_dir():
        return pathlib.Path(env)
    return None


def template_currency(tmpl: pathlib.Path) -> tuple[int | None, int | None]:
    """(days since the KB clone last fetched, days since its HEAD commit).

    Why this exists: the drift check compares a project against whatever
    template is on THIS machine's disk, and nothing in any session lifecycle
    pulls the Knowledge Base. So on a machine whose clone is twenty commits
    behind, `check-template-drift.py` compares against an old template and
    prints "up to date" — a false all-clear about the source of truth for the
    rules themselves. Same class as a `git status` that says "up to date with
    origin" without a fetch.

    Both numbers are read from the filesystem, no network: FETCH_HEAD's mtime
    is when this clone last heard from its remote, and HEAD's commit date
    bounds how old its content can be. Neither proves currency — only a fetch
    does — but a clone that has not talked to its remote in a week is worth
    saying out loud before anyone trusts a drift report from it."""
    git_dir = tmpl.parent / ".git"
    now = _dt.datetime.now(_dt.timezone.utc)
    fetched = None
    fh = git_dir / "FETCH_HEAD"
    try:
        if fh.exists():
            ts = _dt.datetime.fromtimestamp(fh.stat().st_mtime, _dt.timezone.utc)
            fetched = (now - ts).days
    except OSError:
        pass
    head = None
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI"], cwd=str(tmpl.parent),
            capture_output=True, text=True, timeout=5, check=False,
        ).stdout.strip()
        if out:
            head = (now - _dt.datetime.fromisoformat(out)).days
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return fetched, head


def file_hash(path: pathlib.Path) -> str:
    try:
        data = path.read_bytes().replace(b"\r\n", b"\n")
    except OSError:
        return ""
    return hashlib.sha256(data).hexdigest()


# Files that must be byte-identical between a project and the template's
# project/ skeleton. Anything else in .claude/ is project-owned.
TEMPLATE_MANAGED = (
    ".claude/settings.json",
    ".claude/scripts/protocol_config.py",
    ".claude/scripts/session-start-context.py",
    ".claude/scripts/track-new-file.py",
    ".claude/scripts/stop-clean-tree-check.py",
    ".claude/scripts/validate-index.py",
    ".claude/scripts/statusline.py",
    ".claude/scripts/scan-secrets.py",
    ".claude/scripts/check-file-caps.py",
    ".claude/scripts/check-payload-budget.py",
    ".claude/scripts/check-ledger-refs.py",
    ".claude/scripts/migrate-docs-v2.py",
    ".claude/scripts/ledger-archive.py",
    ".claude/scripts/state-archive.py",
    ".claude/scripts/end-derive.py",
    ".claude/scripts/check-template-drift.py",
    ".claude/agents/planner.md",
    ".claude/agents/reviewer.md",
    ".claude/agents/explorer.md",
)

# Files the global install copies into ~/.claude/ (commands cannot be @imported).
GLOBAL_COPIED = (
    ("global/commands/start.md", "commands/start.md"),
    ("global/commands/end.md", "commands/end.md"),
)


def drift_report(proj: str, tmpl: pathlib.Path) -> tuple[list[str], list[str]]:
    """Return (project files differing from template, global copies differing)."""
    proj_diffs: list[str] = []
    for rel in TEMPLATE_MANAGED:
        a = pathlib.Path(proj) / rel
        b = tmpl / "project" / rel
        if not b.exists():
            continue
        if not a.exists() or file_hash(a) != file_hash(b):
            proj_diffs.append(rel)
    global_diffs: list[str] = []
    for src_rel, dst_rel in GLOBAL_COPIED:
        src = tmpl / src_rel
        dst = pathlib.Path.home() / ".claude" / dst_rel
        if src.exists() and (not dst.exists() or file_hash(src) != file_hash(dst)):
            global_diffs.append(dst_rel)
    return proj_diffs, global_diffs
