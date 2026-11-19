---
stack: [privacy, data-format, architecture, llm-agents, git]
kind: gotcha
last_verified: 2026-11-18
---

# A shared file format leaks its source systems through field names: name fields generically when public code reads private files

**One-liner:** a private project writes local data files, and a second project whose code is pushed to a public or shared remote reads them. The data never leaves the machine, but the reader's code has to name every field it reads. A field called `<vendor>UserId` or `now.<helpdesk>` puts the vendor, the helpdesk and the shape of the private work into the public repo. Name fields for what they are (`userId`, `ticket`, `issue`) and keep system names in values only. Do it before the first line of reader code exists, and grep every commit of the public repo against a word list.

*Cove support work, 2026-11-17: per-ticket case files written by a private repo, shown by a viewer in a separate app that pushes to GitHub.*

## What happened

The first draft of the case file format had fields named after the three systems the work touched: the product's user ID, a block named after the helpdesk, and one named after the issue tracker. The files themselves live in a git-ignored folder in the private repo, so the data was safe. The viewer was not: its code would have read those fields by name, and every name would have been committed and pushed.

The fields were renamed before any viewer code existed. That cost a few minutes. After the viewer is built, the same rename means a format migration on both sides.

## The rule

- **Field names are code. Values are data.** Anything the reader must spell out to parse the file ends up in the reader's repo. Anything it only displays stays on the machine.
- **Name by role, not by system.** `userId`, `ticket`, `issue`, `site`. If the reader needs to know which system a value came from, make that a value: `"system": "..."`.
- **The same goes for enum values the reader branches on.** A status the code compares against is code. Keep those generic too, or map them on the private side.
- **Write the brief for the public side generically.** The handoff document for the session that builds the reader gets the same scan as the code.
- **Back it with a check.** Keep a word list (product, vendor, customer and staff names, internal API names) and grep the public repo's staged diff against it on every commit. The format rule prevents the leak by design; the grep catches the slip.

## Also guard the writer

The private side's writer refused to write outside a git-ignored folder, and rejected emails, phone numbers and named greetings in the text it stored. A format with generic names still leaks if a customer's name sits in a value and the folder gets committed by accident.

## Related

- [[privacy-shaped-usage-analytics]]: the same "decide what may leave before you build" habit.
- [[supervised-support-agent-modular-knowledge-and-earned-autonomy]]: the agent that writes these files.
- [[purge-secret-from-git-history]]: what the cleanup costs when a name does get pushed.
