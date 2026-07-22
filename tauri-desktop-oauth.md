---
stack: [tauri, better-auth, cloudflare-worker]
kind: howto
last_verified: 2026-07-22
---

# Desktop OAuth for Tauri 2 Apps (Windows/macOS/Linux)

> Learned the hard way (2026-04-13). This is the pattern that works.

## The Problem

Desktop apps (Tauri, Electron, etc.) can't use standard browser OAuth because:
- The system browser and the app's webview have **separate cookie jars**
- Cross-origin cookies between `localhost:1420` (webview) and `localhost:8787` (auth server) don't work
- Custom URL schemes (`myapp://callback`) are fragile on Windows — deep link registration only works in production installers, not dev mode
- Libraries like `@daveyplate/better-auth-tauri` try to bridge this with deep links + cookies but are unreliable on Windows

## The Solution: Localhost Callback + Bearer Tokens

This is how VS Code, GitHub CLI, JetBrains, and most desktop apps do OAuth. Proven, reliable, no cookie dependencies.

### Flow

```
1. User clicks "Sign in with Google"
2. App starts a temporary HTTP server on a fixed port (e.g. 127.0.0.1:17927)
3. App opens system browser to Google OAuth with redirect_uri=http://127.0.0.1:17927
4. Google authenticates → redirects browser to http://127.0.0.1:17927?code=ABC&state=XYZ
5. App's localhost server catches the code
6. App sends the code to your backend (e.g. Cloudflare Worker)
7. Backend exchanges code with Google → gets user info → creates session → returns bearer token
8. App stores bearer token locally (SQLite, localStorage, secure storage)
9. All subsequent API calls use Authorization: Bearer {token}
```

### Why a Fixed Port?

Google's "Web application" OAuth client type requires **exact** redirect URIs including the port. You can't use a random port unless you switch to a "Desktop app" client type (which requires PKCE and has no client secret).

Register `http://127.0.0.1:17927` (or whatever port you choose) in Google Cloud Console → Credentials → Authorized redirect URIs.

## Implementation

### 1. Rust/Tauri Side

**Cargo.toml:**
```toml
tauri-plugin-oauth = "2"
```

**lib.rs:**
```rust
.plugin(tauri_plugin_oauth::init())
```

**capabilities/default.json:**
```json
"oauth:allow-start",
"oauth:allow-cancel"
```

Note: there is NO `oauth:default` permission — you must use the explicit allow permissions.

### 2. Frontend (TypeScript/React)

**Install:**
```bash
pnpm add @fabianlars/tauri-plugin-oauth@2
```

**Sign-in flow:**
```typescript
import { start, cancel, onUrl } from '@fabianlars/tauri-plugin-oauth';
import { openUrl } from '@tauri-apps/plugin-opener';

async function handleSignIn() {
  // 1. Start localhost OAuth server on fixed port
  const port = await start({ ports: [17927] });
  const redirectUri = `http://127.0.0.1:${port}`;
  
  // 2. Generate CSRF state
  const state = crypto.getRandomValues(new Uint8Array(24))
    .reduce((s, b) => s + b.toString(16).padStart(2, '0'), '');

  // 3. Build Google OAuth URL
  const params = new URLSearchParams({
    client_id: 'YOUR_GOOGLE_CLIENT_ID',
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: 'openid email profile',
    state,
    access_type: 'offline',
    prompt: 'consent',
  });

  // 4. Listen for the callback BEFORE opening browser
  const unlisten = await onUrl((urlString) => {
    const url = new URL(urlString);
    const code = url.searchParams.get('code');
    const returnedState = url.searchParams.get('state');
    
    if (returnedState !== state) throw new Error('CSRF mismatch');
    if (!code) throw new Error('No code received');
    
    // 5. Exchange code with your backend
    exchangeCodeWithBackend(code, redirectUri).then(({ token }) => {
      // 6. Store token locally
      storeToken(token);
    }).finally(() => {
      unlisten();
      cancel(port);
    });
  });

  // 7. Open browser
  await openUrl(`https://accounts.google.com/o/oauth2/v2/auth?${params}`);
}
```

### 3. Backend (Cloudflare Worker / any server)

The backend needs an endpoint that:
1. Receives `{ code, redirectUri }` from the app
2. Exchanges the code with Google's token endpoint
3. Fetches user info from Google
4. Creates/finds user in your database
5. Creates a session and returns a bearer token

```typescript
// POST /api/auth/exchange-code
app.post('/api/auth/exchange-code', async (c) => {
  const { code, redirectUri } = await c.req.json();
  
  // Exchange with Google
  const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      code,
      client_id: env.GOOGLE_CLIENT_ID,
      client_secret: env.GOOGLE_CLIENT_SECRET,
      redirect_uri: redirectUri,
      grant_type: 'authorization_code',
    }),
  });
  
  const tokens = await tokenRes.json();
  
  // Get user info
  const userRes = await fetch('https://www.googleapis.com/oauth2/v2/userinfo', {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  });
  const user = await userRes.json();
  
  // Create session, return bearer token
  const session = await createSession(user);
  return c.json({ token: session.token, user: { name: user.name, email: user.email } });
});
```

### 4. Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. APIs & Services → Credentials → Create OAuth 2.0 Client ID
3. Application type: **Web application** (not Desktop — Web lets you use a client secret)
4. Authorized redirect URIs: add `http://127.0.0.1:17927`
5. Save the Client ID and Client Secret

