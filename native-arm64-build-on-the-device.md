---
stack: [linux, arm64, aarch64, fedora, distrobox, podman, cmake, ninja, clang, ffmpeg, dxc, vulkan, btrfs, ssh, handheld, static-recompilation, build-estimation]
kind: playbook
last_verified: 2026-11-01
---

# Building an x86-first open-source project natively for ARM64, on the ARM64 device itself

**One-liner:** a project that ships Windows / Linux x86-64 / macOS / Android builds but **no Linux ARM64** can usually be built natively on the ARM64 Linux device, inside a container whose distro matches the host's. You skip the cross sysroot, and the binary runs on the host. Upstream's "ARM64 Linux" scripts are often x86-64 cross-builds that nobody has run end to end, so expect two kinds of gap. First, **generated per-platform files** that only exist for the platforms upstream ships. Second, **libraries the program loads at run time** (`dlopen`), which configure, link and `ldd` never check. Upstream usually documents a recipe for a sibling platform, and following it is how you fill both gaps.

*Verified 2026-11-01: LostOdysseyRecomp v1.1.0 (static recompilation of an Xbox 360 game, C++/CMake) on an AYN Odin 3 (Snapdragon 8 Elite, 8 Oryon cores, 16 GB) running Fedora 44 bootc (ArmadaOS). Container setup took under 1 min. The game compiled in 263 s at `-j 4`, DXC in 287 s, and the game boots on Vulkan (Turnip).*

## 1. The shape that works

1. **A container matching the host OS:** `distrobox create --name build --image registry.fedoraproject.org/fedora-toolbox:44` on a Fedora 44 host. Same glibc and the same library sonames, so what you build in the box runs on the host. Map upstream's Ubuntu `apt` package list to Fedora names and install with `dnf install --skip-unavailable`, then print the missing ones. That's quicker than guessing all of them right.
2. **Bypass upstream's ARM64 script if it cross-builds.** Read it for the *flags* (here `-DLO_TARGET_ARCH=armv8-a`, plus the CMake options for each dependency), then run the project's normal Linux configure natively with those flags. A cross toolchain file that hardcodes `/usr/aarch64-linux-gnu` is useless on the device.
3. **Copy CI's exact steps** (`.github/workflows/*.yml` at the release tag): submodule patches applied idempotently (`git apply --reverse --check … || git apply …`), the build-input step, codegen, then the build. Swap `clang-18` for the distro's `clang`.
4. **`ldd` the result on the host, outside the container.** No `not found` means the link-time dependencies are fine. It does *not* cover `dlopen` (§3).
5. **Install the program somewhere stable, not in `out/build/`.** Self-built Linux copies often keep data, saves and settings beside the executable (the "portable" layout). A clean rebuild would delete them. Copy the binary plus whatever upstream's package script copies (read `package_appimage.py` or its equivalent: here it was the binary and an `assets/` folder).

## 2. Generated per-platform files: regenerate with the dependency's own configure

Configure stopped with `No FFmpeg config for linux-aarch64; generate …/ffmpeg-config/linux-aarch64/config.h with the fork's ./configure`. Upstream vendors a pre-generated `config.h` per platform and ships only `android-aarch64` and `macos-aarch64`. The Android folder's README recorded the exact recipe, and the macOS header records its configure line in `FFMPEG_CONFIGURATION`. Steps:

- Copy the **pinned** dependency source to a throwaway folder (here CMake had already fetched it into `_deps/…-src`). Move the fork's tracked `config.h` aside, because it's a platform dispatcher.
- Run the sibling platform's configure line with the target swapped: `./configure --cc=clang --arch=aarch64 --target-os=linux --disable-everything … --enable-decoder=<what the project needs>`.
- Copy `config.h` to the expected path. Sanity check: same line count as the siblings, and the key defines (`ARCH_AARCH64`, `HAVE_NEON`, the decoders) match the macOS/ARM64 one.

**General form:** when a build refuses because a generated file is missing for your platform, look for that file's sibling folders and their README. The recipe is nearly always written down for one platform. It's a one-file upstream PR afterwards.

## 3. Run-time-loaded libraries: configure and `ldd` can't see them

