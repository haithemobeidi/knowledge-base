---
stack: [any, postgres, migrations, deploy, fly-io]
kind: gotcha
last_verified: 2026-11-01
---

# A deploy can land without its migration and look healthy, because the code's own graceful-degrade guard hides the missing table

**One-liner:** If deploying the code and running the migration are separate steps, the code can go live without the migration. A guard written so deploy order can't cause errors ("if the table isn't there yet, skip the feature") will then cover the gap: the app stays up, health checks pass, and the only sign is one warning in a log. Verify a migration by reading the migration ledger table (after a dry run), never from the deploy's success or the app's health. A guard that degrades gracefully must also be loud about what it's skipping.

## The shape

Playmoir's server is a Node app on Fly with Postgres migrations run by hand (`node migrate.js --dry-run`, then `npm run migrate`). A deploy does not run them. Release v168 added a global art table (migration 0033) and code that fills it from Steam in the background.

The code was written to survive either deploy order. A check (`artTableReady()`) asked whether the table existed; if not, the background fill was skipped, the library route served its rows without the new data, and one `console.warn` line was printed. That was the right call for availability. A missing table never caused a 500.

v168 was reported deployed with its migrate. The app was up, the library loaded, and nothing looked broken. Reading `public._migrations` showed it stopped at 0032. Migration 0033 had never run, so the feature the release existed for was doing nothing, and only one log line out of thousands said so. Running the dry run and then the migrate created the table. The fill was then verified by counting rows (408 of 408 games).

## Why it hides

- A graceful-degrade guard is built to make "the dependency isn't there" look like normal operation. That is its job, and it does the same job when the dependency is missing by mistake.
- Health checks test that the process answers, not that the release's feature runs.
- A two-step deploy reports each step on its own. The visible step (code live, new version number) feels like the whole deploy.

## The rule

1. After any deploy that carries a migration, read the migration ledger table and confirm the newest migration's name is there. Run the dry run first: it lists what is pending, so "nothing pending" after the real run is itself the check.
2. Then confirm the feature did its first unit of work (here: rows appeared in the new table), not just that the app is healthy.
3. Make the guard loud. Log it at warning or error level with the migration's name ("table X missing, migration 0033 not run, art fill disabled"), and better still expose it on a status route or startup check that a post-deploy probe can read. "Skipped quietly" is fine for a few seconds of deploy order, not for a whole release.
4. If the platform allows it, run migrations as part of the release (a release command that fails the deploy when the migration fails), so the two steps can't come apart.

## Related

- [[sql-migration-runner-auto-baseline]]: the runner this project uses (dry run, per-migration transactions).
- [[silent-refusals-make-clean-logs-meaningless]]: the same family, a failure designed to be invisible.
- [[negative-control-before-trusting-a-probe]]: a post-deploy probe that can't come back red tells you nothing.
