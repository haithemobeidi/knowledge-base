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
4. Inject: declared tracks (if any), CURRENT_STATE.md, the OPEN ledger items
   (each truncated to the configured cap, grouped by track), the ROADMAP
   status spine (with a warning for bloated cells), the last handoff lines
   (plus the last line per track), a template-drift note, and the mandatory
   cross-check / track-gate directive.

All project-specific values come from `.claude/protocol.json` via
protocol_config.py — never edit this script per project.

Silent on every failure path: exits 0 with no output rather than blocking a
session. A directory with neither protocol.json nor docs/CURRENT_STATE.md is
not a protocol project and gets nothing.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from protocol_config import (  # noqa: E402
    drift_report,
    global_installed,
    load_config,
    multi_track,
    prefix_map,
    project_dir,
    template_root,
    track_aliases,
    track_names,
)

ITEM_RE = re.compile(
    r"^- \[( |x|-)\] ([A-Za-z]{1,4})-(\d+)\s*(?:(?:→|->)\s*[\w-]+\s*)?\((\d{4}-\d{2}-\d{2})"
)


def run(cmd: list[str], cwd: str, timeout: int = 5) -> tuple[int, str]:
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return 1, ""


def emit(text: str) -> None:
    payload = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}
    sys.stdout.write(json.dumps(payload))
    sys.exit(0)


# --- Remote currency ---------------------------------------------------------

def remote_state(proj: str) -> tuple[int, int, bool, bool]:
    """(behind, ahead, dirty, fetch_ok). Fetches; never pulls — a dirty or
    diverged tree needs a human decision, and post-merge hooks can run installs."""
    fetch_rc, _ = run(["git", "fetch", "origin", "--prune"], proj, timeout=20)
    rc, counts = run(["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"], proj)
    behind = ahead = 0
    if rc == 0 and counts:
        try:
            a, b = counts.split()
            ahead, behind = int(a), int(b)
        except ValueError:
            pass
    rc, porcelain = run(["git", "status", "--porcelain"], proj)
    return behind, ahead, rc == 0 and bool(porcelain), fetch_rc == 0


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


