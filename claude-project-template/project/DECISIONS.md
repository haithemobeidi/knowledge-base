# <ProjectName> — Decisions

Append-only log of architectural and process decisions with rationale. Newest at the bottom. Never rewrite a past entry — supersede it with a new one that names what it replaces. Read on demand (the project file links here); not auto-loaded.

Entry shape: **Decision** (what) / **Why** (the evidence or the incident) / **How to apply** (what a future session does differently). Date every entry.

---

## <YYYY-MM-DD> — Bootstrapped from claude-project-template

**Decision:** Adopt the session protocol (global work style + protocol imported from the Knowledge Base; per-project settings in `.claude/protocol.json`; hook-enforced codebase index; moment-of-event ledger).

**Why:** Re-deriving these per project was wasted ceremony, and copies drift.

**How to apply:** Project differences go in `CLAUDE.md` (rules, pointers, explicit overrides) and `protocol.json` (scripts' settings). The scripts stay byte-identical to the template; `check-template-drift.py` reports when they are behind.

---

<!-- Template for the standing-push decision, if you set push_policy: "standing":

## <YYYY-MM-DD> — Standing authorisation for session-end git push

**Decision:** `/end` and mini-wraps may `git push` without asking, so work continues from another machine without ceremony. Force pushes still require per-instance confirmation.

**Why:** <the user works on two machines; the next session's start reads state from the remote>.

**How to apply:** `push_policy: "standing"` in `.claude/protocol.json`. If a push is rejected, report and stop; never retry destructively.
-->
