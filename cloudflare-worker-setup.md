---
stack: [cloudflare-worker, d1, wrangler]
kind: recipe
last_verified: 2026-05-14
---

# Cloudflare Worker + D1 Setup (from zero to deployed)

> The exact sequence. No fluff.

## Prerequisites

- Cloudflare account (free tier is fine)
- `wrangler` installed (`npx wrangler` works without global install)
- A Worker project with `wrangler.toml`

## Step 1 — Log in

```bash
cd apps/cloud
npx wrangler login
```

Opens browser, authorizes the CLI. One-time.

## Step 2 — Create D1 database

```bash
npx wrangler d1 create my-db-name
```

Output gives you the database ID. Copy it into `wrangler.toml`:

```toml
[[d1_databases]]
binding = "DB"
database_name = "my-db-name"
database_id = "93857ccf-5d2b-47e6-b7d4-e449eac51cf6"  # from output above
migrations_dir = "migrations"
```

## Step 3 — Apply migrations

Put your schema in `migrations/0001_initial.sql`:

```sql
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  -- ...
);
```

Apply to remote:

```bash
npx wrangler d1 migrations apply my-db-name --remote
```

Apply to local (for `wrangler dev`):

```bash
npx wrangler d1 migrations apply my-db-name --local
```

## Step 4 — Set secrets

Secrets are env vars that don't go in `wrangler.toml` (which is in git). Set them via CLI:

```bash
echo "your-secret-value" | npx wrangler secret put MY_SECRET_NAME
```

Or interactively:

```bash
npx wrangler secret put MY_SECRET_NAME
# paste value when prompted
```

For a random session signing secret:

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))" | npx wrangler secret put SESSION_SECRET
```

## Step 5 — Deploy

```bash
npx wrangler deploy
```

Output gives you the Worker URL: `https://my-worker.your-account.workers.dev`

## Step 6 — Local dev

```bash
npx wrangler dev --local --port 8787
```

Runs on `http://localhost:8787`. Use `--local` to use a local D1 mirror; without it, `wrangler dev` hits the real D1 (which is usually what you want for integration testing).

## Gotchas

1. **R2 buckets require enabling** — first time you try to create one, you'll get `error code 10042`. Enable R2 in the Cloudflare dashboard once per account, then it works from CLI.

2. **Custom domains** — the `.workers.dev` URL is free and works forever. You don't need a custom domain for production. Add one later via Cloudflare dashboard → your Worker → Triggers → Custom Domains. No code changes needed.

3. **Secrets can't be read back** — once set via `wrangler secret put`, you can't view the value. Only rotate/delete. Keep a copy in a password manager if you need to reference them.

4. **`.dev.vars` for local dev** — put local-only secrets in `apps/cloud/.dev.vars` (gitignored). `wrangler dev` reads them automatically:
   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   ```

5. **D1 database IDs are per-environment** — if you want separate dev/staging/prod databases, create three and use Wrangler environments:
   ```toml
   [env.production]
   [[env.production.d1_databases]]
   binding = "DB"
   database_id = "prod-id-here"
   ```

6. **wrangler.toml changes don't require redeploy to take effect locally** — just restart `wrangler dev`. But remote changes always need `wrangler deploy`.

7. **Check the deployed Worker version** — `wrangler deployments list` shows history. `wrangler rollback <version-id>` reverts.

8. **wrangler crashes on ARM64 Windows hosts** — on Snapdragon X / ARM64 Windows machines (Surface Pro 11, etc.), `wrangler tail` and `wrangler deploy` both crash with a native binary error. The Node.js binary wrangler ships uses an x64-only native module. **Fix: run wrangler from WSL** (`wsl bash -c "cd /mnt/c/... && npx wrangler deploy"`) or from a separate x64 dev machine. We hit this when deploying from an ARM64 laptop in May 2026; WSL runs the x64 binary fine under emulation. As of writing (2026-05) there is no native ARM64 wrangler build.

## Quick health check endpoint

Always add this — saves debugging time:

```typescript
app.get('/api/health', async (c) => {
  try {
    const result = await c.env.DB.prepare('SELECT 1 as ok').first();
    return c.json({ status: 'ok', db: result?.ok === 1 });
  } catch {
    return c.json({ status: 'error', db: false }, 500);
  }
});
```

Then `curl https://your-worker.workers.dev/api/health` tells you everything's wired up.

## CORS for native/mobile apps

If your Worker serves a native app (Tauri, Capacitor, mobile), you need permissive CORS:

```typescript
import { cors } from 'hono/cors';

app.use('/api/*', cors({
  origin: [
    'http://localhost:1420',     // Tauri dev
    'tauri://localhost',          // Tauri prod (macOS)
    'https://tauri.localhost',    // Tauri prod (Windows/Linux)
    'capacitor://localhost',      // Capacitor iOS
    'http://localhost',           // Capacitor Android
  ],
  allowHeaders: ['Content-Type', 'Authorization'],
  allowMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  credentials: true,
}));
```

Note: for native apps, **don't rely on cookies** (different origins, cookie jars don't match). Use bearer tokens instead. See `tauri-desktop-oauth.md`.
