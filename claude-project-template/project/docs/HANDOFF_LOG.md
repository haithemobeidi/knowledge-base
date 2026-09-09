# <ProjectName> — Handoff Log

Append-only one-line history of every development session. Newest entries at the bottom. Summary field hard cap ~300 characters — fact-grade detail lives in the ledger and CURRENT_STATE. A post-/end mini-wrap line covers only the delta since the previous line.

**Format (single track):** `YYYY-MM-DD HH:MM | <Phase/Block name or area> | <one-line summary incl. "Next:"> | <build status>`

**Format (multi-track):** `YYYY-MM-DD HH:MM | <track> | <Phase/Block name or area> | <summary incl. "Next:"> | <build status>` — the track field is what the start hook uses to find your track's last line.

---

<!-- Entries appended by /end. Never edit past rows. -->
