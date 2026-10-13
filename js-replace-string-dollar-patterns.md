---
stack: [javascript, node, tooling]
kind: gotcha
last_verified: 2026-10-02
---

# A scripted find-and-replace in JavaScript eats `$`: the replacement STRING is a pattern language

**One-liner:** in `str.replace(x, replacement)`, a replacement *string* interprets `$$` (one `$`), `$&` (the match), `` $` `` and `$'` (before/after the match) and `$1`… So a codemod that pastes code containing `$$(` writes `$(`. It passed a syntax check and broke at run time. Use a **function** replacer, or `split`/`join`.

*Playmoir, 2026-10-02 (a script editing the landing page's code).*

```js
// Wrong: any `$$`, `$&`, `$'` inside newCode is rewritten.
src = src.replace(oldCode, newCode);
// Right: a function's return value is inserted literally.
src = src.replace(oldCode, () => newCode);
// Also right, for every occurrence:
src = src.split(oldCode).join(newCode);
```

The same applies to `replaceAll`. Python's `str.replace` has no such patterns; `re.sub`'s replacement does (`\1`, `\g<name>`), so use a function there too.
