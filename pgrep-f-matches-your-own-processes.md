---
stack: [linux, bash, ssh, procps, pgrep, pkill, handheld]
kind: gotcha
last_verified: 2026-11-03
---

# `pgrep -f` matches your own processes too: the shell that ran it, and every helper whose arguments carry the word

**One-liner:** `pgrep -f <pattern>` tests the pattern against the **full command line** of every process. `pgrep` leaves itself out, but nothing else you started. That includes the remote shell (`bash -c '<your whole command>'`, which contains the pattern) and any helper you launched earlier with the token in its arguments. An "is the app running? then abort" guard built on it fires on your own tooling. `grep -v pgrep` only hides the shell. Match something only the target has, the exact executable, and write it with the `[x]` bracket trick so the pattern can't match its own text.

## What happened (2026-11-02, a Linux handheld over SSH)

Before copying files into a game's folder, the script refused to run if the game was up:

```bash
pgrep -af -i "ffrs|resonance" | grep -v pgrep && { echo GAME RUNNING, abort; exit 1; }
```

It aborted, and the game wasn't running. The match was my own sleep inhibitor, started a minute earlier to keep the device awake during the transfer:

```
10282 systemd-inhibit --what=sleep:idle --who=ffrs-mod --why=mod transfer sleep 1200
```

The `grep -v pgrep` filter did its one job: it hid the SSH session's shell, whose command line contained both the pattern and the word `pgrep`. It couldn't hide a helper. Had the same pattern gone to `pkill -f`, it would have killed the inhibitor, letting the device suspend mid-copy, and the SSH session's own shell with it.

The retry was luckier than it looked:

```bash
pgrep -af -i "FFRS[^ ]*\.exe|FINAL FANTASY RESONANCE/" | grep -v -e pgrep -e unzip
```

Its second branch also matched the remote shell, because the shell's command line carried the destination path `…/common/FINAL FANTASY RESONANCE/FFRS/Content/Paks`. Only the `grep -v pgrep` saved it. The pattern you guard on tends to appear in the command you're running, because you're operating on the target's own folder.

## The rules

- **Match what only the target has.** For a game, that's its executable (`Game-Win64-Shipping.exe` under Proton/Wine, the binary path for a native one), not a word from its title, folder or Steam name.
- **Use the bracket trick instead of `grep -v`:** `pgrep -af '[G]ame-Win64-Shipping\.exe'`. The regex `[G]ame…` matches `Game…` but not the literal text `[G]ame…` in your own shell's command line. It works the same for `pkill -f`.
- **Name your helpers with words your guards never search for.** The retry's inhibitor became `--who=modxfer`.
- **`pgrep -x name` (no `-f`) matches the process name, which the kernel truncates to 15 characters.** A long Wine executable name needs its truncated form, or `-f` with the full name.
- **Preview before you kill:** run `pgrep -af '<pattern>'` and read the list, then `pkill -f` with exactly the same pattern.

## Related

- `native-arm64-build-on-the-device.md` §5: the sharper case. `pkill -f pattern` over `ssh` kills the session's own shell, and the SSH command exits 255.