## What NOT to Do

- **Don't use deep links for OAuth** (`myapp://callback`) — unreliable on Windows, requires installer-level URL scheme registration, cookies don't transfer
- **Don't use `@daveyplate/better-auth-tauri`** — v0.1.6, single maintainer, broken on Windows, relies on cross-origin cookies
- **Don't use cookies for auth in native apps** — use bearer tokens stored locally
- **Don't use random ports** unless your OAuth client type is "Desktop app" (which requires PKCE)
- **Don't use Tauri's HTTP plugin** (`@tauri-apps/plugin-http`) as a fetch replacement to "fix" cookies — it has its own cookie jar issues

## Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `tauri-plugin-oauth` | 2.0.0 | Rust — localhost OAuth server |
| `@fabianlars/tauri-plugin-oauth` | ^2.0.0 | JS — start/cancel/onUrl API |
| `@tauri-apps/plugin-opener` | ^2.5.0 | JS — open URL in system browser (`openUrl`) |

## Gotchas

1. **No `oauth:default` permission** — use `oauth:allow-start` and `oauth:allow-cancel` explicitly in your capabilities JSON
2. **`@tauri-apps/plugin-opener` exports `openUrl`, not `open`** — the API name differs from what you might expect
3. **Rust `#[serde(rename_all = "camelCase")]`** — if your Tauri commands return structs with multi-word fields, add this attribute or the JS side will see `undefined` for `logged_in` instead of `loggedIn`
4. **better-auth token format** — if using better-auth's `bearer()` plugin, session tokens must be HMAC-SHA256 signed with base64url-no-pad encoding (not standard base64). The plugin uses `createHMAC("SHA-256", "base64urlnopad")` for verification.
5. **Google propagation delay** — after adding a redirect URI in Google Cloud Console, it can take 5 minutes to several hours to propagate. Usually < 2 minutes for new URIs.

6. **Listener stays bound if user closes the browser tab mid-flow** — the most common production bug with this pattern. If the user clicks Sign in, the browser opens, and then they close the tab before completing OAuth (or kill it because they changed their mind), the localhost listener on your fixed port stays bound. Subsequent sign-in attempts fail with "address already in use" until the app is fully restarted. **Mitigation**: wrap the `start()` + `onUrl()` flow with a ~2-minute timeout that calls `unlisten()` + `cancel(port)`, plus surface a Cancel button in the UI that triggers the same teardown. The naive "user will come back to the tab" assumption fails ~10% of the time in practice.

   ```typescript
   const TIMEOUT_MS = 2 * 60 * 1000;
   const timeoutId = setTimeout(() => {
     unlisten();
     cancel(port).catch(() => {});
     setSignInError('Sign-in timed out. Try again.');
   }, TIMEOUT_MS);

   // Inside onUrl callback, clearTimeout(timeoutId) before the exchange call.
   // Inside the Cancel button handler, do the same teardown + clearTimeout.
   ```

7. **The listener dies on component UNMOUNT — so never host this flow in a transient/dismissable UI surface.** Gotcha #6 is about the browser tab closing; this is about the *host component* closing. The correct cleanup for this pattern is teardown on unmount (`useEffect(() => () => tearDown(), [])` — cancel the port + `unlisten()`), because you must not leak the localhost server. But that same correct cleanup means: **whatever component calls `start()`/`onUrl()` must stay mounted for the entire round-trip** (open browser → user authenticates → loopback redirect fires `onUrl`). If you host the flow inside a popover, dropdown, or any panel that unmounts on click-outside / focus-steal / navigation, then the instant that surface closes — which happens the moment the system browser steals focus, or the user clicks away — the component unmounts, `tearDown()` runs, the loopback listener is gone, and the callback **silently never lands**. It works in every quick test (you don't click away) and fails constantly in the wild.

   **Fix**: host the sign-in flow on a surface that stays mounted — a Settings page, a dedicated dialog that doesn't dismiss on outside-click, or an app-level sign-in host exposed via a store/context. From a transient surface (e.g. a notification popover offering "Sign in to resume backup"), **route the user to the persistent surface** rather than running the flow inline. Generalizes beyond OAuth: any teardown-on-unmount subscription whose success depends on an out-of-band event landing later (loopback servers, WebSocket handlers, `postMessage` listeners, deep-link handlers) must not live in a surface that unmounts as part of normal interaction. (Playmoir, 2026-07-21: the notification hub's expired-session "Sign in" routes to Settings/Connections for exactly this reason — the hub panel is a Radix Popover that unmounts on close.)

## Reference Implementation Layout

This pattern was first proven in a Tauri 2 + Cloudflare Worker + better-auth desktop app. The file layout you'd recreate in any project of that shape:

- Exchange endpoint (Worker): `apps/cloud/src/auth/exchange.ts`
- Frontend OAuth flow (React): `packages/frontend/src/features/sync/SyncAccountSection.tsx`
- Auth client helpers: `packages/frontend/src/features/sync/auth-client.ts`
- Rust sync commands with bearer auth: `apps/desktop/src-tauri/src/commands/sync.rs`