def open_ledger_view(text: str, cfg: dict) -> dict:
    header, blocks = ledger_blocks(text)
    cap = int(cfg["ledger"]["item_max_chars"])
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
                text_block = text_block.replace(first, first + f"   ⟵ from {writer}, for {tag}", 1)
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

    parts = ["\n".join(header).rstrip()]
    for key in order:
        parts.append(f"\n#### {key} — {len(groups[key])} open\n" + "\n".join(groups[key]))
    return {
        "text": "\n".join(parts),
        "open": len(open_blocks),
        "closed": closed,
        "truncated": truncated,
        "stale": stale,
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


# --- Main --------------------------------------------------------------------

def main() -> None:
    proj = project_dir()
    if not proj or not pathlib.Path(proj).is_dir():
        sys.exit(0)
    cfg, cfg_exists = load_config(proj)
    state_path = pathlib.Path(proj) / "docs" / "CURRENT_STATE.md"
    if not cfg_exists and not state_path.exists():
        sys.exit(0)  # not a protocol project

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
        emit(
            "⚠️ **Worktree/branch guard tripped at session start.** "
            f"cwd `{proj}` on branch `{branch or '(unknown)'}` — {why}. "
            "Tell the user verbatim from `/start` Step 0 and DO NOT proceed with reading state, "
            "editing files, or running other commands until they resolve it."
        )

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
        emit(
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
        )

    # 4. Happy path — build the payload.
    parts: list[str] = ["## Auto-loaded session context (SessionStart hook)\n", global_note, cfg_note]
    parts.append(
        "✅ Fetched origin — checkout is current.\n"
        if fetch_ok
        else "⚠️ **Could not reach origin** — the docs below are from the local checkout and their "
        "currency is UNVERIFIED. Say so in the status report.\n"
    )

    # Upstream drift (forks): reported, never acted on.
    ref = str(cfg.get("upstream_ref") or "").strip()
    if ref:
        up_behind, up_latest, up_ok = upstream_state(proj, ref)
        if not up_ok:
            parts.append(f"⚠️ Could not fetch `{ref.split('/', 1)[0]}` — upstream drift is unknown this session.\n")
        elif up_behind == 0:
            parts.append(f"✅ This branch contains everything on `{ref}`.\n")
        else:
            parts.append(
                f"📥 **`{ref}` has {up_behind} commit(s) not in this branch** (latest: {up_latest}). "
                "Reported only: bringing the branch up to date (merge or rebase, per the project's "
                "DECISIONS.md) is a session decision at a quiet point, never part of session start. "
                "State the count in the status report.\n"
            )

    # Template drift (informational, one line).
    tmpl = template_root()
    if tmpl and tmpl.is_dir():
        pdiff, gdiff = drift_report(proj, tmpl)
        if pdiff or gdiff:
            bits = []
            if pdiff:
                bits.append(f"{len(pdiff)} project file(s) differ from the template ({', '.join(pdiff)})")
            if gdiff:
                bits.append(f"global copies stale ({', '.join(gdiff)}) → rerun install-global.py")
            parts.append(
                "🔄 **Template drift:** " + "; ".join(bits)
                + ". Run `python .claude/scripts/check-template-drift.py` for details. Mention it in the "
                "status report; resync only when the user says so.\n"
            )

    # Tracks.
    if multi_track(cfg):
        rows = []
        for t in cfg["tracks"]:
            owns = ", ".join(f"`{p}`" for p in t["owns"]) or "(no owned paths declared)"
            rows.append(f"- **{t['name']}** — IDs `{t['prefix']}-N` — owns {owns}")
        shared = ", ".join(f"`{p}`" for p in cfg["shared_paths"]) or "(none declared)"
        parts.append(
            "\n### 🛤️ Parallel tracks declared in `.claude/protocol.json`\n"
            + "\n".join(rows)
            + f"\n- **shared** (any track, announce changes with a →all / →<track> ledger line): {shared}\n"
        )

    # CURRENT_STATE.
    if state_path.exists():
        try:
            parts.append("\n### docs/CURRENT_STATE.md\n" + state_path.read_text(encoding="utf-8").rstrip() + "\n")
        except OSError:
            pass

    # Ledger — open items only, truncated, grouped.
    ledger_path = pathlib.Path(proj) / "docs" / "SESSION_LEDGER.md"
    ledger_info = None
    if ledger_path.exists():
        try:
            ledger_info = open_ledger_view(ledger_path.read_text(encoding="utf-8"), cfg)
            cap = cfg["ledger"]["item_max_chars"]
            soft = cfg["ledger"]["open_soft_max"]
            extras = []
            if ledger_info["truncated"]:
                extras.append(f"{ledger_info['truncated']} item(s) over the {cap}-char cap were truncated")
            if ledger_info["open"] > soft:
                extras.append(f"{ledger_info['open']} open > soft target {soft} — offer a triage pass")
            if ledger_info["stale"]:
                extras.append(
                    f"{len(ledger_info['stale'])} older than {cfg['ledger']['stale_after_days']} days: "
                    + ", ".join(ledger_info["stale"][:12])
                    + (" …" if len(ledger_info["stale"]) > 12 else "")
                )
            parts.append(
                f"\n### docs/SESSION_LEDGER.md — OPEN items only ({ledger_info['open']} open; "
                f"{ledger_info['closed']} closed line(s) omitted — closed items are history)\n"
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
                parts.append(
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
                parts.append("\n### Last 5 lines of docs/HANDOFF_LOG.md\n" + "\n".join(entries[-5:]) + "\n")
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
                    parts.append("\n### Last handoff line PER TRACK (cross-check against YOUR track's line)\n" + "\n".join(per) + "\n")
        except OSError:
            pass

    # Directive.
    audit = cfg.get("audit_command") or ""
    audit_line = (
        f"Run the project audit `{audit}` and mention it ONLY if it reports findings. " if audit else ""
    )
    if multi_track(cfg):
        names = " / ".join(track_names(cfg))
        gate = (
            f"0. **TRACK GATE (before anything else).** This repo runs parallel tracks ({names}). If the "
            "user's first message names the track this session is on, adopt it. Otherwise ASK which track "
            "and WAIT — do not read, edit, or report until you know. Everything below is scoped to YOUR "
            "track: your NEXT ACTION section, your ledger prefix, your last handoff line, your owned paths.\n"
        )
        crosscheck = (
            "1. **CROSS-CHECK (mandatory).** Does YOUR track's NEXT ACTION in CURRENT_STATE agree with the "
            "spine's CURRENT marker for your track, with your track's last HANDOFF line's 'Next:', and with "
            "no open gate tagged for your track or →all? **If they contradict, STOP and surface it — do not "
            "pick one and proceed.**\n"
            "2. If they agree, report: **Track:** <name> / where we are (name + number from the spine) / what "
            "your track's last session did / your single NEXT ACTION / open ledger items (yours + →all + "
            "unassigned, with gates) / a **sync line** stating currency explicitly.\n"
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
            "fetch-failed-so-unverified) and, if an upstream ref is configured, its drift count.\n"
        )
    parts.append(
        "\n---\n**Action requested — session start.** The hook fetched origin and auto-loaded the state docs "
        "above (closed ledger lines are omitted by design — never read them at start). Now:\n"
        + gate
        + crosscheck
        + audit_line
        + "During the session, follow the ledger's moment-of-event rule: queue and strike items THE MOMENT "
        "they arise or resolve — never wait for /end — and keep each item under the cap. Trust but verify: "
        "CURRENT_STATE is hand-written and CAN be stale; the spine wins on any status disagreement. Numbers "
        "are frozen (never renumber). Don't re-read the docs above; don't run `/start` (this hook covered "
        "it). Run git status/log only if the user asks or the cross-check needs it."
    )
    emit("".join(parts))


if __name__ == "__main__":
    main()
