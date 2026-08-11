---
stack: [cpp, cmake, rust, ggml, whisper-cpp, llama-cpp, simd, packaging, release-engineering, desktop, windows-on-arm]
kind: gotcha
last_verified: 2026-08-11
---

# `-march=native` in a vendored dependency ships a binary that only runs on your build machine

**One-liner:** ggml (whisper.cpp, llama.cpp) defaults `GGML_NATIVE=ON`, which means `-march=native` — *"compile for whatever CPU is doing the build."* Nothing warns you, every test passes, and the artifact you ship contains instructions a large share of your users' CPUs cannot execute. The app launches and behaves perfectly, then dies with **`STATUS_ILLEGAL_INSTRUCTION`** the instant that one subsystem runs — and it is invisible on your machine *by construction*, because the only broken code path is the one your build machine runs flawlessly.

## The shape

You embed a native ML library through a Rust/Node/Python wrapper. It builds fine. It works. You ship it.

A user reports: *"the app crashes when I press stop to transcribe."* Not "transcription fails" — the **whole process disappears**. No error dialog, no log line, no crash report.

Windows Event Log:

```
Faulting application name: yourapp.exe, version: 1.3.1.0
Faulting module name:      yourapp.exe          <- the exe itself, not a DLL
Exception code:            0xc000001d           <- STATUS_ILLEGAL_INSTRUCTION
Fault offset:              0x000000000101abf6
```

`0xC000001D` is the give-away. It is not a null deref (`0xC0000005`), not a stack overflow, not your bug. **The CPU refused an opcode.**

## Confirming it in about five minutes

Do not guess which instruction set. Read the bytes at the fault offset — the fault offset is an RVA, so walk the PE section table to convert it to a file offset, then dump:

```
Bytes at fault:  62 F1 7C 48 11 45 04
Preceding:       C5 F8 57 C0
```

Decode by hand; you only need the first byte:

| prefix | meaning |
|---|---|
| `0x62` | **EVEX → AVX-512** |
| `0xC5` / `0xC4` | VEX → AVX / AVX2 |
| `0x0F` | legacy SSE |

`62 F1 7C 48 11 45 04` unpacks as EVEX with `L'L = 10` (512-bit) → `vmovups ZMMWORD PTR [rbp+0x4], zmm0`. The instruction immediately *before* it, `C5 F8 57 C0` (`vxorps xmm0,xmm0,xmm0`), is plain AVX and executes fine.

**The fault lands exactly on the first ZMM touch.** That is a complete diagnosis, from a crash log, without a debugger, a symbol server, or a reproduction on your own hardware.

## Why almost nobody has AVX-512

This is the part that makes it a shipping bug rather than an exotic one. AVX-512 is **absent** on:

- **Windows-on-ARM** — the x64 emulator (Prism) implements up to AVX2/FMA/BMI2, nothing wider.
- **Every Intel consumer CPU since Alder Lake (12th gen)** — present on the silicon, **fused off at the factory** because the E-cores lack it.
- **AMD before Zen 4.**

So "modern CPU" is not the relevant axis, and a newer machine is *more* likely to lack it than an older one. If your build box is a Xeon, a Rocket Lake part, or Zen 4/5, you are in the small minority that can run what you shipped.

## Why only one feature broke

Two compilers build the two halves of a typical app, with two different ISA policies:

| half | compiler | ISA policy |
|---|---|---|
| your app code (UI, DB, networking) | rustc / tsc / etc. | **baseline** `x86_64` — SSE2 |
| the vendored native lib | CMake, via the `-sys` crate | **`-march=native`** |

Language toolchains target a conservative baseline by default; **C/C++ build systems for perf-critical libraries do the opposite**, because their primary audience compiles from source for their own machine.

The AVX-512 therefore exists *only* inside the ggml objects. Nothing executes them until the feature runs. The result reads like "the transcribe feature is buggy," but transcribe was never buggy — it was the only feature whose machine code the user's CPU could not run.

## The fix

`whisper-rs-sys`'s `build.rs` forwards any `GGML_*` / `WHISPER_*` / `CMAKE_*` environment variable through as a CMake define, so this is a supported lever, not a patch:

```toml
# .cargo/config.toml
[env]
GGML_NATIVE = { value = "OFF", force = true }
```

**`OFF` does not mean "no SIMD"** — which is the reason people leave it ON. In `ggml/CMakeLists.txt`:

```cmake
if (GGML_NATIVE OR NOT GGML_NATIVE_DEFAULT)
    set(INS_ENB OFF)     # NATIVE=ON  -> use -march=native
else()
    set(INS_ENB ON)      # NATIVE=OFF -> enable an explicit baseline
endif()

option(GGML_SSE42 "" ${INS_ENB})
option(GGML_AVX   "" ${INS_ENB})
option(GGML_AVX2  "" ${INS_ENB})
option(GGML_BMI2  "" ${INS_ENB})
option(GGML_FMA   "" ${INS_ENB})
option(GGML_F16C  "" ${INS_ENB})
# GGML_AVX512 is a separate option, default OFF
```

Turning `GGML_NATIVE` **off** turns the explicit instruction-set options **on**. You get SSE4.2 + AVX + AVX2 + BMI2 + FMA + F16C and no AVX-512 — a safe ~2013-and-newer floor, and exactly the set Windows-on-ARM emulates. The perf difference versus AVX-512 is modest; the difference between "runs" and "hard crash" is not.

