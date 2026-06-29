---
stack: [supabase, postgres, powersync, security]
kind: howto
last_verified: 2026-06-29
---

# Supabase RLS when YOUR server (not the Supabase SDK) fronts the database

**One-liner:** If your app reaches Postgres through your own backend + a replication-based sync layer (PowerSync, ElectricSQL, etc.) instead of the Supabase client SDK, RLS is **not** your authorization model — but you must still **enable RLS deny-all** to lock the auto-generated PostgREST/anon API that Supabase ships **on by default**.

---

## The trap (it bites in both directions)

Two opposite mistakes, both common:

1. **"Just enable RLS and you're secure."** False when your auth is app-level. RLS with per-tenant *policies* is a heavy architectural commitment — policy design across tables, request-scoped DB roles, extra roundtrips, and real slowdown on serverless (e.g. ~2x on Cloudflare Workers + Hyperdrive, because request-scoped context means transactions and no connection-pool caching). If your isolation already lives in your server (scoped queries) + sync rules, you do **not** want RLS as your auth model. (See the widely-shared *"Just enable RLS and you won't be hacked — no, it's not that simple"* critique — it's correct, for the model it describes.)

2. **"We don't use the Supabase API, so RLS doesn't matter."** Also false. Supabase auto-generates a **PostgREST REST + GraphQL API on every project, enabled by default**, reachable with the **anon key** — which is *designed to be public/shippable*. If your tables have RLS **off**, anyone with the project ref + anon key can read/write every row through that API, **bypassing your server entirely.** That's the actual disaster the "enable RLS" warnings are about.

---

## The resolution: deny-all backstop (no policies)

Enable RLS with **zero policies** on every public table:

```sql
alter table public.<each_table> enable row level security;
```

This is essentially **free** in this architecture, because your two real access paths bypass RLS:

- **Writes** go through your server as the **table-owner role** (Supabase pooler default user `postgres.<ref>` = the `postgres` owner). Table owners **bypass RLS** unless you set `FORCE ROW LEVEL SECURITY` (don't). Writes unaffected.
- **Reads/sync** go through **logical replication** (PowerSync/Electric read the WAL). Replication is **not subject to RLS at all**; per-user row filtering happens in the **sync rules** (`SELECT * FROM t WHERE user_id = auth.user_id()`), not RLS. Sync unaffected.

So deny-all RLS locks only the `anon`/`authenticated` PostgREST surface — the door you don't use — while leaving the doors you do use wide open. It's a **backstop, not your auth model.** Your real isolation stays in the server's owner-stamped, scoped queries + the sync rules.

Note: none of the "RLS is slow/complex" objections apply here — there are **no policies** to design and **no query-path cost** (your app never queries through an RLS-bound role).

---

## Foot-guns

- **Never add `FORCE ROW LEVEL SECURITY`** with no policies — it subjects the owner role to RLS too and denies every write → "production returns empty for everyone." This is the single way to brick it.
- **Verify the connection role is the owner** before enabling. If your server connects as a *non-owner* role, deny-all would block its writes. (Check the username in `DATABASE_URL` — pull just the part before the password.)
- **Instantly reversible**: `alter table ... disable row level security`. So "enable → smoke-test one write → roll back if it breaks" is a completely safe loop. The scary "empty data" outcome is a 5-second revert here, not a disaster.
- **Codify it as a migration** (`NNNN_enable_rls.sql`), not ad-hoc dashboard SQL, so a rebuild re-applies it. Idempotent — re-enabling an already-enabled table is a no-op.
- Supabase's **Security Advisor** flags RLS-disabled public tables; deny-all clears those warnings too.

---

## When you WOULD want real per-tenant policies

Only if you later let clients hit Supabase **directly** — e.g. a mobile app using the Supabase SDK instead of routing through your own server. Then you're back in the heavy per-tenant-policy world (and should weigh the serverless cost). As long as everything funnels through your own server + sync layer, deny-all is the right and cheap posture.

---

## Checklist for a new Supabase + own-backend project

1. Server connects as the `postgres` owner via the pooler `DATABASE_URL`. ✓ bypasses RLS.
2. Sync layer (PowerSync/Electric) does per-user filtering in **sync rules**, not RLS. ✓
3. Ship a `NNNN_enable_rls.sql` migration: `enable row level security` on **every** public table, **no policies, no FORCE**.
4. Smoke-test one write after enabling — confirms the owner bypass holds.
5. Authorization itself lives in the server (stamp `user_id` server-side, scope every write `WHERE user_id = <session>`). RLS is the backstop, that is the lock.

---

*Captured from the Playmoir pre-paywall security pass, 2026-06-29. Backend context: see [`powersync-steam-backend-architecture.md`](./powersync-steam-backend-architecture.md).*
