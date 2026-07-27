#!/usr/bin/env python3
"""Regenerate kb-browser.html from the root-level lesson .md files.

Scans every lesson file (root-level .md, excluding README/DECISIONS/references
and the claude-project-template/ skeleton), parses its `stack` / `kind` /
`last_verified` frontmatter, pulls the curated one-liner out of README.md's
Lessons list, and embeds the whole dataset as JSON inside a self-contained
HTML file with a faceted filter UI. No server, no build step beyond this
script, no external dependencies (stdlib only).

Run this after adding or editing a lesson:
    python build-kb-browser.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
EXCLUDE = {"README.md", "DECISIONS.md", "references.md"}
OUTPUT = ROOT / "kb-browser.html"

# Tag -> facet group, for the sidebar. Falls back to "Other" for anything
# not listed here, so a new tag on a future lesson never breaks generation.
TAG_GROUPS = {
    # Languages
    "rust": "Languages", "typescript": "Languages", "javascript": "Languages",
    "sql": "Languages", "css": "Languages",
    # Frameworks & libraries
    "react": "Frameworks & Libraries", "framer-motion": "Frameworks & Libraries",
    "tailwind": "Frameworks & Libraries", "zod": "Frameworks & Libraries",
    "sqlx": "Frameworks & Libraries", "tokio": "Frameworks & Libraries",
    "better-auth": "Frameworks & Libraries", "animation": "Frameworks & Libraries",
    "design-system": "Frameworks & Libraries", "frontend": "Frameworks & Libraries",
    "state-management": "Frameworks & Libraries",
    # Platforms & runtimes
    "tauri": "Platforms & Runtimes", "electron": "Platforms & Runtimes",
    "capacitor": "Platforms & Runtimes", "node": "Platforms & Runtimes",
    "vite": "Platforms & Runtimes", "webview2": "Platforms & Runtimes",
    "windows": "Platforms & Runtimes", "desktop": "Platforms & Runtimes",
    "desktop-overlay": "Platforms & Runtimes", "mobile": "Platforms & Runtimes",
    "ios": "Platforms & Runtimes", "android": "Platforms & Runtimes",
    "multiwindow": "Platforms & Runtimes", "threads": "Platforms & Runtimes",
    # Cloud & backend
    "cloudflare-worker": "Cloud & Backend", "cloudflare-r2": "Cloud & Backend",
    "d1": "Cloud & Backend", "wrangler": "Cloud & Backend", "s3": "Cloud & Backend",
    "s3-compatible": "Cloud & Backend", "presigned-urls": "Cloud & Backend",
    "aws4fetch": "Cloud & Backend", "fly-io": "Cloud & Backend",
    "supabase": "Cloud & Backend", "supabase-postgres": "Cloud & Backend",
    "postgres": "Cloud & Backend", "sqlite": "Cloud & Backend",
    "http-api": "Cloud & Backend", "graphql": "Cloud & Backend",
    # Data & sync
    "powersync": "Data & Sync", "local-first": "Data & Sync",
    "local-first-sync": "Data & Sync", "sync": "Data & Sync",
    "offline-first": "Data & Sync", "distributed-systems": "Data & Sync",
    "codegen": "Data & Sync", "monorepo": "Data & Sync",
    "pnpm-monorepo": "Data & Sync", "migrations": "Data & Sync",
    # Auth & security
    "auth": "Auth & Security", "jwt": "Auth & Security", "sessions": "Auth & Security",
    "security": "Auth & Security", "azure": "Auth & Security", "azure-cli": "Auth & Security",
    "entra-id": "Auth & Security", "trusted-signing": "Auth & Security",
    "azure-trusted-signing": "Auth & Security", "code-signing": "Auth & Security",
    "smartscreen": "Auth & Security", "distribution": "Auth & Security",
    "chrome": "Auth & Security", "git": "Auth & Security", "steam-openid": "Auth & Security",
    # Integrations
    "api-integration": "Integrations", "monetization": "Integrations",
    "steam": "Integrations", "vdf": "Integrations", "game-library-integration": "Integrations",
    # Reliability & perf
    "sentry": "Reliability & Perf", "crash-reporting": "Reliability & Perf",
    "performance": "Reliability & Perf", "dom": "Reliability & Perf",
    # Process & meta
    "any": "Process & Meta", "refactoring": "Process & Meta",
    "codebase-audit": "Process & Meta", "docs": "Process & Meta",
    "tooling": "Process & Meta", "claude-code": "Process & Meta",
}

GROUP_ORDER = [
    "Languages", "Frameworks & Libraries", "Platforms & Runtimes",
    "Cloud & Backend", "Data & Sync", "Auth & Security", "Integrations",
    "Reliability & Perf", "Process & Meta", "Other",
]

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
README_ENTRY_RE = re.compile(
    r"^- \[([\w.\-]+\.md)\]\([^)]*\)\s+—\s+(.*)$", re.MULTILINE
)


def parse_frontmatter(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    block = m.group(1)
    body = text[m.end():]
    fields = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
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
    }, body


def load_descriptions():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    return dict(README_ENTRY_RE.findall(readme))


def build():
    descriptions = load_descriptions()
    lessons = []
    for path in sorted(ROOT.glob("*.md")):
        if path.name in EXCLUDE:
            continue
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        if not meta.get("kind"):
            continue  # not a frontmatter'd lesson (shouldn't happen for root .md)
        title_match = TITLE_RE.search(body)
        title = title_match.group(1).strip() if title_match else path.stem
        groups = sorted({TAG_GROUPS.get(tag, "Other") for tag in meta["stack"]})
        lessons.append({
            "id": path.name,
            "title": title,
            "kind": meta["kind"],
            "last_verified": meta["last_verified"],
            "stack": meta["stack"],
            "groups": groups,
            "description": descriptions.get(path.name, ""),
            "content": body.strip(),
        })

    all_tags = sorted({tag for l in lessons for tag in l["stack"]})
    tags_by_group = {g: [] for g in GROUP_ORDER}
    for tag in all_tags:
        tags_by_group[TAG_GROUPS.get(tag, "Other")].append(tag)
    tags_by_group = {g: sorted(ts) for g, ts in tags_by_group.items() if ts}

    all_kinds = sorted({l["kind"] for l in lessons})

    dataset = {
        "lessons": lessons,
        "tagsByGroup": tags_by_group,
        "groupOrder": [g for g in GROUP_ORDER if g in tags_by_group],
        "kinds": all_kinds,
        "generatedFrom": len(lessons),
    }
    data_json = json.dumps(dataset, ensure_ascii=False).replace("</", "<\\/")

    template = (ROOT / "kb-browser.template.html").read_text(encoding="utf-8")
    html = template.replace("__KB_DATA_JSON__", data_json)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(lessons)} lessons.")


if __name__ == "__main__":
    build()