### The same trap in ARM form

`GGML_NATIVE=OFF` also disables the ARM `-mcpu=native` probe, so an ARM64 build falls back to baseline `armv8-a` and loses `+fp16`/`+dotprod`. That is a **speed** cost only — NEON is mandatory on ARM64.

The obvious recovery is `GGML_CPU_ARM_ARCH=armv8.2-a+dotprod+fp16`. Be careful what you put in it: `+i8mm` is Oryon-and-newer, and requiring it **reintroduces the identical bug in ARM form**. Pin the floor you are willing to support, not the features your laptop happens to have. (Also check your compiler driver accepts the spelling — ggml passes it as a GNU-style `-march=`, and `clang-cl` is picky.)

## Gate it, because you cannot feel this bug

The failure is silent at build time and only manifests on hardware you do not own. So verify the **artifact**, mechanically, every release. Scanning for the EVEX prefix in `.text` is enough and needs no toolchain:

```js
// EVEX is a 4-byte prefix starting 0x62. In 64-bit code 0x62 has no other
// meaning (legacy BOUND is invalid), and P0 is RXBR'00mm — bits 3-2 must be
// 00 and the opcode map (bits 1-0) is 1..3. That constraint is what stops
// embedded data from reading as an instruction.
for (let i = textStart; i < textEnd; i++) {
  if (buf[i] !== 0x62) continue;
  const p0 = buf[i + 1];
  if ((p0 & 0x0c) !== 0) continue;
  const map = p0 & 0x03;
  if (map < 1 || map > 3) continue;
  hits++;
}
```

**Positive-control it before you trust it** — run it against the known-bad binary and confirm it goes red. Ours reported 11,970 hits and exited 1 on the broken release; a gate never observed to fail is not evidence (see [negative-control-before-trusting-a-probe.md](./negative-control-before-trusting-a-probe.md)).

Two traps when re-checking after the fix:

- **The native build is cached.** Cargo/CMake will happily reuse a warm build dir and not re-derive flags, so the gate can still fail after a correct config change. Clear the `-sys` crate's CMake cache before concluding the fix didn't work.
- **Check the shipped exe, not an intermediate.** The static lib is not what users run.

## Where else this lives

`-march=native` is the famous one, but the family is "build-host properties baked into a distributed artifact":

| ecosystem | the thing that bakes your machine in |
|---|---|
| CMake / C++ | `-march=native`, `-mtune=native`, `-mcpu=native` |
| ggml / llama.cpp / whisper.cpp | `GGML_NATIVE=ON` (**the default**) |
| Rust | `RUSTFLAGS="-C target-cpu=native"` |
| NumPy / SciPy from source | auto-detected CPU dispatch baseline |
| PyTorch / TensorFlow custom builds | `-march=native`, or a CUDA arch list matching only your GPU |
| Go | `GOAMD64=v3/v4` (v4 requires AVX-512) |
| Docker | building on arm64 and shipping to amd64 hosts, or vice versa |

The general detector is the same in every case: **inspect the artifact for instructions/architectures narrower than your support floor** rather than trusting that the build "worked."

## When you *do* want native

Legitimately: internal tooling on known hardware, HPC clusters where the build node matches the compute nodes, benchmarking, or a from-source install path where the user compiles on the machine that will run it. The rule is not "never use native" — it is **never use native for an artifact that travels.** If the binary crosses a machine boundary, the ISA must be a floor you chose, not a fact about your desk.

For a distributed app that genuinely needs the top-end path, the answer is **runtime dispatch**, not compile-time native: build several kernel variants, detect CPU features with `cpuid` at startup, and select. That is what ggml's `GGML_CPU_ALL_VARIANTS` + `GGML_BACKEND_DL` do, and what NumPy and modern libcs do. It costs binary size and build complexity, and it is the only way to be both fast and portable.

## The transferable core

**A default that optimizes for the developer's machine is a defect generator for anything you distribute**, and it is the hardest defect class to catch because the build machine is definitionally the one machine where it cannot reproduce. Vendored native dependencies are where this hides, because their defaults were chosen for a *compile-it-yourself* audience and you inherited them silently by adding one line to a manifest.

**Audit the compile flags of native dependencies you did not configure.** You are shipping their defaults, and their defaults were not written with your users in mind.

## See also

- [dev-path-fallback-hides-missing-bundled-asset.md](./dev-path-fallback-hides-missing-bundled-asset.md) — the same family and, remarkably, the *same feature one release earlier*: 1.3.0 shipped a model the installer never bundled (hidden by a compile-time path), 1.3.1 fixed that and shipped an unrunnable one. Two consecutive "works on the build machine" bugs, two completely unrelated mechanisms. Its generalisation — *any code path whose success depends on properties of the build machine is a bug detector disabled on the only machine that runs it* — extends cleanly from file paths to instruction sets.
- [verify-the-artifact-your-user-receives.md](./verify-the-artifact-your-user-receives.md) — adjacent but distinct: there the shipped bytes were the *wrong bytes*; here they are the right bytes that will not execute. Both end at the same rule — measure the artifact, not the build.
- [negative-control-before-trusting-a-probe.md](./negative-control-before-trusting-a-probe.md) — before trusting the AVX-512 gate above, confirm it can go red.
