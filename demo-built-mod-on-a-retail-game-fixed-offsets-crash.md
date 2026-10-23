---
stack: [windows, games, reverse-engineering, unreal, powershell, python]
kind: playbook
last_verified: 2026-10-23
---

# A mod built against the demo crashes the retail game: fixed offsets break, signature scans survive

**One-liner:** a runtime game mod carries two kinds of addresses. Hooks found by **signature scan** survive a rebuild of the game; addresses baked in as **fixed offsets** (an SDK dumped from one specific exe) do not, and the crash they cause is diagnosable in one lookup: the fault offset in the Windows Application log equals the stale offset. From FINAL FANTASY RESONANCE (2026-10-22, day-one retail build): PolarWizard's ultrawide fix 0.2.0, built against the demo, crashed retail at launch at exactly its SDK's `AppendString` offset. The repair was 13 bytes in the plugin, every one of them verified against the retail exe without running the game, plus turning off the one feature that still had an unverified code path.

## The red flags I walked past

The fix's latest release was dated 2026-09-18. The game's retail release was 2026-10-22. A fix that predates the game it fixes was built against a demo or a beta, and a day-one build is a different exe. The research agent even wrote "I could not find a thread where someone reports success with this specific fix", and the repo's issue tracker already had "crashes instantly on retail" with two confirmations, five hours old. I installed anyway and handed the user a test list; the user's next message was "crashes".

**Before installing any runtime mod:** compare the release date with the game's current build date (Steam `appmanifest_<id>.acf` → `LastUpdated`, or the exe's PE timestamp), and read the open issues. Thirty seconds. The rest of this lesson is what to do when you didn't.

## Diagnose from the crash record, not from guesswork

