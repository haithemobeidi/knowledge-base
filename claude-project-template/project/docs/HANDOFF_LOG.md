# <ProjectName> — Handoff Log

Append-only. Newest at the bottom. One entry per session.

**Only the newest entry (per track) is ever injected at session start**, which is why
there is no length cap: it is read once, by the session that needs it, and then it is
history. Older entries stay here forever at zero cost. Never edit a past entry.

## Why this shape

It is [I-PASS](https://doi.org/10.1056/NEJMsa1405556), the handoff bundle from the
multicenter trial that cut medical errors 23% and preventable adverse events 30%
across 10,740 admissions — **with no increase in handoff duration**. Its five
elements were chosen because pilot observers found those were the ones most often
missing from real handoffs: illness severity, contingency planning, and receiver
read-back.

The two that a software handoff usually lacks are the last two: **If it fails** and
**Confirm**. A next session that only knows the happy path stalls the moment it
doesn't happen.

Keep it to the delta. A 2026 meta-analysis of 1,590 handovers found errors in ~88%,
with omission the most common — and named *excessive non-essential information* among
the leading contributing factors. Long narrative causes the loss it looks like it
prevents. Do not re-summarize the project; the reader has `CURRENT_STATE.md`.

---

## Format

```
## YYYY-MM-DD HH:MM | <track> | <Phase/Block or area>
**Status:** green | yellow | red — <what was verified, on what, when>
**Changed:** <the delta this session, short>
**Next:** <the first move, with enough context to make it>
**If it fails:** <the contingency — what to try, or what it would mean>
**Confirm:** <the one thing the next session must restate before starting>
```

- **Status** is one word first, so the receiver knows the severity before the detail.
- **Changed** is the delta only. Not the project, not last week.
- **Next** must be actionable without reading anything else. Cite ledger IDs — the
  start hook expands the ones `CURRENT_STATE`'s NEXT ACTION names.
- **If it fails** is the element most often missing and the cheapest to write.
- **Confirm** is the read-back: what the next session states back before starting.
  If it cannot be stated from this entry, the entry is not finished.

Single-track repos drop the `<track>` field. A post-`/end` mini-wrap appends an entry
covering **only** the delta since the previous one.

---

<!-- Entries appended by /end. Never edit past entries. -->
