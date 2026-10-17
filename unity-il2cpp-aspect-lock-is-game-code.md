---
stack: [unity, il2cpp, windows, games, reverse-engineering, python, powershell]
kind: playbook
last_verified: 2026-10-17
---

# A Unity ultrawide lock lives in the game's code, not the engine; find it through the IL2CPP dump

**One-liner:** Unity itself renders any aspect ratio, and its perspective cameras are Hor+, so a Unity game stuck in 16:9 has *the game's own C#* forcing it. On IL2CPP builds that C# is compiled into `GameAssembly.dll`. Il2CppDumper recovers every class, field and method RVA from `global-metadata.dat`, which turns "scan 72 MB for a plausible pattern" into "read the method named `ApplyResolutionChange`". From Castlevania: Belmont's Curse (2026-10-17): the 16:9 lock was a `supportOnly16By9` field in the game's `VideoSettings`, enforced in two layers, and was undone with **3 bytes**. Nothing was injected, no loader was installed, and no FOV math was needed.

## This is a method, not a reusable patch

Every Unity game hand-rolls its 16:9 lock somewhere different, so a fix for one game won't carry to another. Common homes:

- **A settings or resolution class.** This one filtered the menu and swapped in a 16:9 table at apply time.
- **`Camera.rect` / `pixelRect` letterboxing.** A component computes a viewport rect from `Screen.width / Screen.height`.
- **`CanvasScaler`.** `matchWidthOrHeight` keeps the UI at 16:9 while the 3D view is fine. A HUD-only problem.
- **The engine's own `PixelPerfectCamera`** (URP 2D). It crops to its reference resolution.
- **Cinemachine confiners.** They clamp the camera to room bounds sized for 16:9. That doesn't letterbox; you see past the room's edges instead.

To find which one, xref the **game assembly's** callers of `Camera.set_rect`, `Screen.SetResolution` and `CanvasScaler.set_matchWidthOrHeight`. Only callers outside `UnityEngine.*`, `Cinemachine.*` and DOTween matter. In this game every `set_rect` caller was a library (planar reflection, split screen, DOTween). That ruled out letterboxing in one pass and pointed at the settings class.

## The two-layer shape (this game)

1. **Menu filter.** A LINQ closure allowed a resolution only if it was 16:9, *or* if `supportOnly16By9` was off and the resolution matched the monitor's ratio. The constructor hard-sets the flag (`mov byte [rcx+0x40], 1`), and the serialized asset almost certainly does too, so the field is a decoy (see [patch-the-consumer-not-the-value.md](./patch-the-consumer-not-the-value.md)). Fix: `je`→`jmp` on the branch after `cmp byte [rcx+0x40], 0`.
2. **Apply-time swap.** `ApplyResolutionChange` looked the chosen index up in two parallel static tables and passed **the 16:9 one** to `Screen.SetResolution`. So 3440x1440 in the menu became 2560x1440 in a forced borderless window. Fix: point both loads of static `+0x8` at `+0x0` (disp8 `08`→`00`).

Either layer alone looks like a failure. Unlocking the menu gives you an entry that still applies 16:9, and fixing the apply step changes nothing while the entry is greyed out. When an unlock "does nothing", look for a second consumer.

## Then the UI breaks: width-matched CanvasScalers

Native resolution exposed a third problem the 16:9 lock had been hiding. The UI canvases were 3840x2160 `ScaleWithScreenSize` scalers with `matchWidthOrHeight = 0`, which matches **width**. At 3440x1440 that gives a scale of 0.90 instead of 0.67, so the UI is about 34% too tall: cards spilled out of their panels and covered headers. Check this before shipping any Unity ultrawide fix.

- **Reading scaler settings from the assets:** with UnityPy, take every `MonoBehaviour`'s `get_raw_data()` and search for the scaler's fixed tail, `0000c042 0000c042 0000803f` (fallback DPI 96, sprite DPI 96, dynamic PPU 1). Walking back 32 bytes gives mode, reference PPU, scale factor, reference resolution, match mode and match. No typetree is needed, and all 3,049 files took a few minutes. The 1920x1280 ones turned out to be nested canvases, where a scaler does nothing; the 3840x2160 ones were the roots that matter.
- **The fix belongs in Unity's own `CanvasScaler.HandleScaleWithScreenSize`,** not in 1,000 assets. Right after the screen size is read (here `xmm8` = width, `xmm7` = height), clamp `width = min(width, height * 16/9)`. The UI sizes as on a 16:9 screen of the same height and gets the extra width. 16:9 and narrower screens get bit-identical values, since `1080 * 1.7777778f` is just above 1920. It's a 6-byte `jmp` + `nop` hook over two instructions (`mov ecx,[rbx+0x34]; xorps xmm6,xmm6`), which the cave replays before jumping back.
- **Cave space was scarce:** the game-code `il2cpp` section's longest int3 run was 17 bytes. The runtime's `.text` had one 30-byte run after a `ret`. Building the constant in a register (`mov eax, 0x3FE38E39; movd xmm0, eax`) instead of loading it from memory brought the cave down to 29 bytes. Check that the scratch register is dead at the hook; here `eax` was overwritten by the next call.
- **Unavoidable side effect:** elements anchored to the screen edges move outward (cards drifted away from their centre-anchored headers). Unity always stretches screen-space canvases across the whole screen, so a "16:9 box" can't be done from the scaler. Readable and correctly sized is the realistic target; ask the user whether the drift bothers them.