1. **Windows Application log, event 1000.** `Faulting module: <game exe>`, `Fault offset: 0x0000000001376360`. The module being the game exe, not the mod DLL, is normal: the mod handed the game a wrong address and the game faulted executing or reading it.
2. **The mod's own log.** Good mods log every hook as `Found '<signature>' @ exe+<rva>` and every fixed-offset use as a bare number. Everything logged as *Found* survived; the crash came from something that wasn't scanned for. Here the aspect-ratio patches, the widget hooks and the movie hooks all logged signature hits on retail. The SDK offsets (Dumper-7's `Basic.hpp`: `GObjects`, `GNames`, `GWorld`, `AppendString`, `ProcessEvent`) were constants.
3. **Match the fault offset to the SDK.** `0x1376360` was the SDK's `AppendString`. That is the whole diagnosis. Someone on the issue had reached the same conclusion from live memory; the two derivations agreeing is what let the rest proceed.

## First response: feature-gate, don't patch

Read the mod's `install()` before touching bytes. It usually applies fixes in order and gates some on config flags. Here `aspect_ratio::apply` (two byte patches, signature-found) and `post_processing` ran unconditionally and used no SDK; the `[movies]` and `[hud]` features were the only callers of SDK code. Turning both off in the TOML gave a crash-free ultrawide game in one config edit, with a known cost (pre-rendered movies stretch), while the real repair was verified. A commenter on the issue had reported the same configuration working on retail, which is a second source for a config change that is otherwise free to try.

## Verify a stranger's offsets without running the game

The issue comment supplied retail offsets read from live memory. Trust is not verification, and a wrong `GObjects` corrupts memory rather than crashing cleanly. Two static checks, both cheap:

- **A function offset: signature scan.** Take the function's opening bytes from the comment (or from the demo exe at the demo offset) and count hits in the retail exe. Exactly one hit, and it must land on the claimed RVA after mapping file offset → RVA through the PE section table. Here `48 89 5C 24 10 48 89 74 24 18 57 48 83 EC 20 80 3D ?? ?? ?? ?? 00 48 8B F2 8B 19 48 8B F9 74` hit once, at `0x013763A0`. The demo offset `0x01376360` landed mid-function (`01 00 00 00 48 8B CF E8 ...`), which is where the game faulted. A function prologue also sanity-checks itself: UE's `ProcessEvent` opens `40 55 56 57 41 54 41 55 41 56 41 57 48 81 EC`, and that is exactly what sat at the claimed retail offset and not at the demo one.
- **A data global: count the code that references it.** A global in `.data` is zero-initialized in the file, so there is nothing to pattern-match at the address itself. Instead, for every position `i` in the code section, read the int32 at `i` as a RIP-relative displacement and ask whether `rva(i + 4 + trailing) + disp` equals the candidate, for trailing immediates of 0, 1 and 4 bytes. The engine's object table is used everywhere: **1,070** references to the retail `GObjects`, **0** to the demo one; 49 vs 0 for `GNames`. That asymmetry is the verification. (`GWorld` scored 1 vs 1 and stayed unverified, which was fine because the plugin never used it; see next point.) A 125 MB code section takes two minutes in pure Python with the `array` module and seconds with numpy.
- **Only verify what the binary uses.** Count each demo offset's little-endian bytes inside the plugin: `GObjects` 4×, `AppendString` 1×, the other three 0×. Those five occurrences are the patch, and the unverified globals are irrelevant.

## Patch the plugin, not the game

Replace the five 4-byte immediates. The patch script refuses unless it finds **exactly** 4 and 1 of the old values and 0 of the new, and compares the result's SHA-256 to the known-good hash before installing. Thirteen bytes changed (the immediates share bytes with their replacements).

Two things specific to loader-based mods:

- **A backup must not keep the plugin extension.** Ultimate ASI Loader loads every `*.asi` in `scripts\`. A backup named `fix.asi.orig.asi` or dropped into the same folder with the extension intact is loaded too, and now two copies hook the same functions. Name it `.asi.bak`.
- **A feature with a known unverified path stays off even after the offsets are fixed.** The HUD path here also held a raw pointer to a render target across garbage collection (use-after-free on the second battle). The imm32 patch doesn't touch that. The installer forces that flag off in the config and says so, rather than letting a user flip it on and hit a crash the fix is supposed to have solved.

## Shipping it to other players

- **Refuse on any other build.** The installer reads the exe's PE `TimeDateStamp` and the 17 prologue bytes at the known `AppendString` file offset and installs only if both match. A game update then produces a clear refusal instead of a crash, and the message points at the upstream release page.
- **Don't redistribute the binaries.** Download the upstream release zip from its GitHub URL, compare its SHA-256, extract with .NET, verify the hash of each file you are about to use, patch, verify again, then write. The repo holds a `.bat`, a README and a license. Nobody has to trust a stranger's DLL from a forum post, and the credit stays where it belongs.
- **Windows PowerShell: `Get-FileHash` and `Expand-Archive` are script-module functions,** not compiled cmdlets. Launched as `powershell -NoProfile -Command "... Invoke-Expression ..."` from a `.bat` under pwsh 7, `Get-FileHash` resolved to "not recognized" even though `Get-Command` found it in a plain child shell. Root cause not pinned down (module auto-loading inside `Invoke-Expression` is the suspect); the cure is to not depend on it: `[Security.Cryptography.SHA256]::Create().ComputeHash($stream)` and `[IO.Compression.ZipFile]::ExtractToDirectory()` after `Add-Type -AssemblyName System.IO.Compression.FileSystem` work in 5.1 and 7 alike.
- **Test the matrix on a scratch copy of the exe folder**, driven by an environment-variable override for the game directory and a command-line argument for the menu choice so the script runs non-interactively: stock → install → install again (no-op) → remove; demo plugin + wrong config → install (backup, patch, config fixed); corrupted plugin → install repairs with backup; other build → refuse; zip next to the script → used instead of downloading; then a status-only run against the real install to exercise Steam-library discovery. Nine runs, one bug found (the one above), none of them on the user's game.

## When it's overkill

If the upstream author has already shipped a retail build, install that. If the mod uses signature scans for everything (the log says *Found* for every hook and never crashes), there is nothing here to do. This playbook is for the gap between a game update and the next mod release, when the fix is a handful of constants and you can prove each one.

**See also:** [patch-the-consumer-not-the-value.md](./patch-the-consumer-not-the-value.md) for choosing where to patch in a binary you can't rebuild and the exactly-one-match rule; [unity-il2cpp-aspect-lock-is-game-code.md](./unity-il2cpp-aspect-lock-is-game-code.md) for the test-matrix and `.bat` launcher details this installer copies; [unreal-ultrawide-two-layers-and-steam-delivery.md](./unreal-ultrawide-two-layers-and-steam-delivery.md) for what the aspect-ratio patches themselves do and how Steam treats added files versus patched ones.
