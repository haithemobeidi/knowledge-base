---
stack: [steam, rust, vdf, game-library-integration]
kind: reference
last_verified: 2026-07-20
---

# Steam library integration — cover art, install-state, and the ToS constraint that shapes the whole architecture

**Context:** for any project that reads a user's local Steam library (a launcher, an overlay tool, a companion app — not just Playmoir). Steam's client has changed its on-disk layouts multiple times over the years and there's very little good public documentation of the current state; this is a snapshot of what actually works today, plus the ToS constraint that determines your architecture before you write any code.

## 1. Cover-art resolution — Steam's librarycache has THREE coexisting layouts

A real Steam install has games cached at different times across client updates, so all three layouts can be present simultaneously on one machine:

| Layout | Shape | Era |
|---|---|---|
| **A — flat-in-appid-dir** | `{appid}/library_600x900.jpg`, `_2x.jpg` variant, `library_capsule.jpg`, `header.jpg`, `library_hero.jpg`, `logo.png` | Current-ish |
| **B — nested content-hash** | `{appid}/{contentHash}/library_capsule.jpg`, `.../library_header.jpg`, `.../library_hero.jpg`, `.../library_hero_blur.jpg` | Newest |
| **C — legacy flat** | `librarycache/{appid}_library_600x900.jpg` directly in the root | Old |

**Resolution technique:** walk all three layouts unconditionally and use a `maybe_set(slot, dir, filename)` helper that only writes into an `Option<String>` slot if it's currently empty. Scan order stops mattering — each asset slot (capsule/header/hero/logo) just converges on whichever layout actually has that file for that game. Prefer the `@2x` variant when both exist (some games cache ONLY the `@2x` file, so don't skip checking for it).

**Windows path gotcha:** Steam's registry `SteamPath` value uses forward slashes; joining it with `PathBuf::join` on Windows injects backslashes, producing a mixed-slash path. If you're feeding this path into something with its own glob-matching (e.g. Tauri's asset-protocol scope), mixed separators silently fail to match. Normalize to one separator (flatten to `/`) before using the path anywhere that does its own matching.

**If a cover looks broken/missing** even after checking all three layouts: Steam's librarycache is populated **lazily**. A game that hasn't been opened/viewed in the Steam client recently may simply not have its art cached to disk yet, regardless of which layout you're checking. The reliable fix is prompting the user to click the game once in Steam's own library (which triggers Steam to download the missing asset) — your code's three-layout fallback chain is the safety net for "which layout is it in," not a fix for "Steam hasn't downloaded it at all."

## 2. Text KeyValues (VDF) parsing — hand-roll it, it's simpler than it looks

`libraryfolders.vdf` (which drives lets exist at multiple Steam library locations) and `appmanifest_{appid}.acf` (per-game install metadata: `name`, `installdir`, `StateFlags`, `SizeOnDisk`, `LastPlayed`) are both Valve's plain-text **KeyValues** format — nested `"key" "value"` pairs in braces.

If every field you need is a **flat, top-level pair** (not nested inside a same-named sibling key that could collide), a hand-rolled line-scan extractor is legitimately simpler and more auditable than pulling in a general KeyValues parser — you don't need full tree parsing for "give me the value next to this exact key at this nesting depth." Two real gotchas either way:

- **`libraryfolders.vdf` lives at two possible paths** depending on Steam client version: `steamapps/libraryfolders.vdf` (legacy) and `config/libraryfolders.vdf` (newer). Check both; don't assume one.
- **VDF string values backslash-escape quotes and backslashes** (Windows paths inside VDF look like `"installdir"  "Half-Life\\2"`). Unescape `\\` sequences before using the extracted path — skipping this corrupts any path containing a literal backslash (i.e. every Windows path).

## 3. Binary `appinfo.vdf` — don't hand-roll this one, use a validated crate

`appinfo.vdf` (Steam's cache of every app's metadata, including whether an appid is a real game vs. a tool/demo/soundtrack/DLC) is a **different, binary** format — not text KeyValues — and Valve has changed its binary structure over time (a comment in this codebase's `Cargo.toml` notes it's currently "v41 string-table format, June 2024"). This is exactly the case where "don't reinvent the wheel" flips to "don't hand-roll a binary format parser Valve can silently version-bump" — use a maintained crate (this project uses `steam-vdf-parser` from crates.io) and **validate it against a real, current `appinfo.vdf` file before trusting it** — binary format parsers for undocumented formats are exactly where a stale crate silently breaks.

Read the app's classification via `appinfo → common → type` (Steam's own field distinguishing `game` from tool/demo/etc.) instead of hand-maintaining a denylist of non-game appids — it's self-updating as Steam adds new apps. Keep a small static fallback denylist (known non-game appids like the Steamworks Common Redistributables, `228980`) for when `appinfo.vdf` can't be read at all, so the feature degrades instead of failing outright.