## Toolchain and its traps

- **Il2CppDumper:** `Il2CppDumper.exe GameAssembly.dll <Game>_Data/il2cpp_data/Metadata/global-metadata.dat <outdir>`. Run it from **PowerShell with Windows paths**, and set `"RequireAnyKey": false` in its `config.json`. Launched from Git Bash with `/f/...` paths, it silently fell back to a **GUI file-open dialog** on the user's desktop, which they noticed and asked about, and it wrote nothing.
- **`script.json`** maps address → name for every method and metadata slot (`VideoSettings_TypeInfo`, `Method$...`). Load it and annotate capstone output, so `call` and `[rip+x]` targets get names.
- **The code is in a section named `il2cpp`, not `.text`** (which held only about 4.7 MB of runtime). An xref scanner that took the first `.text*` section found zero callers, which looks exactly like "no callers exist". Iterate the sections or pick the big executable one. File offset = RVA − (section VA − raw pointer); here that was RVA − 0xC00.
- **Identical-code folding lies about names.** `Resolution.get_width` showed up as `UnityEngine.Touch$$get_fingerId`, and `get_height` as `TextCore.GlyphRect$$get_y`, because they're byte-identical getters merged by the linker. Treat names on `call` targets as hints. Work out meaning from the field offsets and what the caller does with the result.
- **Small helpers get inlined.** `Is16By9` had zero callers because its body was pasted into the closure. A dead-looking helper still tells you the constants to look for (`1.7777778` and the `0.01` tolerance).
- **Static fields:** `mov rax, [Class_TypeInfo]; mov rcx, [rax+0xB8]` gives the static-fields block, and the dump's `// 0x8` comment on a static is its offset inside that block. That's how "the second table" became the single byte `[rcx+8]`.
- **Value arrays:** a `ValueTuple<int,int>[]` stores elements at `+0x20 + i*8` and the length at `+0x18`. Decode the `.cctor` to get the real resolution list (the `mov edx, W` / `mov r8d, H` pairs).
- **Python in Git Bash:** `python -I` (isolated mode) drops user site-packages, so `capstone`/`pefile` "aren't installed". Keep your scripts in their own folder and run them without `-I`. Only the inputs are untrusted, and they're binaries, not Python.

## Shipping it

Follow the rules in [patch-the-consumer-not-the-value.md](./patch-the-consumer-not-the-value.md): signature scan, refuse unless the match count is exact, back up, detect your own previous patch. Two additions from this one:

- **When identical sites are legitimate, check their spacing.** The table load appears twice (width read, height read). The script requires exactly 2 matches, **0x4B bytes apart**, so a future build with a third look-alike makes it refuse instead of writing to it.
- **The `.bat`-with-embedded-PowerShell launcher breaks on an apostrophe in its own path.** `-Command "...Get-Content -LiteralPath '%~f0'..."`: the game folder "Castlevania Belmont's Curse" closes the quote, and you get "The string is missing the terminator". Pass the path through an environment variable instead (`set "SELF=%~f0"` → `$env:SELF`). The earlier WITN/LORWIN/Vahrin's Call scripts have the same latent bug; their folders just happen not to contain `'`.
- **PowerShell aliases beat functions.** A helper named `Cat` made every call run `Get-Content` (alias `cat`), which failed with "Cannot convert 'System.Object[]' to … 'Path'". Before naming a helper, check `Get-Alias <name>`; `cat`, `gc`, `sort`, `diff`, `kill`, `ls`, `type` and `select` are all taken.
- **Detect independent parts independently.** Once the patcher gained a second part, a DLL patched by the first release was neither stock nor fully patched. Give each part its own stock / patched / unknown state, apply only what's missing, and refuse only on unknown. Test the whole matrix on scratch copies: stock → apply, re-run, undo with a backup, old release → upgrade, undo without a backup, one flipped byte → refuse. The script's running-game check will block tests while the user is playing, so run the test copy with that one guard renamed.
- For a public repo, add `*.bat text eol=crlf` to `.gitattributes`, find the game through `HKCU\Software\Valve\Steam` → `libraryfolders.vdf` rather than a hardcoded drive, and don't commit any game binaries (`*.dll` in `.gitignore`).

## When it's overkill

On a Mono build (`<Game>_Data/Managed/Assembly-CSharp.dll`, no `GameAssembly.dll`), skip all of this. Open the DLL in dnSpy/ILSpy, read the real C#, and edit the IL directly. If a maintained BepInEx/MelonLoader ultrawide plugin already exists for the game, use it. A byte patch only earns its keep when there's nothing to install alongside the game and the change is a few branches.
