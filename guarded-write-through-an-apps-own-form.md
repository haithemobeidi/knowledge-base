---
stack: [web, javascript, browser-automation, graphql, data-safety, llm-agents, customer-support]
kind: pattern
last_verified: 2026-11-17
---

# Change one field on a live record through the app's own form: a backup before, a save guard during, a diff after

**One-liner:** an agent has to change a real customer's record, and the app's update call sends the whole object, nulling any field left out. Don't hand-build the API call. Back up the record. Make the change in the app's own edit form. Hook `fetch` and XHR so the save is blocked unless only the named field differs. Then re-read the record and diff it against the backup. Report the changed fields: only the named one should appear.

*Cove, 2026-11-17: an agent moved a user to another company (tenant) at a customer's building, with the support lead watching. The guard passed, and the diff showed exactly one changed field. The scope rule comes from the lead: "if the task is change tenant only ever change that".*

## Why not the API

The app's user-update mutation takes the entire user object. The notes from an earlier bulk job on the same app spell out the risk: a hand-built payload nulls every field it omits, and that's how you wipe a thousand people's phone numbers, tags and opt-outs. The app's own form always sends a complete object, read fresh from the server. So the form is the safe way to write, and the guard is what proves it sent only the change you meant.

## The steps

1. **Get the go** for this one change, on this record.
2. **Back up** the record, using the same read the edit page uses, to a local file outside version control.
3. **Open the edit form** and change only the named field.
4. **Guard the save.** Before clicking Save, wrap `fetch` and `XMLHttpRequest.prototype.send`. If the outgoing body is the update operation, compare it with the backup and block it on any surprise:

   ```js
   const before = JSON.parse(sessionStorage.getItem('backup'));
   const check = body => {
     const j = JSON.parse(body);
     if (!/update/i.test(j.operationName || '')) return null;
     const inp = j.variables.input, problems = [];
     if (j.variables.id !== before.id) problems.push('wrong record');
     if (inp.role !== before.role) problems.push('role changed');
     if (inp.email !== before.email) problems.push('email changed');
     if (inp.accountStatus !== before.accountStatus) problems.push('status changed');
     const ids = inp.companyIds || [];
     if (!ids.includes(TARGET) || ids.includes(OLD)) problems.push('target not set cleanly');
     return problems;
   };
   // In the fetch wrapper: if check(body) has problems, return Promise.reject(...) instead of sending.
   // In the XHR wrapper: call this.abort() and don't send.
   ```

   Keep the backup in `sessionStorage`: it survives the app's client-side navigation after Save.
5. **Save, re-read, diff.** List the fields that differ from the backup. The report names them. Anything beyond the named field means stop and tell the human.

## Clicking safely

List rows often put edit, delete and email-invite icons side by side, a few pixels apart. Zoom in before clicking, click only the edit icon, and confirm the form that opens is the right record before changing anything.

## What it doesn't cover

The guard checks the record, not what the field drives. A company change can also move a user's door-access mapping, if each company maps to a different access-control group. Look at the downstream mapping before saving, and say what it will do in the report.

## Related

- [[capture-a-spas-own-api-calls-with-a-fetch-hook]]: the same hook, used to learn reads.
- [[supervised-support-agent-modular-knowledge-and-earned-autonomy]]: where this sits in the agent's rules.
- [[negative-control-before-trusting-a-probe]]
