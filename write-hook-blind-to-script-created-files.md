---
stack: [claude-code, hooks, protocol, git]
kind: gotcha
last_verified: 2026-09-16
---

# A file-tool hook is blind to files that scripts create — match the shell tools too and diff `git ls-files --others` after each call

**One-liner:** A `PostToolUse` hook that matches only `Write|Edit` fires only when the *file tools* touch a file. Anything a shell call creates — a Python script writing twenty Kotlin files, a heredoc, a generator, a `git mv` — never passes through those tools, so the hook queues nothing and the "every new file gets an index entry" guarantee silently stops holding. The failure is invisible until the end-of-session backstop diffs `HEAD`, and only if such a backstop exists. Same family as [[write-triggered-enforcement-blind-to-deletion]]: enforcement keyed on one tool's events misses every other road to the same effect.

## The failure shape

Playmoir, 2026-09-16 (139th session): a permission mode that asks Claude to prefer the shell over the dedicated file tools meant every new file of the session was written by `python - <<'EOF' … EOF` scripts. Five commits, 24 new files, `pending-index-updates.txt` empty the whole time. Nothing was lost — `/end` Step 1b (`git diff --name-only HEAD` + `git ls-files --others` against the index) caught all 24 — but the hook everyone trusted had done nothing.

## The fix

Match the shell tools as well, and after a shell call queue every **untracked** file in the repo under the same skip rules:

```json
{ "matcher": "Write|Edit|Bash|PowerShell", "hooks": [{ "type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/.claude/scripts/track-new-file.py\"" }] }
```

```python
if tool in ("Write", "Edit"):
    candidates = [project_relative(tool_input["file_path"])]
elif tool in ("Bash", "PowerShell"):
    candidates = git("ls-files", "--others", "--exclude-standard")   # ~50 ms
queue(p for p in candidates if not skipped(p) and p not in index_text)
```

`--exclude-standard` keeps build output and ignored files out; the index check keeps it idempotent; a clean tree queues nothing, so the per-call cost is one cheap git command. Tracked-but-unindexed files a script *edits* stay the backstop's job (it diffs `HEAD`), which is fine — a tracked file already had its chance at an entry.

## The rule

When a guarantee is enforced by reacting to one tool's events, list every other way the same outcome can happen (scripts, shell, generators, renames, another process) and either hook those too or make the end-of-session diff the primary check and say so. Keep the backstop even after the hook is fixed: the hook is a convenience, the diff is the guarantee.
