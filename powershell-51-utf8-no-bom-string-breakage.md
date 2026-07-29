---
stack: [powershell, windows]
kind: gotcha
last_verified: 2026-07-29
---

# PowerShell 5.1 reads BOM-less UTF-8 scripts as ANSI — and an em-dash can terminate your string

## Symptom

A `.ps1` written by a modern tool (editor, agent, generator — anything that
saves UTF-8 without BOM) does its main work fine, then dies near the end with
an error that makes no sense, e.g.:

```
The term 'exit' is not recognized as the name of a cmdlet...
+   Write-Host "`nSIGNING FAILED (exit $code) â€” env cleared..."
```

Two tells in one screenshot: the error points *inside* a double-quoted string
(where a bare word should never be parsed as a command), and the punctuation
renders as mojibake (`â€”` where an em-dash was written).

## Cause — two layers, and the second one is the surprise

1. **Windows PowerShell 5.1 decodes BOM-less `.ps1` files as the ANSI code
   page** (cp1252 on Western systems), not UTF-8. `pwsh` 7+ defaults to UTF-8,
   but you don't control which host the user runs — `powershell` is still what
   muscle memory types.
2. A UTF-8 em-dash is bytes `E2 80 94`. Read as cp1252 that's `â` + `€` + —
   the killer — `0x94` = **`”` (right curly double-quote), which PowerShell's
   parser accepts as a legitimate string delimiter.** The string literal
   terminates early, the rest of the line is parsed as code, and you get
   "term not recognized" errors for words that were supposed to be inside a
   message. Curly single-quotes (`0x91`/`0x92`) do the same to
   single-quoted strings.

So it's not "weird characters look ugly" — multibyte punctuation can *change
the parse* of the script. Whether it breaks at parse time (whole file refuses
to run) or runtime depends on where the mangled quote lands.

## Fix

- **Keep `.ps1` files pure ASCII** — hyphens, straight quotes. Simplest and
  robust in every host.
- If you need non-ASCII, **save as UTF-8 *with* BOM** — the only encoding
  signal PowerShell 5.1 respects for UTF-8.
- When generating scripts from a tool whose default is BOM-less UTF-8 (most
  are), treat "no em-dashes / no smart punctuation in .ps1" as a hard rule
  rather than a style preference.

## Adjacent gotcha from the same session: `\uXXXX` in agent tool params decodes to raw bytes

When an AI agent (or any JSON-carrying layer) writes a file containing the
six-character escape TEXT `\u0003`, the JSON decode step may turn it into the
literal control byte before it reaches disk — invisibly. The file then holds
real `ETX`/`BS`/`DEL` bytes that render as `''` in most viewers, and
attempts to fix it by sending the same escape sequence mangle it the same way
again. Way out: write the file through a layer with no escape processing —
build the backslash from a char code and concatenate, e.g. in Node:

```js
const BS = String.fromCharCode(92);        // "\" with zero escaping involved
s = s.split(String.fromCharCode(3)).join(BS + 'u0003');
```

Verify with a hex dump (`od -c`), not a viewer — viewers hide exactly the
bytes you're hunting.
