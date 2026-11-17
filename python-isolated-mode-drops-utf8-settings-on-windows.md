---
stack: [python, windows, encoding, cli, claude-code]
kind: gotcha
last_verified: 2026-11-17
---

# `python -I` ignores PYTHONIOENCODING and PYTHONUTF8, so piped output on Windows falls back to cp1252

**One-liner:** isolated mode (`python -I`) is the safe way to run a script that reads untrusted files, and it also ignores every `PYTHON*` environment variable, including the two that make output UTF-8. On Windows, a piped or redirected `print()` then encodes with the ANSI code page (cp1252). A character cp1252 lacks (an arrow `→` in a customer email) raises `UnicodeEncodeError`. Worse, characters cp1252 does have (em-dash, curly quotes) don't raise at all: they go out as cp1252 bytes, which a UTF-8 reader shows as garbage. Fix it in the script with `sys.stdout.reconfigure(encoding="utf-8")`, or on the command line with `-X utf8`, which `-I` doesn't touch.

*Cove support copilot, 2026-11-16: a one-off `python -I -c` that printed ticket text failed on `→`, while the project's scripts, run without `-I` in the same shell, printed fine. Measured on Python 3.14.0, Windows 11, Git Bash.*

## Why `-I` is in the command at all

Isolated mode keeps the script's own directory and the current directory off `sys.path`, so a planted `json.py` next to a downloaded file can't run on `import json`. Agent environments ask for it whenever Python reads files that came from outside. It implies `-E` (ignore all `PYTHON*` variables) and `-s` (no user site-packages). Measured with `-I`: `sys.flags.isolated == 1`, `ignore_environment == 1`, `no_user_site == 1`, `safe_path == True`.

`-E` is the part that bites. `PYTHONIOENCODING` and `PYTHONUTF8` are environment variables, so they're gone.

## Measured (stdout piped to `cat`, so not a console)

| Command | `sys.stdout.encoding` | `print("a→b")` |
|---|---|---|
| `PYTHONIOENCODING=utf-8 python -c ...` (exported) | utf-8 | prints `a→b` |
| `PYTHONIOENCODING=utf-8 python -I -c ...` | cp1252 | `UnicodeEncodeError: 'charmap' codec can't encode character '→'` |
| `PYTHONUTF8=1 python -I -c ...` | cp1252 (`sys.flags.utf8_mode == 0`) | same error |
| `python -I -X utf8 -c ...` | utf-8 | prints `a→b` |
| `python -I -c "import sys; sys.stdout.reconfigure(encoding='utf-8'); ..."` | utf-8 | prints `a→b` |

Redirecting to a file instead of a pipe gives cp1252 too. A real console is different: Python writes to it through the wide-character console API, so the bug hides while you test by hand and appears when a tool or agent captures the output.

## The silent half

`print("—’")` (em-dash, right single quote) under `-I` writes the bytes `97 92`: valid cp1252, invalid UTF-8. Nothing raises. Whatever reads the output as UTF-8 shows replacement characters, or a later step chokes on them. Mojibake in the middle of a report is the symptom, not an error, and the error only arrives at the first character cp1252 can't encode.

## Fixes, in order of preference

- **In the script:** `sys.stdout.reconfigure(encoding="utf-8")` near the top (Python 3.7+). It works whatever the flags and the environment are. Do the same for `sys.stderr` if tracebacks may carry user text.
- **On the command line:** `python -I -X utf8 ...`. `-X` options are arguments, not environment, so isolation keeps them.
- **Don't print data at all:** write it to a file opened with `encoding="utf-8"` and read the file. Printing is for short summaries.

## A nearby shell trap

`PYTHONIOENCODING=utf-8 && python ...` sets a shell variable; unless it was already exported, the child never sees it (measured: `FOO=1 && python -c "import os; print(os.environ.get('FOO'))"` prints `None`). Use `export VAR=...` first, or put it on the same command: `VAR=... python ...`. Either way, it's still ignored under `-I`.

## The future

PEP 686 (Final) turns UTF-8 mode on by default from Python 3.15. That default doesn't come from the environment, so `-I` shouldn't undo it. Check `sys.flags.utf8_mode` on the version you actually run before relying on it.

## Related

- [[python-write-text-turns-lf-into-crlf-on-windows]]: the other Windows default that changes bytes behind the script's back.
- [[powershell-51-utf8-no-bom-string-breakage]]: the same cp1252 default, on the PowerShell side.