## 4. Install-state reconciliation: authoritative-scan-diff, with a hard rule about failure vs. empty

The general pattern for "periodically re-derive a local boolean from a live external source" (not Steam-specific in principle, but this is the clearest instance): treat a fresh scan as authoritative, and flip every row that claims `installed = true` but is absent from the new scan.

```sql
UPDATE games SET installed = 0, updated_at = unixepoch()
WHERE platform = 'steam' AND installed = 1 AND deleted_at IS NULL
  AND steam_appid NOT IN (...)   -- the just-scanned set of currently-installed appids
```

**The same pattern applies to a REMOTE authoritative-set pull, not just a local scan** — with one extra gotcha. A "pull my owned games" REST/API pull that only ever *upserts what it received* has the identical bug in a different guise: a refunded or gift-removed game is simply absent from the response (the server already filters it out), so a naive pull never removes the now-stale local row — it just silently never updates it again, and the count drifts upward forever. Fix: after upserting the received set, also soft-delete local live rows scoped to that source whose id is absent from it (`WHERE platform = 'steam' AND deleted_at IS NULL AND steam_appid NOT IN (...pulled ids...)`) — same shape as the install-state diff above, applied to *ownership* instead of *install state*. Two guards this version needs that the pure-local scan doesn't:
- **Don't prune a row that has a competing local authority.** A game that's still installed on disk but absent from the "owned" pull is very often *family-shared* (some platforms surface a shared library's installed titles even though the owning account isn't the pulling account) — pruning it would vanish a game that's genuinely still playable. Exclude anything the local scan independently confirms is installed; a real refund self-heals once the game is eventually uninstalled and the next pull runs.
- **An empty/short response must never drive a prune.** A fresh sign-in whose cloud side hasn't populated yet, or a paginated response you're only seeing one page of, looks identical to "the user now owns zero games" from the diff's point of view — skip the prune entirely whenever the pulled set is empty, rather than trusting absence-from-empty as a signal.

**The load-bearing correctness rule:** the scan function must return an explicit `Err` (failure) when Steam isn't installed at all or the scan couldn't complete — never `Ok(empty list)` for that case. If "Steam not found" and "Steam found, zero games installed" both produced an empty list, a transient scan failure (or a machine that simply doesn't have Steam) would mass-flip every previously-installed row to `false`. Only reconcile against a **proven-successful** scan; a proven-failed one should leave existing state untouched. This is the general shape for any "resync local state from an external source" feature — the failure path and the legitimately-empty path must be distinguishable at the type level (`Result`, not a plain array), or a transient failure silently masquerades as "everything is now gone."

## 5. The Steam Web API ToS constraint that determines your whole import architecture

Steam's Web API terms cap a single developer key at **100,000 calls/day** and prohibit sharing or delegating that key to third parties. A product that proxies Steam Web API calls through one shared backend-held key cannot scale past a small user base — 1,000 users making 100 calls/day each exhausts the daily cap by noon. This is a hard constraint, not a "we'll optimize later" problem.

The pattern other Steam-integrated tools (Playnite, GOG Galaxy 2.0) and this project converge on is a **three-tier import model** that avoids the shared-key bottleneck entirely:

1. **Local VDF/ACF read** for installed games — no API key needed at all (sections 1–4 above).
2. **Steam OpenID 2.0 sign-in** for identity only (SteamID64) — not the Web API, no key, no rate limit (see `powersync-steam-backend-architecture.md` for the OpenID flow itself).
3. **User brings their own Steam Web API key** (self-service, free, instant at Steam's key page) for anything that needs the full owned-games list beyond what's locally installed — each user consumes their OWN 100k/day budget, so the product's scale is no longer bounded by a shared key. Store the user's key via the OS keychain/DPAPI, not plaintext.

If you're scoping a new Steam-integrated feature, decide up front which of these three tiers it actually needs — most "show the user's library" features only need tier 1, and reaching for tier 3 (asking the user for their own API key) should be reserved for features that genuinely need data local scanning can't provide (full owned-games list including uninstalled-and-never-locally-seen games, playtime history, etc.).

## Related, adjacent domain (save-file locations, not cover art)

If a future feature needs "where does game X keep its save files," don't build a proprietary per-game path database from scratch — the community already maintains one: `mtkennerly/ludusavi` (Rust, GPL-3) ships a manifest dataset (`ludusavi-manifest`) derived from PCGamingWiki's save-location data, keyed by Steam appid. Check its license terms before redistributing, but it's a solved, actively-maintained problem — don't re-derive it by hand.
