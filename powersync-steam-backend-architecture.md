---
stack: [powersync, supabase-postgres, cloudflare-r2, fly-io, steam-openid, jwt, tauri]
kind: architecture
last_verified: 2026-07-20
---

# Backend, Auth & Sync — the managed-services rearchitecture (PowerSync + Steam + Postgres + R2)

> The second backend Playmoir was built on. The first (see [local-first-sync-with-d1.md](./local-first-sync-with-d1.md)) was a hand-rolled sync engine on Cloudflare D1 + Google auth. This one replaces the hand-rolled sync with an off-the-shelf engine (PowerSync), swaps Google login for Steam, and moves the source-of-truth DB to Postgres. This doc is the mental model + the auth flow in detail + the strategic reasoning (build-vs-buy, self-hosting economics, vendor lock-in) so the choices are explainable to a non-engineer.

---

## The 30,000-ft view: 1 server, 3 storage layers, 1 sync engine

```
            ┌──────────────────────────────────────────────┐
            │              YOUR DEVICE (desktop)            │
            │                                               │
            │  React UI ──reads──► Local SQLite (fast,      │
            │                       works offline)          │
            │                          ▲   │                │
            │            write-through │   │ local writes   │
            │                          │   ▼                │
            │                   PowerSync client (appDb)    │
            └───────────────────────────┬───────────────────┘
                                         │  (sync, both directions)
              ┌──────────────────────────┼───────────────────────────┐
              │                           │                           │
   ┌──────────▼──────────┐   ┌────────────▼────────────┐   ┌──────────▼──────────┐
   │  PowerSync Cloud    │   │  Write server (Fly.io)  │   │  Cloudflare R2      │
   │  (sync engine)      │   │  Hono / Node 22         │   │  (blob storage)     │
   │  streams Postgres   │   │  • verifies identity    │   │  screenshot/audio   │
   │  rows → clients     │   │  • applies CRUD writes  │   │  bytes              │
   └──────────┬──────────┘   │  • presigns R2 URLs     │   └─────────────────────┘
              │              │  • Steam library sync   │
   ┌──────────▼──────────┐   └────────────┬────────────┘
   │  Supabase Postgres  │◄───── writes ───┘
   │  (source of truth)  │
   └─────────────────────┘
```

**Four moving parts:**

| Part | What it is | Where it runs | Could we swap it? |
|---|---|---|---|
| **Write server** | Small Node.js (Hono) app — the gatekeeper. Checks who you are, applies writes, presigns file URLs, syncs Steam library. | Fly.io (`playmoir-server.fly.dev`) | **Easily** — it's a normal Node server; any host runs it. |
| **Postgres** | Cloud "master copy" of games, journal entries, screenshot/audio rows. | Supabase | **Easily** — Postgres is Postgres; move to any Postgres host or self-host. |
| **R2** | Object storage for the actual *bytes* of screenshots/audio. | Cloudflare | **Easily** — R2 speaks the S3 API; any S3-compatible store works. |
| **PowerSync** | Off-the-shelf **sync engine** keeping cloud Postgres ↔ each device's local SQLite mirrored automatically. | PowerSync hosted cloud | **This is the one real lock-in.** Proprietary. Replacing it means rebuilding sync (which is exactly what we tore out). |

**The core idea:** the app reads/writes its *own local database* (fast, offline-capable). PowerSync silently shuttles changes between that local DB and cloud Postgres in both directions, so multiple devices converge. The write server is the bouncer deciding what's allowed and stamping ownership.

**Why this over the hand-rolled D1 version:** we didn't *build* the sync logic this time — we plugged in a product. The previous backend was ~13 hard-won sync patterns (outbox, field-level LWW, tombstones, chunking that preserves row identity...) that each cost a production incident to learn. Buying that off the shelf is the "don't reinvent the wheel" principle applied to the single hardest part of the system.

---

## Authentication — the full flow

### One big idea: **Steam is the login. There are no passwords.**

Playmoir never sees a password. It delegates "prove who you are" entirely to **Steam via OpenID 2.0**. Steam vouches for you and returns one thing: your **SteamID64** (a unique number). That SteamID *is* your user identity everywhere — every game, entry, screenshot, and audio row is stamped with it.

(There used to be a Google login — now retired. See "The migration tail" below.)

### The sign-in dance (a relay race)

