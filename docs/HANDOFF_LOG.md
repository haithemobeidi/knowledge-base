# Knowledge Base — Handoff Log

Append-only, newest at the bottom. One entry per session that did multi-step work
here (a template change, a mining pass, a site rebuild). A single lesson written
and committed does not need an entry — its commit message is the record.

Format is the template's own I-PASS shape, so this repo eats its own cooking:

```
## YYYY-MM-DD HH:MM | <area>
**Status:** green | yellow | red — <what was verified>
**Changed:** <the delta>
**Next:** <the first move, with enough context to make it>
**If it fails:** <the contingency>
**Confirm:** <what the next session restates before starting>
```

---

## 2026-09-20/21 | Protocol v2 — audit, research, build

**Status:** green — all scripts syntax-checked; both new checks validated against Playmoir's real documents and made to fail on purpose; the v1 path verified unchanged (hook still emits valid JSON at its usual size). Committed and pushed as `70dc989`.

**Changed:** Audited the v1 harness against a live 3-track project and measured session start at 163,478 chars (~41,000 tokens) — five times a normal full Claude Code startup payload, 56% of it `CURRENT_STATE.md`. Traced the cause: the 2026-09-08 ledger caps worked and the mass moved to the one adjacent uncapped document, growing it from 5,968 to 92,900 characters in twelve days. Researched context engineering, agent memory systems, and human shift-handover practice (four subagents, findings in the session scratchpad). Wrote `DESIGN.md`, then built v2: one budget on the assembled payload plus `check-payload-budget.py`; a ledger manifest (61,376 → 12,813 chars measured, all 89 items still listed); `check-ledger-refs.py` for struck IDs still cited in state docs; three v2 document shapes; the I-PASS handoff format; an ACCEPT read-back at `/start`. Fixed two v1 bugs found in the audit: a no-upstream branch reporting "checkout is current" from a fetch that proved nothing, and the ledger's 3,071-char rules header being injected every session despite living in `PROTOCOL.md`.

**Next:** Write `migrate-docs-v2.py`. It must write `.new` files beside the originals and never replace anything — every verb in the migration is *append* or *move*, never delete or summarize. The big piece is mechanical: all 30 session blocks in Playmoir's `CURRENT_STATE.md` carry an ordinal (153rd down to 120th) and all 30 have a matching `HANDOFF_LOG` line, so the narrative merges by joining on the ordinal. The only judgment call is the 38 "Things to watch" bullets, which go to the user as one table (still live / standing fact / obsolete), the same shape `MIGRATION.md` already uses for legacy tag triage.

**If it fails:** If the ordinal join misses entries, do not fall back to summarizing — leave the unmatched blocks in place and report them. Losing detail is worse than a partial migration; the whole design rests on nothing being rewritten. If the migrated payload lands above 25,000 chars, shrink the largest contributor rather than raising the budget: raising it is how v1 failed.

**Confirm:** v2 is **inert** until a project sets `protocol_version: 2`. Before touching Playmoir, restate that syncing the scripts alone changes nothing, and that the 95KB `CURRENT_STATE` comes down only when the documents are migrated — not when the scripts are.

**Also worth knowing:** two claims made during this session were wrong and retracted — that a count of 22 open ledger items citing closed items indicated missed closures (they are provenance and sequencing citations; the ledger is well-kept), and a routing-detection check built on that premise (dropped; it would have false-positived on the first case examined). Do not resurrect either without new evidence. The four research findings files are in the session scratchpad only and will not survive; `DESIGN.md` carries the citations that mattered.
