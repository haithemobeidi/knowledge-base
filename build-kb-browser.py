#!/usr/bin/env python3
"""Regenerate the Knowledge Base site from the lesson .md files and the process docs.

Two outputs from one template (`kb-browser.template.html`, authored as an HTML
fragment: <title> + <style> at the top, then markup and script):

    kb-browser.html            full document — double-click to open locally, no server
    kb-browser.artifact.html   the bare fragment — what the Artifact tool publishes as the
                               hosted page (gitignored; regenerate, then republish)

Data embedded as JSON:
  - lessons: every root-level .md with `stack` / `kind` / `last_verified` frontmatter,
    with its one-liner pulled from README.md's Lessons list
  - docs:    the process documents (template README, global rules, commands, project
             skeleton, migration guide, this repo's DECISIONS and references)

Run after adding or editing a lesson or a template doc:
    python build-kb-browser.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
EXCLUDE = {"README.md", "DECISIONS.md", "references.md"}
OUTPUT = ROOT / "kb-browser.html"
OUTPUT_FRAGMENT = ROOT / "kb-browser.artifact.html"
TEMPLATE = ROOT / "claude-project-template"

# Tag -> facet group, for the sidebar. Falls back to "Other" for anything
# not listed here, so a new tag on a future lesson never breaks generation.
TAG_GROUPS = {
    # Languages
    "rust": "Languages", "typescript": "Languages", "javascript": "Languages",
    "sql": "Languages", "css": "Languages", "kotlin": "Languages", "python": "Languages",
    # Frameworks & libraries
    "react": "Frameworks & Libraries", "framer-motion": "Frameworks & Libraries",
    "tailwind": "Frameworks & Libraries", "zod": "Frameworks & Libraries",
    "sqlx": "Frameworks & Libraries", "tokio": "Frameworks & Libraries",
    "better-auth": "Frameworks & Libraries", "animation": "Frameworks & Libraries",
    "design-system": "Frameworks & Libraries", "frontend": "Frameworks & Libraries",
    "state-management": "Frameworks & Libraries", "compose": "Frameworks & Libraries",
    "jetpack-compose": "Frameworks & Libraries", "css-grid": "Frameworks & Libraries",
    "view-transitions": "Frameworks & Libraries", "layout": "Frameworks & Libraries",
    # Platforms & runtimes
    "tauri": "Platforms & Runtimes", "tao": "Platforms & Runtimes", "electron": "Platforms & Runtimes",
    "capacitor": "Platforms & Runtimes", "node": "Platforms & Runtimes",
    "vite": "Platforms & Runtimes", "webview2": "Platforms & Runtimes",
    "windows": "Platforms & Runtimes", "desktop": "Platforms & Runtimes",
    "desktop-overlay": "Platforms & Runtimes", "mobile": "Platforms & Runtimes",
    "ios": "Platforms & Runtimes", "android": "Platforms & Runtimes",
    "multiwindow": "Platforms & Runtimes", "threads": "Platforms & Runtimes",
    "chrome-extension": "Platforms & Runtimes", "manifest-v3": "Platforms & Runtimes",
    "web": "Platforms & Runtimes", "adb": "Platforms & Runtimes", "comfyui": "Platforms & Runtimes",
    "powershell": "Platforms & Runtimes",
    # Cloud & backend
    "cloudflare-worker": "Cloud & Backend", "cloudflare-r2": "Cloud & Backend", "cloudflare": "Cloud & Backend",
    "d1": "Cloud & Backend", "wrangler": "Cloud & Backend", "s3": "Cloud & Backend",
    "s3-compatible": "Cloud & Backend", "presigned-urls": "Cloud & Backend",
    "aws4fetch": "Cloud & Backend", "fly-io": "Cloud & Backend",
    "supabase": "Cloud & Backend", "supabase-postgres": "Cloud & Backend",
    "postgres": "Cloud & Backend", "sqlite": "Cloud & Backend",
    "http-api": "Cloud & Backend", "graphql": "Cloud & Backend", "sse": "Cloud & Backend",
    "cdn": "Cloud & Backend", "server": "Cloud & Backend",
    # Data & sync
    "powersync": "Data & Sync", "local-first": "Data & Sync",
    "local-first-sync": "Data & Sync", "sync": "Data & Sync",
    "offline-first": "Data & Sync", "distributed-systems": "Data & Sync",
    "codegen": "Data & Sync", "monorepo": "Data & Sync",
    "pnpm-monorepo": "Data & Sync", "migrations": "Data & Sync", "database": "Data & Sync",
    # Auth & security
    "auth": "Auth & Security", "jwt": "Auth & Security", "sessions": "Auth & Security",
    "security": "Auth & Security", "azure": "Auth & Security", "azure-cli": "Auth & Security",
    "entra-id": "Auth & Security", "trusted-signing": "Auth & Security",
    "azure-trusted-signing": "Auth & Security", "code-signing": "Auth & Security",
    "smartscreen": "Auth & Security", "distribution": "Auth & Security",
    "chrome": "Auth & Security", "git": "Auth & Security", "steam-openid": "Auth & Security",
    "privacy": "Auth & Security", "analytics": "Auth & Security",
    # Integrations
    "api-integration": "Integrations", "monetization": "Integrations", "billing": "Integrations",
    "steam": "Integrations", "vdf": "Integrations", "game-library-integration": "Integrations",
    "play-billing": "Integrations", "llm": "Integrations", "ai": "Integrations", "gemini": "Integrations",
    # Reliability & perf
    "sentry": "Reliability & Perf", "crash-reporting": "Reliability & Perf",
    "performance": "Reliability & Perf", "dom": "Reliability & Perf", "debugging": "Reliability & Perf",
    "observability": "Reliability & Perf", "testing": "Reliability & Perf",
    # Process & meta
    "any": "Process & Meta", "refactoring": "Process & Meta",
    "codebase-audit": "Process & Meta", "docs": "Process & Meta", "process": "Process & Meta",
    "tooling": "Process & Meta", "claude-code": "Process & Meta", "multi-agent": "Process & Meta",
    "research": "Process & Meta", "upgrade": "Process & Meta",
}

GROUP_ORDER = [
    "Languages", "Frameworks & Libraries", "Platforms & Runtimes",
    "Cloud & Backend", "Data & Sync", "Auth & Security", "Integrations",
    "Reliability & Perf", "Process & Meta", "Other",
]

# The process collection: (id, path relative to ROOT, section, description).
# Order here is the order in the site's Process navigation.
PROCESS_DOCS = [
    ("start-here", "README.md", "Start here",
     "The front door: the three entry points for a human or an agent, the template, and the freshness rule."),
    ("template", "claude-project-template/README.md", "Start here",
     "The two layers (global and project), the per-machine install, the bootstrap procedure, the settings reference, parallel tracks, troubleshooting."),
    ("migration", "claude-project-template/MIGRATION.md", "Start here",
     "Bringing an existing project onto the layered protocol in one session without losing its place."),
    ("work-style", "claude-project-template/global/WORK_STYLE.md", "Global rules",
     "How the user and Claude work together in any app: the rhythm, building, capturing lessons, product principles. Loaded into every session."),
    ("work-style-detail", "claude-project-template/global/WORK_STYLE_DETAIL.md", "Global rules",
     "The long-form version of each work-style rule: the why, the exact steps, the incident that earned it."),
    ("protocol", "claude-project-template/global/PROTOCOL.md", "Global rules",
     "The session lifecycle: start, during, end, the ledger, parallel tracks, hooks. Loaded into every session."),
    ("start-command", "claude-project-template/global/commands/start.md", "Commands",
     "The /start step list: worktree guard, sync guard, track gate, cross-check, the status report."),
    ("end-command", "claude-project-template/global/commands/end.md", "Commands",
     "The /end step list: project check and secret scan, index, ledger reconciliation, state docs, commit, clean tree."),
    ("project-file", "claude-project-template/project/CLAUDE.md", "Project skeleton",
     "The outlined project file: what is different about one app, with an explicit Overrides section."),
    ("protocol-json", "claude-project-template/project/.claude/protocol.json", "Project skeleton",
     "The per-project settings the scripts read: check command, push policy, skip paths, ledger caps, tracks."),
    ("ledger-skeleton", "claude-project-template/project/docs/SESSION_LEDGER.md", "Project skeleton",
     "The ledger's header rules and item shapes, including per-track IDs and tags."),
    ("current-state-skeleton", "claude-project-template/project/docs/CURRENT_STATE.md", "Project skeleton",
     "The rolling state doc's required shape, single-track and multi-track."),
    ("decisions", "DECISIONS.md", "This repo",
     "Why the Knowledge Base is shaped the way it is: every structural decision with its reason, append-only."),
    ("references", "references.md", "This repo",
     "The reading list behind the template and the tooling choices, and what was deliberately left out."),
]

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
README_ENTRY_RE = re.compile(r"^- \[([\w.\-]+\.md)\]\([^)]*\)\s+—\s+(.*)$", re.MULTILINE)


def parse_frontmatter(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    stack = []
    if "stack" in fields:
        raw = fields["stack"].strip().strip("[]")
        stack = [t.strip().strip("'\"") for t in raw.split(",") if t.strip()]
    return {
        "stack": stack,
        "kind": fields.get("kind", "").strip(),
        "last_verified": fields.get("last_verified", "").strip(),
    }, text[m.end():]


def load_descriptions():
    return dict(README_ENTRY_RE.findall((ROOT / "README.md").read_text(encoding="utf-8")))


def load_lessons():
    descriptions = load_descriptions()
    lessons = []
    for path in sorted(ROOT.glob("*.md")):
        if path.name in EXCLUDE:
            continue
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        if not meta.get("kind"):
            continue  # not a frontmatter'd lesson (a stray note, a transcript)
        title_match = TITLE_RE.search(body)
        lessons.append({
            "id": path.name,
            "title": title_match.group(1).strip() if title_match else path.stem,
            "kind": meta["kind"],
            "last_verified": meta["last_verified"],
            "stack": meta["stack"],
            "groups": sorted({TAG_GROUPS.get(tag, "Other") for tag in meta["stack"]}),
            "description": descriptions.get(path.name, ""),
            "content": body.strip(),
        })
    return lessons


def load_docs():
    docs = []
    for doc_id, rel, section, description in PROCESS_DOCS:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            content = f"# {path.name}\n\n```json\n{text.strip()}\n```\n"
        else:
            _, content = parse_frontmatter(text)
            if rel == "README.md":
                # The lessons list is the Lessons collection; keep the rest of the front door.
                cut = content.find("\n## Lessons")
                if cut != -1:
                    tail = content.find("\n## Decisions & references")
                    content = content[:cut] + "\n## Lessons\n\nEvery lesson is in the **Lessons** collection of this site, with facets, search and freshness.\n" + (content[tail:] if tail != -1 else "")
        title_match = TITLE_RE.search(content)
        docs.append({
            "id": doc_id,
            "title": title_match.group(1).strip() if title_match else path.name,
            "section": section,
            "description": description,
            "source": rel,
            "content": content.strip(),
        })
    return docs


def wrap_document(fragment):
    """Local file: wrap the fragment in a real document, head parts in <head>."""
    cut = fragment.rfind("</style>")
    cut = cut + len("</style>") if cut != -1 else 0
    head, body = fragment[:cut], fragment[cut:]
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            + head + "\n</head>\n<body>\n" + body + "\n</body>\n</html>\n")


def build():
    lessons = load_lessons()
    docs = load_docs()
    all_tags = sorted({tag for l in lessons for tag in l["stack"]})
    tags_by_group = {g: [] for g in GROUP_ORDER}
    for tag in all_tags:
        tags_by_group[TAG_GROUPS.get(tag, "Other")].append(tag)
    tags_by_group = {g: sorted(ts) for g, ts in tags_by_group.items() if ts}
    dataset = {
        "lessons": lessons,
        "docs": docs,
        "tagsByGroup": tags_by_group,
        "groupOrder": [g for g in GROUP_ORDER if g in tags_by_group],
        "kinds": sorted({l["kind"] for l in lessons}, key=lambda k: (-sum(1 for l in lessons if l["kind"] == k), k)),
        "generatedFrom": len(lessons),
    }
    data_json = json.dumps(dataset, ensure_ascii=False).replace("</", "<\\/")
    template = (ROOT / "kb-browser.template.html").read_text(encoding="utf-8")
    fragment = template.replace("__KB_DATA_JSON__", data_json)
    OUTPUT_FRAGMENT.write_text(fragment, encoding="utf-8")
    OUTPUT.write_text(wrap_document(fragment), encoding="utf-8")
    print(f"Wrote {OUTPUT.name} ({OUTPUT.stat().st_size // 1024} KB) and {OUTPUT_FRAGMENT.name}: "
          f"{len(lessons)} lessons, {len(docs)} process docs, {len(all_tags)} tags.")


if __name__ == "__main__":
    build()