1. **Desktop opens a local "mailbox."** It starts a tiny loopback web server on your machine (`127.0.0.1:<random-port>`, via `tauri-plugin-oauth`) whose only job is to catch a reply later. It also generates a random **nonce** (anti-tampering / CSRF).
   - `packages/frontend/src/features/auth/useSteamSignIn.ts`

2. **Browser opens to our Fly server**, which immediately **302-redirects to Steam's login page** (OpenID `checkid_setup`, `identifier_select` mode = "Steam, tell us whoever's logged in").
   - `apps/server/src/index.js` → `/auth/steam/start`

3. **You log into Steam.** Steam does the real identity check and signs an assertion.

4. **Steam redirects back to our Fly server** with the signed assertion as query params (`openid.mode=id_res`, `openid.sig`, `openid.identity`, ...).
   - `apps/server/src/index.js` → `/auth/steam/callback`

5. **Our server re-verifies the assertion with Steam.** Critically it does **not** trust the assertion at face value — it POSTs it *back* to Steam with `openid.mode=check_authentication` and only proceeds if Steam replies `is_valid:true`. This is what defeats a forged "I'm logged in as X" note. It then extracts the SteamID64 from the `openid.identity` URL.
   - `apps/server/src/auth/steam-openid.js` (xPaw's hardened validator, ported from PHP)
   - **Why Fly, not Cloudflare Workers:** Steam 403s these `check_authentication` callbacks from Cloudflare's network. A normal long-running server avoids it. This single requirement drove the choice of host.

6. **Server records the user + mints a session token.** `upsertUser(steamId)` writes a `users` row (SteamID PK, persona name, avatar — fetched best-effort from Steam's profile XML). `mintSession(steamId)` signs a **30-day HS256 JWT** (subject = SteamID, secret = `SESSION_SECRET`).
   - `apps/server/src/auth/users.js`, `apps/server/src/auth/session.js`

7. **Server redirects to the local mailbox** (`http://127.0.0.1:<port>/?token=<jwt>&steam_id=...&state=<nonce>`). The desktop checks the nonce matches, then **stores the session token in local SQLite** (`sync_meta` KV table).
   - `apps/desktop/src-tauri/src/commands/steam_auth.rs` → `steam_store_session`

That session token is now your "I'm signed in" badge — 30 days, reused silently on every launch.

### The two-token system (the crux — understand this and you've got auth)

There are **two** tokens doing **different jobs**:

**Token 1 — the session token ("your house key").**
- Minted at sign-in, 30-day HS256 JWT, stored on device.
- Proves "I am SteamID X" to *our* server.
- Sent as `Authorization: Bearer <token>` on every call to our server (library sync, writes, presign requests).

**Token 2 — the PowerSync token ("a 5-minute visitor pass").**
- PowerSync is a separate company's service; it won't accept our house key directly.
- When the app needs to sync, it shows its house key to *our* server (`POST /auth/powersync-token`) and our server mints a **short-lived (5-min) RS256 JWT** signed with our **private** key.
- PowerSync verifies that pass is genuinely ours using our **public** key, published as a JWKS at `GET /keys`.
- `apps/server/src/auth/powersync-token.js`, `packages/frontend/src/features/powersync/connector.ts` → `fetchCredentials()`

**Why two?** *Separation of trust.* The long-lived key never leaves the device↔our-server relationship. The thing handed to a third party is deliberately short-lived and narrowly scoped — useless within 5 minutes if leaked. (HS256 vs RS256 matters here: the session token is symmetric — only our server needs to verify it. The PowerSync token is asymmetric — a *third party* must verify it without holding a secret, so we sign with a private key and publish the public one.)

### Stateless auth: how the server knows you without remembering you

The server keeps **no sessions table.** The session token is a **JWT** — a small signed bundle (SteamID + expiry) sealed with a server-only secret. On each request the server just checks the signature + expiry (like a banknote watermark) and reads the SteamID straight out. No DB lookup.

Payoff: the server can be **cloned across many machines** with none of them sharing a memory of who's logged in. Any instance verifies any token alone. This is what makes horizontal scaling trivial — and it matters for the self-hosting discussion below.

### The security guarantee that makes multi-user safe

**The server stamps your identity onto your data — it never trusts the client to declare who it is.**

When the app sends a write, it includes a `user_id`. The server **discards it** and substitutes the SteamID from the verified token, and every write is scoped `WHERE user_id = <you>`. So a malicious client *cannot* write under someone else's account or modify a row it doesn't own — enforced in the SQL itself, not on the honor system.
- `apps/server/src/db.js` → `applyOp()` + the `WRITABLE` column allowlist (also the SQL-injection guard: only allowlisted tables/columns ever reach the query string, since table + column names are interpolated, not parameterized).

**Non-obvious gotcha with the `WRITABLE` allowlist: a PowerSync CRUD op carries the row's full replicated-column set, not just the columns your local statement touched.** Client-side, `UPDATE games SET playtime_minutes = ? WHERE id = ?` looks column-scoped — but PowerSync's CRUD queue serializes the op from its *watched table schema*, so the batch that reaches `applyOp()` can include every replicated column on that row, not only `playtime_minutes`. If a server-authoritative column (one only the server itself is ever supposed to set) isn't in `WRITABLE`, the whole op — including the one column you actually meant to write — gets rejected, not just silently dropped. Symptom: adding a new synced column and forgetting to add it to `WRITABLE` doesn't just mean "that column never updates," it can mean *every* unrelated create/edit on that table starts failing the moment a client happens to have that column staged in its CRUD op. Add a new replicated column to `WRITABLE` in the same commit that adds it anywhere else — see `n-copies-of-truth-drift-guard.md`.

---

## File storage without handing out keys — presigned URLs

Screenshot/audio **bytes** don't flow *through* our server (slow + expensive), and we can't ship R2 credentials inside a desktop app (a secret in a client isn't secret). The fix is a **presigned URL** — valet parking for uploads:

1. App asks our server: "I want to upload object `<uuid>`." (`POST /attachments/presign-upload`, with the session token.)
2. Server — which holds the R2 creds (Fly secrets) — generates a **single-use, 5-minute, pre-authorized URL** that grants write to **exactly that one object**, namespaced under the caller's SteamID: `screenshots/<steamid>/<uuid>` (audio: `audio/<steamid>/<uuid>`). The SteamID comes from the verified token, so the URL physically can't target anyone else's files.
   - `apps/server/src/attachments/r2.js` (`aws4fetch` SigV4 signer; `presignPut` / `presignGet`)
3. App uploads bytes **straight to R2** with that URL. Download is the same in reverse.
4. On the desktop, the upload/download is done in **Rust, not the WebView** (`apps/desktop/src-tauri/src/commands/attachments.rs`) so image/audio bytes never round-trip through JS memory. The Rust side has two narrow allowlists (allowed file extensions + R2-host-only URLs) so it can't be abused into a read-any-file-and-PUT-anywhere exfiltration gadget.

Creds stay server-side, heavy data never bottlenecks our server, and each URL is scoped so tightly it's useless beyond its one intended object.

---

## How sync actually moves a row (end to end)

1. You write locally → PowerSync client queues a **CRUD op** (PUT/PATCH/DELETE) and writes the local row immediately (instant UI).
2. PowerSync's connector drains the queue → `POST /upload` (batch) with the session token. `applyOp()` applies each op to Postgres in one transaction, stamping `user_id`.
   - `packages/frontend/src/features/powersync/connector.ts` → `uploadData()`
3. Postgres is now authoritative. PowerSync streams the canonical row back **down** to *all* the user's devices.
4. On each device a **write-through** watches the PowerSync tables and mirrors rows into **local SQLite**, so the existing grid/detail/journal UI keeps reading plain local SQLite unchanged.
   - `packages/frontend/src/features/powersync/write-through.ts` (`appDb.watch(...)` → `upsert*FromCloud`)
5. For attachments, the row syncs first (cheap metadata); the bytes follow via R2 presign on upload, and a fresh device **downloads** the bytes from R2 when it first sees a row it lacks.

**Identity detail worth remembering:** primary keys are **client-generated UUIDs**, deterministic for Steam games (`steam:<steamid>:<appid>` → UUIDv5). One identity, no integer-rowid reconciliation across devices. (A real bug here once: local games used a random UUIDv4 while cloud used the deterministic v5 → every entry/screenshot synced with a dangling parent link. Fixed by carrying the cloud v5 id down as the local uuid.)

---

## The migration tail (why one feature still looks broken)

The **AI features** (Polish + Recap generation) are the *only* thing still wired to the *old* backend — the retired Cloudflare Worker that used Google sign-in. Under Steam auth they look for a Google token that no longer exists and report "Not signed in." Migrating them to the new Steam-session + Fly path is the final step that finishes the rearchitecture. Lesson: when swapping an identity provider, grep for *every* consumer of the old token (`sync_meta.auth_token` here) — a single missed reader is a silently dead feature.

---

## Build vs. buy, self-hosting economics & vendor lock-in (the strategic part)

A founder's instinct is often "I want to control the whole stack so a vendor can't raise prices or degrade on me." That instinct is *half right*. Untangling it:

### "Home server" vs "self-managed infra" vs "managed services" are three different things

People collapse these into one. They're not:

1. **Literal home server** (a box in your house). **Not viable at scale, for technical — not cost — reasons:** residential internet has tiny upload bandwidth, data caps, dynamic IPs, and usually a ToS forbidding servers; one power/ISP blip takes the whole product down (no redundancy); a home line is trivially DDoSed offline; one location = bad latency worldwide; and *you* become personally liable for the physical + network security of user data (GDPR etc.). Money doesn't fix any of these.

2. **Self-managed infrastructure** (rent bare/dedicated servers from Hetzner/OVH and run Postgres + object storage + a sync engine yourself). **Viable, and per-unit often *cheaper* at large scale** — this is the real "control" path, and big companies do exactly this. The catch is you take on the *operational* burden: backups, replication, failover, security patching, monitoring, on-call. That's a job (or a team). Managed services charge a premium precisely to absorb that labor + reliability.

3. **Managed services** (the current setup: PowerSync + Supabase + R2 + Fly). **More per-unit, but you buy zero-ops + reliability + elastic scaling.** Correct default for a solo/small founder pre-scale.

### "Would I still make money at 100k–1M users?"

**Almost certainly yes — and infra cost is rarely what decides it.** Key insight for a **local-first** app like this: the cloud does very little per user. It syncs small text rows and stores occasional small blobs. The genuinely expensive workloads — video streaming, large-scale LLM inference, realtime multiplayer — are *not* in this product's shape. So per-user cloud cost is small.

Rough order of magnitude (varies with usage, treat as a shape not a quote): a local-first app's managed-services bill at ~100k users tends to land in the low-hundreds to low-thousands of dollars/month. A paid tier converting even a few percent at a few dollars/month **dwarfs** that. The margin question is *optimization*, not *viability*. Self-hosting on rented hardware could shave the infra line at scale — but that saving only matters once it's large enough to outweigh the ops cost of running it, which is usually a *later-stage* move (more scale, more revenue, possibly staff to justify it).

### The paranoia is partly valid — but the right hedge is *portability*, not a home server

Vendor lock-in and price hikes are real risks. The correct mitigation is **architectural portability** (use open standards so you can move), and the good news is this stack is *already* mostly portable:

| Component | Lock-in risk | Why |
|---|---|---|
| Write server (Fly) | **Low** | Plain Node/Hono — runs on any host. |
| Postgres (Supabase) | **Low** | Standard Postgres — move to any Postgres host or self-host. |
| R2 (Cloudflare) | **Low** | Speaks the S3 API — any S3-compatible store works. |
| **PowerSync** | **Real** | Proprietary sync engine. Replacing it = rebuilding sync (the thing we deliberately stopped hand-rolling). |

So the practical strategy: stay portable on the commodity pieces (DB, storage, compute — already done), and make **one** eyes-open bet on the hard, proprietary piece (PowerSync) because building+operating sync yourself is the single most expensive thing you could insource. If PowerSync ever raises prices or degrades, the escape hatch is "rebuild the sync layer," which is bounded work against a Postgres DB you already own — not "rebuild everything." The stateless-JWT auth design also means *auth* isn't tied to any vendor; you could move every piece without touching how login works.

**Bottom line for a non-dev founder:** you're not trapped, you will make money, and the lever that protects you isn't owning hardware — it's keeping the commodity layers swappable (done) and treating the one proprietary dependency as a conscious, reversible bet.

---

## Key files (quick index)

**Auth:** `apps/server/src/auth/{steam-openid,session,powersync-token,users}.js` · `packages/frontend/src/features/auth/{useSteamSignIn,steam-session}.ts` · `apps/desktop/src-tauri/src/commands/steam_auth.rs`
**Sync:** `packages/frontend/src/features/powersync/{connector,schema,db,write-through}.ts` · `apps/server/src/db.js` (`applyOp` + `WRITABLE`)
**Server routes:** `apps/server/src/index.js`
**R2 / attachments:** `apps/server/src/attachments/r2.js` · `apps/desktop/src-tauri/src/commands/attachments.rs`
**Postgres schema:** `apps/server/migrations/0001-0005_*.sql`
