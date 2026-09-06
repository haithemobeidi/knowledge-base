---
stack: [android, adb, debugging, any]
kind: pattern
last_verified: 2026-09-06
---

# An app's own export feature is a read channel into storage you can't otherwise reach — and its manifest leaks the paths and IDs you need

You're debugging an app whose data lives somewhere you cannot read: private app storage on an unrooted Android phone (`/data/user/0/<pkg>` — no `su`, app not debuggable so `run-as` refuses, `adb backup` disabled since Android 12), a sandboxed desktop app, a container you can't exec into. The bug is "the app says there's no data, but the data is obviously there." You need to see what's actually on disk, and every direct route is closed.

**The pattern: drive the app's own export / backup / "save to file" feature and read what it writes to shared storage.** The app runs with full access to its own files. Anything it is willing to write out — a backup zip, a diagnostic bundle, a "share" file, a config export — lands in a place you *can* read (`/sdcard/Download`, a picker-chosen folder, a temp dir). Three things make this more than a workaround:

1. **The export's metadata is the prize, not the payload.** Export formats almost always carry a manifest, and manifests are written by code that has the absolute paths in hand. In the case that produced this lesson (GameNative, an Android Steam-on-Wine launcher), a 3 KB save-export zip carried a `manifest.json` whose `roots[].path` entries were the full private paths — `/data/user/0/app.gamenative/files/imagefs/home/xuser-STEAM_4538960/.wine/drive_c/users/xuser/AppData/LocalLow/CONFAK/Zenonia/Save_Release/76561198044866630/slot_000` — including the container directory naming scheme *and* the user's SteamID64 (the folder name), neither of which was readable any other way. Two hours of source reading had produced a guess at that path; the manifest confirmed it in one line.
2. **A 0-byte or "nothing found" export is itself a measurement.** Read the export code path before trusting the empty result: many implementations create the output file *first* (Android SAF `CreateDocument` does this before any app code runs) and bail out *before* writing when their search finds nothing. So "export produced 0 bytes" means "the app's search resolved to zero files", not "the export is broken" — which tells you the app is looking in the wrong place, and turns the question into "where does the app look?" (readable in its source) versus "where is the data?" (readable via the next trick).
3. **Drive mappings are the other half.** Sandboxes that emulate another OS (Wine/Proton containers, Winlator-style launchers, emulators) usually map a shared folder to a drive letter or mount inside the sandbox — GameNative maps `D:` to `/sdcard/Download`. The sandbox's own file manager (here "Open container" → `wfm.exe`) can then copy the private tree *out* to the shared folder, where `adb pull` reads it. The user did one drag-and-drop; from then on the whole save tree was inspectable on the PC, including the game's `Player.log`, which printed the exact save path the game was writing to ("Write Final Path C:/users/xuser/AppData/LocalLow/…").

**Procedure, in the order that pays off fastest:**

- Confirm the direct routes really are closed (`which su`, `run-as <pkg>`, `dumpsys package <pkg> | grep debuggable`) — thirty seconds, and it stops you hunting for root later.
- Trigger the export (UI or `adb shell input tap`), then `adb pull` it and open the manifest first. Extract every absolute path and identifier.
- If the export is empty, read the export code path to learn *where it searched*, then use a drive mapping / share sheet / in-sandbox file manager to copy the real tree to shared storage and diff the two locations.
- Keep the pulled tree — it doubles as the backup you want before touching anything.

**Scope honestly.** The export only shows what the app's code chooses to serialize; a manifest can also *lie by omission* (roots that resolved to nothing are simply absent). And the same channel runs the other way: an import feature is a *write* channel into private storage — but check its parser before relying on it (the one in this case split archive entry names at the first `/`, so any root ID containing a slash could never round-trip; export worked, import did not).

Related: `patch-the-consumer-not-the-value.md` ("mine what shipped by accident" — the same instinct applied to binaries you *can* read), `negative-control-before-trusting-a-probe.md` (an empty result is not proof of absence), `steam-library-integration.md` (the save-location time-skew that made the empty export happen).
