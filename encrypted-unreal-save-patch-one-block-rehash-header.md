---
stack: [windows, games, reverse-engineering, unreal, steam, python]
kind: playbook
last_verified: 2026-10-24
---

# An encrypted Unreal save is one block per field: SHA-1 header, AES-ECB body, patch the block and re-hash

**One-liner:** a game's in-save play clock read 28h52m while Steam had the same playthrough at about 16h, because the game's timer keeps counting while the PC sleeps and Steam's does not. Steam's number is server-side and untouchable; the clock the player sees lives in the save, so the fix is a save edit. FINAL FANTASY RESONANCE (demo 2026-09-06, retail 2026-10-24) wraps a stock Unreal `GVAS` save in a 32-byte `SVHD` header carrying a SHA-1 of the ciphertext, then encrypts the body with **AES-256-ECB** using a key that sits in plain text in the pak's config. ECB makes one field one 16-byte block, and a bare hash makes re-hashing the whole integrity story. Locate the property by its full name-plus-type tag exactly once, patch four bytes, assert that exactly one cipher block changed, re-hash, write through a temp file, decrypt again to verify. Back up outside the folder Steam autocloud watches, edit with the game closed, and expect Steam to upload the change silently at the next launch.

## The wrapper, as measured

| Offset | Bytes | Meaning |
|---|---|---|
| 0x00 | `53 56 48 44` | magic `SVHD` |
| 0x04 | u32 | version: `0x00010000` demo, `0x00010001` retail |
| 0x08 | 20 bytes | SHA-1 of everything from 0x20 to end of file (the **ciphertext**, not the plaintext) |
| 0x1C | 4 bytes | zero |
| 0x20 | rest | standard Unreal `GVAS` SaveGame, AES-256-ECB, zero-padded to a 16-byte multiple |

The key is `SaveDataEncryptionKey` under `[/Script/SaveGameUtility.SaveGameUtilitySettings]` in the game's pak config, a 32-character ASCII string used directly as the 256-bit key. Any UE title shipping the same SaveGameUtility plugin will have the same shape and its own key in the same place. The decrypted body is ordinary GVAS: `SaveGameFileVersion=3`, UE4 version 522, UE5 version 1017, then the SaveGame class path and a flat property list.

Two checks decide in one second whether a new build still fits the recipe, before anything is written: the header SHA-1 must match the payload (container unchanged), and the decrypt must start with `GVAS` (key unchanged). Retail bumped the header version by one and changed neither.

## Why ECB is the whole story

- **One field, one block.** In ECB every 16-byte block encrypts independently, so changing a 4-byte float changes exactly one block of ciphertext. That is the strongest possible write guard: after re-encrypting, diff the new payload against the old block by block and refuse unless the changed set is exactly `[offset // 16]`. A wrong locator, a shifted length or a padding mistake all fail this assert; a correct edit cannot.
- **Identical first cipher blocks are a free same-key test.** Every save of this game, demo and retail, options file included, opens with the same 16 cipher bytes (`a5 e3 7a 47 6d dd 5f 00 ...`). Under ECB that means identical plaintext under an identical key; under any chained mode with a fresh IV it could not happen. One `xxd -s 0x20 -l 16` on a demo and a retail save settled "did they rotate the key?" before the key was even typed in.
- **A hash is not a MAC.** The header SHA-1 covers the ciphertext and nothing secret goes into it, so the game accepts any payload whose hash you recompute. If a wrapper used an HMAC with a key you do not have, this playbook stops at the header.

## Locate by the full tag, require exactly one

A GVAS property is `FString name, FString type, u64 size, [flags], value`. Searching for the bare name finds strings in other contexts; searching for the full tag pins the property and its type at once. The `PlayTime` locator, byte for byte:

```
09 00 00 00 "PlayTime" 00     length-prefixed name (9 incl. NUL)
0E 00 00 00 "FloatProperty" 00
00 00 00 00 04 00 00 00 00    size 4 and the one flag byte
<f32 little-endian seconds>
```

