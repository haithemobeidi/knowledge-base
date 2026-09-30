---
stack: [android, adb, animation, debugging, testing]
kind: pattern
last_verified: 2026-09-27
---

# Film it before reasoning about it: `adb screenrecord` → every frame → a step scan, plus the device traps that return wrong evidence

**One-liner:** for any bug the user can *see* in motion (a hairline, a flicker, a missing animation, a shadow arriving late), guessing from code costs hours, while a recording cut into frames usually finds it in minutes. That happened in four separate Android sittings. Record with `adb shell screenrecord` while driving the gesture, extract **every real frame** with ffmpeg, and scan for a **step** (a region suddenly brighter or darker than its neighbour), not a peak. Then switch the suspect off and film again. The device tools also have traps that return stale or wrong evidence without looking broken; those are listed at the end.

*Playmoir Android on a Pixel 10 Pro Fold (Android 17), 2026-09-19 → 09-27: M-39 hairlines, M-45 white edges, M-75 flicker, M-81 missing first flight, M-35 late shadow.*

## Why film

- **A metric can't see a missing animation.** Frame times were fine (22.7 ms cold vs 19.9 ms warm) on the flight that never ran (`compose-nav-flag-lifetime-first-flight.md`).
- **One number can't see a three-state bug.** "How long is the button absent?" moved with four fixes while the user saw no change (`compose-shared-element-overlay-covers-your-button.md`).
- **The eye's report is about a specific build.** Film the build the user sees, not a debug build (`test-build-change-recheck-eye-reports.md`).

## The recipe

```bash
# while driving the tap (a foldable's inner panel needs its display id)
adb -s <serial> shell screenrecord --display-id <id> --bit-rate 20000000 --time-limit 4 /sdcard/x.mp4
# (or stop early: adb shell pkill -INT screenrecord)
adb -s <serial> pull /sdcard/x.mp4
ffmpeg -i x.mp4 -fps_mode passthrough frames/%04d.png   # every real frame, no resampling
ffprobe -show_frames x.mp4                              # real presentation times
```

Then:
- **Step scan, not peak scan:** sample a strip across the suspect edge in every frame, and flag frames where it jumps relative to the pixels just below it. A peak detector gets fooled by bright art.
- **Measure what the user described,** in their terms ("renders, unrenders, re-renders" is three states).
- **Negative control:** switch the suspected cause off and film again. If the film is identical, the suspect is innocent, however good the theory.
- Watch the frame geometry: on the Fold the recording was 2076 wide with the 1080-wide screen centred (x offset 498).

## Device traps that hand back wrong evidence

| Trap | What you see | Fix |
|---|---|---|
| `screencap` without `--require-dpu` | a **stale cached frame** that looks like "the tap did nothing" (caught when the status-bar clock lagged by a minute) | `screencap -d <display> --require-dpu -p …` for any evidence frame |
| foldable, no display id | nothing usable | pass `-d` / `--display-id` for the active panel |
| the phone listed twice (ip:port and mDNS) | "more than one device" | always `-s <serial>`; re-read it, the port rotates |
| Git Bash path conversion | `/sdcard/x` becomes `C:/Program Files/Git/sdcard/x` | `MSYS_NO_PATHCONV=1`, or `//sdcard/...` |
| `uiautomator dump` mid-animation | a stale or wrong-window tree, or "could not get idle state" | wait 2 s, retry once, then tap from a fresh `--require-dpu` screenshot |
| `monkey -p <pkg> … 1` to launch | random events after launch, including **turning auto-rotate on** | launch with `am start -n <pkg>/.MainActivity` |
| `pm clear --cache-only` (Android 17) | denied (`INTERNAL_DELETE_CACHE_FILES`), and the CLI **hangs**, exiting 255 minutes later | Settings → Storage & cache → Clear cache, opened with `am start -a android.settings.APPLICATION_DETAILS_SETTINGS -d package:<pkg>`; plain `pm clear` wipes the data |
| an agent drives the phone the user is holding | a share sheet sits over the app mid-run | check the focused window before each gesture block |

The Android 17 cache-clear behaviour was seen on one device; check yours before generalising.

## Related

- `screen-recordings-lie-about-luminance.md`: the Windows capture pitfall (tone mapping), different from these.
- `negative-control-before-trusting-a-probe.md`, `instrument-before-patching.md`.
- `partial-coverage-edges-half-over-half.md`: a bug found this way.
