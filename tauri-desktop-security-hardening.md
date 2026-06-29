---
stack: [tauri, security]
kind: checklist
last_verified: 2026-06-29
---

# Tauri 2 desktop security-hardening checklist

Reusable pre-launch hardening for a Tauri (Rust + WebView) desktop app.

**Threat-model calibration:** a local user already controls their own machine, so "user can read their own DB/files" is NOT a finding. The real risks are **untrusted DATA** (cloud-synced content, deep links, third-party-sourced strings) crossing into code/path/SQL execution, and the **blast radius an XSS would have** given the capabilities you granted.

## 1. Asset-protocol scope — beware broad globs
`app.security.assetProtocol.scope` in `tauri.conf.json` controls what the webview can read via `asset://`. A glob like `**/SomeApp/**` matches that segment **anywhere on disk** — it can expose credential/config files far beyond what you actually read.
- Scope to the **narrowest real path** (e.g. `**/appcache/librarycache/**`, your app-data dirs) — never a broad app-root glob.
- Each unnecessary glob is a file-exfil vector the moment an XSS lands.

## 2. `opener` allow-list — least privilege
`opener:allow-open-url` with `https://*` / `http://*` / `scheme://*` lets (an XSS in) the webview open arbitrary URLs or fire arbitrary custom-scheme verbs.
- Allow only the exact URLs you open: e.g. `steam://run/*` + your specific `https://your-api.example.com/*`, not wildcards.
- Audit by grepping the frontend for every `openUrl(` / `open(` call before narrowing — usually only 1–3.

## 3. Keep debug commands out of release
Dev-only IPC commands (process enumeration, on-demand capture, seed generators) ship in the binary unless gated.
- Put `#[cfg(debug_assertions)]` on BOTH the command `fn` AND its entry in `generate_handler![]` (Tauri supports `#[cfg(...)]` on individual handler entries).
- Grep the handler list for `debug_*` / `dev_*` / `seed_*` before shipping.

## 4. Path-contain every command that takes a path from the frontend
Any `#[tauri::command]` that receives a `file_path: String` and reads/writes/deletes it can be handed an arbitrary path by (an XSS in) the webview.
```rust
let root = app.path().app_data_dir()?.join("subdir");
let canon_root = std::fs::canonicalize(&root)?;
let canon = std::fs::canonicalize(&input_path)?;          // also proves it exists
if !canon.starts_with(&canon_root) { return Err("path outside app dir".into()); }
```
- Make ONE `canonical_under(candidate, root)` helper and reuse it (don't reimplement per command).
- Exception: a true save-dialog destination is legitimately anywhere — accept those, but know the command can't *prove* it came from the dialog.

## 5. CSP — don't ship dev origins
The CSP in `tauri.conf.json` applies to release too. Strip dev-only entries (`http://localhost:<devport>`) so a release XSS can't reach local services. Keep `script-src 'self' 'wasm-unsafe-eval'` (no `unsafe-inline` for scripts); `style-src 'unsafe-inline'` is normal/low-risk.

## 6. The XSS lynchpin (items 1, 2, 4 are amplifiers)
Those items only become exploitable when untrusted text renders as HTML. So the load-bearing check: **does any synced / third-party / user string ever hit `dangerouslySetInnerHTML` / `innerHTML` without escaping?** Route all such rendering through one escape-then-stitch helper. If that holds, the amplifiers are dormant; if it breaks, they're all live. Verify it explicitly — don't assume.

## 7. `sql:allow-execute` to the webview
tauri-plugin-sql exposes raw SQL to JS by design (the frontend owns DB writes) → an XSS = full local DB control. Acceptable *only* while item 6 holds. Longer term, move writes behind narrow Rust commands so you can drop `sql:allow-execute`.

## 8. Secrets on disk
Tokens/keys written to the local DB or files should be wrapped with the OS facility — Windows **DPAPI** (`CryptProtectData`), macOS Keychain, Linux libsecret — not stored plaintext.

## Verify
`cargo check` in **both** debug and release after `#[cfg]`-gating — the release build is what proves the gated symbols and their handler entries stay consistent (a mismatch only errors in one profile).

---
*Captured from the Playmoir pre-paywall security pass, 2026-06-29. See also `tauri-desktop-oauth.md`, `tauri-sqlite-direct-sqlx.md`.*