Assert the tag occurs **exactly once** in the plaintext (`find` and `count`), and refuse otherwise. Then scan the plaintext for every other property whose name contains the concept (`re.findall(rb"[A-Za-z_]\w*Time\w*(?=\x00)")`) and read each one before deciding yours is the display source. Here the siblings were `SavedDateTime` (a struct, the save timestamp), `DateTime` inside it, and `elapsedLifeTime` (a float at about 1,100 s, something's lifetime, not the clock). The one that matched the on-screen value to the second was `PlayTime`; the others stayed untouched.

The value sat at plaintext offset `0x8b9` (block 139) in every slot of both builds, because the property list before it is the same fixed header block. Do not hard-code that; it is a sanity check on the locator, not the locator.

## Write discipline

1. Patch the float in the decrypted plaintext; re-encrypt the whole plaintext (ECB, no padding changes because the length is unchanged).
2. Assert exactly one block changed (above) and that the file length is unchanged.
3. Rebuild the header: keep bytes 0..8 and 28..32, replace 8..28 with SHA-1 of the new payload.
4. Write to `<file>.tmp`, then `os.replace` over the original. A crash mid-write leaves the original intact.
5. Re-read the file through the same loader: header hash OK, `GVAS` magic OK, tag found once, value within 0.5 s of the target, and plaintext identical outside the four patched bytes.

Keep the patcher next to the backup it was used with, so the next time (the clock drifts again) the tool and the baseline are in one folder. The retail pass reused the demo script with two line changes (save folder, slot count).

## Steam autocloud around a hand edit

- **Edit with the game closed; Steam may stay open.** Steam compares each tracked file against `userdata/<account>/<appid>/remotecache.vdf` (per-file `sha`, `size`, `localtime`, `remotetime`) at launch and exit, not continuously. Measured after the edit: all four slots had a new local SHA-1 while remotecache still held the pre-edit hashes, and nothing uploaded until the next launch.
- **Local-only change uploads silently.** Only "both sides changed since last sync" raises the Keep local / Keep remote dialog; if it does appear, keep local, the side holding the edit. The first-upload race in [steam-library-integration.md](./steam-library-integration.md) is the other way to reach that dialog.
- **The backup lives outside the autocloud root.** Steam watches `%LOCALAPPDATA%\FFRS\Steam\<steamid64>\`; a copy left in that folder with a `.sav` name is a candidate for sync and for the game's slot enumerator. A dated sibling folder in Documents, holding the whole save tree plus the Steam `remotecache.vdf` snapshot, and verified by comparing SHA-256 of every file, is the baseline. Steam's Verify integrity never touches saves, so it is neither a risk here nor an undo path; the undo is copying the backup back.
- **Proportional, not flat, across slots.** Four rotating slots carried 26h34m to 28h52m. Scaling all by one factor (newest slot to exactly 15:00:00, the rest to 13h48m to 14h55m) keeps older saves showing less time than newer ones, so the load screen stays self-consistent.

## Tool traps

- `python -I` ignores user site-packages, so `from Crypto.Cipher import AES` (pycryptodome) fails under it even though plain `python` imports fine. Saves the user owns are not downloaded content; run them under plain `python`, or fall back to `openssl enc -d -aes-256-ecb -K <hex key> -nopad`.
- Git Bash on Windows has `xxd` and `sha256sum` but no `strings`; a Python regex over the decrypted bytes is the substitute and gives you property names rather than fragments.

## When it is not this

If the decrypt does not produce `GVAS`, the key moved: pull the pak config again (`SaveGameUtilitySettings`) before assuming a new scheme. If the header hash check fails on an untouched file, the container changed and the version field will have moved too. If the first cipher blocks of two saves differ, the mode is chained or the key is per-file, and the one-block guard no longer applies.

**See also:** [patch-the-consumer-not-the-value.md](./patch-the-consumer-not-the-value.md) for the exactly-one-match rule and choosing where to patch; [demo-built-mod-on-a-retail-game-fixed-offsets-crash.md](./demo-built-mod-on-a-retail-game-fixed-offsets-crash.md) for the same game's binary-side lesson and the backup-naming trap; [steam-library-integration.md](./steam-library-integration.md) for Steam's on-disk layouts and the cloud first-upload conflict.
