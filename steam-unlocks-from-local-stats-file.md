---
stack: [steam, rust, desktop, local-first]
kind: pattern
last_verified: 2026-09-29
---

# Detect Steam achievement unlocks from Steam's own local file, ~8 s after they happen, with no API key, login or Steamworks

**One-liner:** the Steam client keeps a per-user, per-game binary cache at `Steam/appcache/stats/UserGameStats_<accountid>_<appid>.bin` with every unlock's timestamp, and rewrites it **during play, about 8 s after an unlock**, not only at exit. A sibling `UserGameStatsSchema_<appid>.bin` maps bit indexes to achievement API names. Polling that one file's mtime every few seconds while a game runs detects unlocks faster than any Web API round trip, needs no key and no sign-in, and doesn't impersonate the game the way Steamworks-based tools do. `stats_log.txt` looks tempting but is a generic heartbeat; don't use it as a trigger.

*Research with local evidence 2026-09-15 (Playmoir D-26); the watcher shipped in desktop 1.5.0 and fired within seconds on a live unlock on 2026-09-29. The "mint the rows locally" half at the end is a plan (D-85), not yet built.*

## The files

**User file** (binary KeyValues: type bytes `0x00` subkey, `0x01` string, `0x02` int32, `0x07` uint64, `0x08` end):

```
cache { crc PendingChanges
  <statgroup> { data = <int32 bitmask of unlocked bits>
                AchievementTimes { "<bit index>" = <unix seconds> ... } }
  ... }
```

**Schema file:** `<appid> { stats { <statgroup> { bits { <bit> { name = "<api name>" display {…} bit = <n> } } } } }`. The stat-group id is the same key in both files. A machine with a real library has hundreds of pairs (348 here).

`userdata/<accountid>/<appid>/` does **not** hold achievement state; it's Steam Cloud's manifest.

## Timing (measured, local)

| Game | Unlock | File mtime |
|---|---|---|
| The Blood of Dawnwalker (still running) | 00:49:52 | 00:50:00 |
| Onimusha | 13:59:12 | 13:59:20 |

The write follows the game's `StoreStats` → server → merge cycle, about 8 s after the unlock, mid-session. `stats_log.txt` does log a line within ~1 s of an unlock, but the same "no stats data in server response" line fires with **no** unlock too. It's a store heartbeat, not a signal. Directory mtimes on the logs also lagged their content, so mtime-watching the log is unreliable.

## The watcher

- Poll the running game's user file on the existing monitor tick (3 s): `stat` for mtime, and re-parse only when it changes.
- **Baseline at game start**, and emit only when the *set* of unlocked bits grows.
- **Torn-read guard:** a partial or garbage read parses to `None` and is retried next tick, never treated as "unlocks removed". Tests cover a real 134-byte sample, a torn file and garbage.
- **Read-only, always.** Never write under Steam's folders.

Prior art reads the same file: SamRewritten (Rust), rewind (polls every 3 s), PSerban93/Achievements. Achievement Watcher uses only the file's mtime as a cue to call the Web API. Tools that act as the game through Steamworks show the user as "Playing" and can strand the running AppID; this approach avoids that entirely.

**Open questions (unverified):** whether the file is written at unlock while the client is offline (expect yes, with `PendingChanges > 0`), and whether Steam writes in place or via rename (it affects which file-system events would fire, one reason to poll mtime instead of watching).

## Why it mattered: the API path was the slow part

On a live unlock (2026-09-29) the local watch fired at once, but the user-facing nudge waited for the *server* to pull the unlock from the Steam Web API, which hadn't listed it yet, so a 60 s poll caught it a minute later. It also didn't work signed out at all, and every user's polling drew on one shared API key's daily quota.

## The plan that builds on it (D-85, not yet verified)

The server's unlock row ids are **UUIDv5 of `ach:{steamId64}:{appid}:{apiname}`**, and `SteamID64 = 76561197960265728 + accountid`, which the desktop knows from the registry without a session. So the client can **mint the identical rows locally** the moment Steam writes the file, and the server's copies land *on* them instead of duplicating. The named risk: a local row the user has already linked to a journal entry must not be clobbered by the server's newer copy (a local-only column protects the link). Update this section when it's built.

## Related

- `steam-library-integration.md`: the other local Steam files (VDF/ACF, `appinfo.vdf`, librarycache).
- `silent-refusals-make-clean-logs-meaningless.md`: Steam's 403 for private profiles on the API path.
