# References — reading list for future-me

Curated pointers for when you next refactor the Knowledge Base or start a new project. Not exhaustive — just things worth re-reading on demand.

## Documentation patterns

- **[Diátaxis](https://diataxis.fr/)** — The four-mode framework (tutorials / how-tos / reference / explanation). Authoritative grammar for organizing technical docs. Adopt the kinds in lesson frontmatter (already done); adopt subfolders only when lesson count crosses ~10.

## Claude Code — templates and patterns

- **[hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)** — Canonical curated list of CLAUDE.md files, hooks, status lines, slash commands, subagents. Browse-only; cherry-pick.
- **[abhishekray07/claude-md-templates](https://github.com/abhishekray07/claude-md-templates)** — Real CLAUDE.md files from HumanLayer, Cloudflare, ChrisWiles. Steal phrasing.
- **[Filip-Podstavec/claude-leverage](https://github.com/Filip-Podstavec/claude-leverage)** — Subagents + commands + hooks shipped as an installable plugin. Clean clean-tree-guard hook patterns. Read for ideas, don't install.
- **[centminmod/my-claude-code-setup](https://github.com/centminmod/my-claude-code-setup)** — Cross-session memory-bank pattern. Compare against your `HANDOFF_LOG.md` design.
- **[elizabethfuentes12/claude-code-dotfiles](https://github.com/elizabethfuentes12/claude-code-dotfiles)** — Pattern for syncing `~/.claude/` via git with explicit allowlist. Adopt if you start working on >1 machine.
- **[github/spec-kit](https://github.com/github/spec-kit)** — `/specify` → `/plan` → `/tasks` flow. Currently rejected as overkill for solo work; reconsider if scope grows.

## MCP servers

- **[modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)** — Official reference servers: filesystem, fetch, sequentialthinking, github, memory.
- **[Cloudflare MCP servers](https://developers.cloudflare.com/agents/model-context-protocol/mcp-servers-for-cloudflare/)** — Workers Bindings (D1/R2/KV), observability (logs, analytics), Browser Rendering. Already wired into `.mcp.json.template`.
- **[cloudflare/mcp-server-cloudflare](https://github.com/cloudflare/mcp-server-cloudflare)** — Source / additional CF servers as they ship.
- **[dirvine/tauri-mcp](https://mcpservers.org/servers/dirvine/tauri-mcp)** — Tauri-specific: automated UI interaction, screenshots, console logs from a running app. Niche but exactly the right stack.

## What's deliberately NOT here

- `claude-code-templates` (davila7) — kitchen-sink CLI, would dilute the curated template.
- Memory MCP knowledge graph — overlaps with `HANDOFF_LOG.md` + harness memory.
- Obsidian MCP — not on Obsidian; KB is small enough that Read/Grep wins.
- Cookiecutter generators — copy-in beats templating engines for solo workflow.