The game built, linked, passed `ldd`, imported its data, downloaded its portable shader pack, found the GPU, and then exited cleanly: `dxcompiler library not available: …/libdxcompiler.so: cannot open shared object file` → `no usable backend; guest startup aborted`. Upstream's docs called ARM64 DXC a fallback for shader-pack misses. In practice the **presentation shaders compile live at every start**, so it was required. Configure had been silent about it.

- **Read the first run's log for `dlopen` failures** before believing a build works. Grep it for `cannot open shared object`, `not available` and `fallback`.
- Fedora 44 has no DXC package (only DirectX-Headers). Microsoft's Linux releases are x86-64 only.
- Build it natively from upstream's **pinned revision**, using the *target* half of upstream's cross script: same CMake flags (`-DENABLE_SPIRV_CODEGEN=ON -DLLVM_TARGETS_TO_BUILD= -DLLVM_DEFAULT_TARGET_TRIPLE=dxil-ms-dx …`), and the script's source patch for new compilers. Drop the cross half (the NATIVE TableGen host build and the toolchain file); on the device everything is native. It needs `clang-format` (`clang-tools-extra`). Build only the `dxcompiler dxc` targets.
- **Smoke-test before staging:** compile a one-line HLSL pixel shader to SPIR-V with the new `dxc` and check the magic `0x07230203`. Then put `libdxcompiler.so` next to the binary, and also in the project's staging path so future builds copy it.

## 4. Estimating the build time from CI: use a cold run, then scale

CI step timings are a good estimate only from a run with **0 % compiler-cache hits**. The latest release run showed a 3-min compile at 68 % ccache hits, while cold runs took 17:33–18:04 on 4-vCPU GitHub runners (`ccache --show-stats` in the job log tells you which kind of run you're reading). Even the cold number was **4× pessimistic** for the device: 263 s at `-j 4` on 2 + 6 Oryon cores. Shared CI vCPUs are slow. Treat a cold CI time as an upper bound and scale it by core count and per-core speed. At `-j 4` the CPU zones reached 94 °C and throttled at their 90/95 °C passive trip points (hot and critical trips were 120/125 °C), fan at max, battery at 32 °C. It was safe but loud.

## 5. Traps met along the way (each cost a retry)

- **distrobox does not share the host's `/var/tmp`.** It shares `$HOME`, `/tmp`, `/run/media` and `/media`. A script written to `/var/tmp` on the host is "No such file" inside the box. Keep scripts and logs under `$HOME`.
- **`cmd1 && cmd2 &` backgrounds the whole chain, and a background job in a non-interactive shell gets stdin from `/dev/null`.** `ssh host 'cat > f.sh && chmod +x f.sh && nohup bash f.sh &' < local.sh` writes an **empty** file. Write the file first, then detach: `cat > f.sh; (setsid nohup bash f.sh >/dev/null 2>&1 </dev/null &)`.
- **`pkill -f pattern` over `ssh` matches its own shell**, whose command line contains the pattern. It kills the session (ssh exits 255) along with the target. Use `pkill -f '[w]ho=x'` or match the exact process name.
- **Importers that walk folders often skip symlinks deliberately.** A symlink pointing at the SD card made the scan find nothing ("no supported discs"). A **bind mount** (`sudo mount --bind <real> <dir>`) looks like a real directory. Unmount it afterwards.
- **btrfs reflink dedup is invisible to `du`.** The app "freed 5.78 GB" with `FICLONE`, yet `du -sh` still showed 22G. `sudo btrfs filesystem du -s <dir>` showed 14.3 GiB exclusive plus 1.8 GiB shared. An app that finds duplicates by content but checks "already shared" by inode will offer the same dedup on every launch.
- **Launching a GUI app over SSH into a KDE Wayland session:** copy `WAYLAND_DISPLAY`, `DISPLAY`, `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` from `/proc/$(pgrep -u $USER -x plasmashell)/environ`. `spectacle -b -n -f -o shot.png` takes a screenshot without a prompt, so you can see what the user sees.
- **Don't poll a long remote build from background loops on the workstation.** Detach the job on the device, write its stages to a log, and check when asked. On a handheld the user's ears are the progress bar: the fan drops when the compile ends.

## Related

- `march-native-ships-an-unrunnable-binary.md`: the opposite risk. A native build is fine *here* because the build machine **is** the target, but don't ship that binary to other ARM64 CPUs without checking `-march`.
- `first-build-on-a-second-os.md`: what rots when only one platform ever compiles the code.
