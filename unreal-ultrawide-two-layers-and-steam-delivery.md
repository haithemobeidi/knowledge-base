---
stack: [unreal, windows, games, steam, reverse-engineering]
kind: playbook
last_verified: 2026-10-23
---

# Unreal ultrawide is two layers (the bars, then the FOV axis), and Steam treats a hex patch and an ASI mod differently

**One-liner:** an Unreal game stuck in 16:9 on a wider monitor has two separate things wrong, owned by two separate engine fields: `bConstrainAspectRatio` draws the black bars, and `AspectRatioAxisConstraint` decides whether the extra width shows more world (Hor+) or crops the top and bottom (Vert-). Fix one and it looks half-broken. The folklore "find the 16:9 float" fails because the value comes from assets, not the exe (one decoy hit in a float table). Both UE4 (Forsaken Realms: Vahrin's Call, 2026-07) and UE5 (FINAL FANTASY RESONANCE, 2026-10) were fixed by patching the **code that reads** those two fields, once as a hex patch to the exe and once through a runtime plugin, and the two delivery methods behave differently under Steam.

## The two layers

| Layer | Engine field | What you see if only the other one is fixed | UE4 fix (Vahrin's Call, hex) | UE5 fix (FFRS, PolarWizard plugin at startup) |
|---|---|---|---|---|
| Bars | `FMinimalViewInfo::bConstrainAspectRatio`, read in `CalculateProjectionMatrixGivenView` | Image is cropped top and bottom, no bars | `test byte ptr [rcx+0x30], 1` → immediate `01`→`00` (4-byte `F6 41 30 01`; validated by `0F 84` and `F3 0F 10 51 2C` within 128 bytes, exactly one site) | signature `89 ?? ?? 0F ?? ?? ?? ?? ?? 00 33 ?? ?? 83 ?? 01`, byte +15 (`and ecx, 1`'s immediate) → `00` |
| FOV axis | `ULocalPlayer::AspectRatioAxisConstraint` | Bars gone, but you lose vertical view instead of gaining horizontal | `Engine.ini`: `[/Script/Engine.LocalPlayer]` `AspectRatioAxisConstraint=AspectRatio_MaintainYFOV` | signature `0F ?? ?? ?? ?? ?? 41 ?? ?? ?? ?? ?? 00 00 48 ?? ?? ?? ?? 00 00 4C ?? ?? 4D ?? ??`, +6: `movzx edx, byte [r15+0xB8]` → `mov edx, 0` + 3 NOPs |

The field offsets (`+0x30`, `+0x2C`, `+0xB8`) are per build; the shapes are not. In UE4 the axis constraint was still config-backed, so an ini line did it. In the UE5 game the plugin's author patched the load instead, which also works when the game's own config overrides the engine default.

## Why the float hunt fails here

The 16:9 constant as a float is `39 8E E3 3F`. FFRS's 495 MB exe contained it **once**, in a float table (`1.0, 1.1667, 1.6446, 1.7778, 3.3333`), not anywhere a projection is computed. The per-camera aspect ratio lives in the cooked assets, which in UE5 are IoStore containers (`.utoc`/`.ucas`) that plain grep can't read. Vahrin's Call was the same shape a layer down: the value was in an 18.5 GB pak. The consumer, the engine's projection code, is the choke point. See [patch-the-consumer-not-the-value.md](./patch-the-consumer-not-the-value.md).

A quick useful probe anyway: count the float. Zero or one hits means the value is external and you are in consumer-patch territory; dozens means you are probably looking at a UI layout table, not the camera.

## Where things live, UE4 vs UE5

- Exe: `<Project>\Binaries\Win64\<Project>-Win64-Shipping.exe`. The root `<Game>.exe` is a bootstrap; a loader DLL must sit next to the shipping exe or it never loads.
- User config: `%LOCALAPPDATA%\<Project>\Saved\Config\WindowsNoEditor\` (UE4) versus `...\Saved\Config\Windows\` (UE5). `GameUserSettings.ini` is there; `Engine.ini` is created by you if absent. The UE5 file carries a `;METADATA=(Diff=true, UseCommands=true)` header; keep it.
- Shipped `.pdb` next to the exe: UE4 builds often ship one, which turns pattern hunting into symbol lookup. FFRS shipped none. Check before scanning.
- Crash evidence: the shipping build wrote no `Saved\Logs`; the Windows Application log (event 1000, fault offset) and `%ProgramData%\Microsoft\Windows\WER\ReportArchive` had everything.

## HUD after the bars are gone

Unreal's UMG root fills the viewport. Remove the constraint and the HUD spans the full 21:9 with elements anchored to the new edges, scaled by the DPI curve on the **shortest** side, so nothing changes size. That is the opposite of Unity's width-matched canvases ([unity-il2cpp-aspect-lock-is-game-code.md](./unity-il2cpp-aspect-lock-is-game-code.md)), where the UI grows 34% and overlaps. Mods that offer a "constrain HUD" option are offering to **shrink** it back into a centred box, which only matters at 32:9. Ask the user whether edge-anchored HUD bothers them before chasing it; on 21:9 it usually reads as a feature.

## Delivery: hex patch to the exe vs an ASI plugin beside it

| | Hex patch to the shipping exe | Loader + plugin (`winmm.dll` / `dinput8.dll` proxy, `scripts\*.asi`) |
|---|---|---|
| Steam **Verify integrity of game files** | Restores the depot file: the patch is **undone**, re-run the tool | Added files are **ignored**: the fix survives |
| Game update | Replaces the exe. A signature-based tool re-finds the site or refuses; a fixed-offset tool corrupts the install | Exe moves; the plugin's **signature-scanned** hooks survive, its **fixed offsets** (SDK dumps) crash the game at launch. See [demo-built-mod-on-a-retail-game-fixed-offsets-crash.md](./demo-built-mod-on-a-retail-game-fixed-offsets-crash.md) |
| Turn it off | Restore `exe.ORIGINAL` | Rename or delete the proxy DLL; or the plugin's own `enable = false` |
| Anti-cheat / signatures | Modified exe fails any signature check | Exe untouched; proxy DLLs are what AV heuristics dislike |
| Trust surface | Your 1-byte diff | Someone else's 1.5 MB plugin plus a 3.6 MB loader; check version info (`CompanyName: ThirteenAG`) and hashes, scan with Defender |
| Backups | `exe.ORIGINAL` next to it, loader ignores it | A backup plugin must **not** end in `.asi`, the loader loads every one |

**Decision rule.** A maintained runtime fix for the game exists → use it, after checking its release date against the game's build date and its issue tracker. None exists, or the game is a one-off → a length-preserving byte patch to the consuming branch, found by a signature whose uniqueness you measured, shipped as a `.bat` that refuses on anything but exactly one match. The user's history leans towards deterministic patches: a runtime injector (Flawless Widescreen) black-screened War in the North, which is why "a maintained fix exists" has to mean one that someone has run on the current build.

## Checklist for the next Unreal game

1. Resolution is set and correct (`GameUserSettings.ini` shows your width and height) but the image is 16:9 → it is the camera constraint, not the resolution. Ini resolution tweaks will not help.
2. Search GitHub for `<game> fix` (PolarWizard, Lyall) and the game's Nexus page. Compare dates with the Steam build. Read the issues.
3. If using a plugin: version info and hash of the loader, Defender scan, read the plugin's `install()` to know which features touch SDK offsets.
4. If patching: look for a `.pdb`, else signature-scan for the two consumer sites above. Cross-validate the address two independent ways before writing.
5. Test list for the user: title screen, gameplay fills width, battle, map/menus, one pre-rendered movie (should stay 16:9 with bars), HUD edges. Two battles if the mod touches encounter transitions.

**See also:** [patch-the-consumer-not-the-value.md](./patch-the-consumer-not-the-value.md), [unity-il2cpp-aspect-lock-is-game-code.md](./unity-il2cpp-aspect-lock-is-game-code.md), [demo-built-mod-on-a-retail-game-fixed-offsets-crash.md](./demo-built-mod-on-a-retail-game-fixed-offsets-crash.md).
