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

import hashlib
import json
import os
import pathlib
import re

CONFIG_REL_PATH = ".claude/protocol.json"

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
    "ledger": {
        # Hard cap on one item's text (ID line + continuation lines). Longer
        # analysis goes to a linked doc; the hook truncates at injection.
        "item_max_chars": 600,
        # Soft target for the open-item count; /end reports when exceeded.
        "open_soft_max": 30,
        # Open items older than this are listed at /end as "route or close".
        "stale_after_days": 45,
        # Closed [x]/[-] lines older than this are pruned at /end.
        "prune_closed_after_days": 7,
    },
    # Parallel tracks. [] = single track (IDs are L-N, no ownership rules).
    # Each: {"name": "desktop", "prefix": "D", "owns": ["apps/desktop/", ...]}
    "tracks": [],
    # Paths every track may edit; changes there are announced with a ledger
    # line tagged →all or →<other track>.
    "shared_paths": [],
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
            if key == "ledger" and isinstance(value, dict):
                cfg["ledger"].update({k: v for k, v in value.items() if not k.startswith("$")})
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
        tracks.append({"name": name, "prefix": prefix, "owns": owns, "aliases": aliases})
    cfg["tracks"] = tracks
    cfg["shared_paths"] = [_norm_prefix(str(p)) for p in (cfg.get("shared_paths") or []) if str(p).strip()]
    return cfg, exists


def multi_track(cfg: dict) -> bool:
    return len(cfg.get("tracks") or []) > 1


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
