---
stack: [python, pathlib, windows, git, line-endings, scripting]
kind: gotcha
last_verified: 2026-11-03
---

# `Path.write_text()` on Windows turns every `\n` into `\r\n`, and `read_text()` hides it from you

**One-liner:** a quick Python read-modify-write (`p.write_text(p.read_text().replace(a, b))`) run on Windows silently converts an LF file to CRLF. Text mode translates `\n` to `os.linesep` on write. The same script never notices, because `read_text()` translates `\r\n` back to `\n` on read. The damage shows up later, in a different tool that reads bytes: an exact multi-line match fails, git starts warning, a shell script breaks on Linux. Write with `newline=""` (or `write_bytes`) and it can't happen.

## Measured (Python 3.14.0, Windows 11, 2026-11-03)

Start with an LF file, `b"line one\nline two\n"`:

| Step | `\r` bytes in the file |
|---|---|
| start | 0 |
| `p.write_text(p.read_text().replace("two", "2"))` | **2**: both newlines are now `\r\n` |
| `p.write_text(p.read_text(), newline="")` (on a fresh LF copy) | 0 |
| `open(p, "w").write("a\nb\n")` | 2: plain `open()` in text mode does the same |

And the reason nobody notices:

| Reader | Sees the `\r`? | `"line one\nline 2" in text` |
|---|---|---|
| `p.read_text()` | no (universal newlines) | True |
| `p.read_bytes().decode()` | yes | **False** |

So the API that caused the change can't see it. Anything that compares bytes can.

## Where it bit

Session-state docs in a repo, edited by small inline Python scripts during a long session (2026-11-02):

1. An early edit used `read_text` / `write_text`. Git warned `in the working copy of 'docs/CURRENT_STATE.md', CRLF will be replaced by LF the next time Git touches it`. The commit itself was fine: the repo's `.gitattributes` (LF everywhere) plus `core.autocrlf=true` normalised the blob to LF. The working copy stayed CRLF.
2. A later edit read the file with `read_bytes().decode()` to avoid newline translation, and its `assert text.count(old) == 1` failed on a multi-line `old` joined with `\n`. The single-line replacements earlier in the same script had already gone through, so the file was half-edited when it stopped.
3. After converting the working copy back to LF, `git status` still showed the file `M` with an empty `git diff`. The bytes were identical to `HEAD` (`cmp` agreed), but the index's cached state was stale. `git update-index --really-refresh` didn't clear it; `git add <file>` did, and committed nothing.

The more serious version is a file that ends up on Linux. A CRLF shell script fails with `$'\r': command not found`, and a CRLF value in a config file carries a stray `\r` that a parser may or may not strip.

## The fix

- **Write:** `p.write_text(s, encoding="utf-8", newline="")` (the `newline` parameter exists from Python 3.10), or `p.write_bytes(s.encode("utf-8"))`. For `open()`, pass `newline=""` too.
- **Read for exact matching:** `p.read_bytes().decode("utf-8")` shows the file as it really is. If the file might already be CRLF, normalise it explicitly first (`.replace("\r\n", "\n")`) and write LF back. Don't let the API decide quietly.
- **Repo guard:** a `.gitattributes` with `* text=auto eol=lf` makes git check out LF on every platform, so a Windows working copy matches what Linux gets.
- **Check before a byte-exact edit:** `file x.md` says `with CRLF line terminators` when it is.
