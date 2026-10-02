---
stack: [android, adb, testing]
kind: gotcha
last_verified: 2026-10-02
---

# Wireless adb: "connection refused" means the PC isn't paired, and the port you were given may be the wrong one

**One-liner:** when `adb connect <ip>:<port>` fails against a phone with Wireless debugging on, ask the network which ports the phone is advertising with `adb mdns services` before you guess. If the TLS connect port refuses, this PC isn't paired (or the pairing was lost). The fix is one pairing code from the phone, `adb pair`, then `connect`. Don't retry the same connect.

*BuddySystem / Rephrase Buddy on a Pixel 10 Pro Fold, 2026-10-02. The PC built the APK fine; the install stalled on the connection for three attempts until mDNS showed what was actually going on.*

## What happened

The user gave the phone's address from the Wireless debugging screen: `192.168.1.183:35847`.

| Attempt | Result | What it meant |
|---|---|---|
| `adb connect 192.168.1.183:35847` | `failed to connect` | The TLS connect port exists but won't talk to an unpaired PC |
| `ping 192.168.1.183` | replies | The network is fine; don't chase Wi-Fi |
| `adb mdns services` | `_adb-tls-connect._tcp 192.168.1.183:35847` and `_adb._tcp 192.168.1.183:5555` | The phone is advertising; 35847 is the right connect port |
| `adb connect 192.168.1.183:5555` | `actively refused (10061)` | Legacy `adb tcpip` port isn't open; not the way in |
| Phone: *Pair device with pairing code*, then `adb pair 192.168.1.183:41129 231904` | `Successfully paired` | Pairing uses a **different, short-lived port** from connecting |
| `adb connect 192.168.1.183:35847` | `connected` | Install worked from here |

`adb devices` was also empty at the start because the adb daemon had just been started. That's normal and not a sign of anything.

## The recipe

```bash
adb mdns services                       # what is the phone actually advertising?
adb connect <ip>:<tls-connect-port>     # works if this PC is paired
# refused → on the phone: Developer options → Wireless debugging → Pair device with pairing code
adb pair <ip>:<pairing-port> <6-digit-code>   # pairing port + code are on the pairing dialog, expire in ~1 min
adb connect <ip>:<tls-connect-port>
adb devices -l                          # may list the phone twice (ip:port and the mDNS name); use -s <ip:port>
```

## Gotchas

- **Two ports, two jobs.** The pairing dialog shows a pairing port that is valid for about a minute. The Wireless debugging screen shows the connect port. Pairing with the connect port, or connecting with the pairing port, both fail without a useful message.
- **The connect port changes** when Wireless debugging is toggled or the phone reboots. `adb mdns services` is the cheap way to read the current one without asking the user.
- **Pairing persists** (the PC's `~/.android/adbkey` is remembered by the phone) until the user revokes authorizations or the phone forgets it. So a refused connect on a PC that used to work usually means the phone dropped the pairing, not that anything is broken.
- **Port 5555 is a different mechanism** (`adb tcpip 5555` over USB first). It shows up in mDNS on some phones but refuses unless that mode was enabled. Don't use it as a fallback.
- **Two device rows.** After connecting, the phone can appear as both `ip:port` and `adb-<serial>-<id>._adb-tls-connect._tcp`. Any `adb` command without `-s` then fails with "more than one device".
- **Ask for the pairing code early.** If the user is about to step away, the pairing code is the one thing only they can provide. Ask for it with the first refused connect, not the third.

## Related

- [`film-it-adb-screenrecord.md`](./film-it-adb-screenrecord.md): what to do once you're connected (recording, device traps).
- [`play-billing-sideload-testing.md`](./play-billing-sideload-testing.md): sideload signing, which decides whether an install is in-place.
