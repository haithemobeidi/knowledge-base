---
stack: [ui, react, jetpack-compose, typescript, kotlin]
kind: gotcha
last_verified: 2026-08-12
---

# A hold-last-value anti-flicker rule is correct within one subject and wrong across subjects

**One-liner:** "keep painting the last good value until a replacement arrives" is a legitimate anti-flicker pattern — and a bug factory the moment the *subject* changes underneath it, because a retention policy with no identity check can't tell "the same thing, momentarily valueless" from "a different thing entirely." The fix is one line: reset the held value when the identity key changes.

## The symptom

A hero band holds the last cover art it painted and only ever *replaces* it — a
deliberate rule so a game whose art is still decoding doesn't flash to blank. Then the
band's subject switches to a game with **no** cover at all: nothing arrives to replace
the held art, so the band keeps painting the *previous game's* artwork under the new
game's title, indefinitely. The retention rule worked exactly as written; it was
written without asking "last value *of what*?"

## The mechanism

Any cache keyed implicitly by *slot* ("the band's image") instead of by *subject*
("game X's image") has this hole. Within one subject, holding is right: transient
null/loading states shouldn't flash. Across subjects, holding is a lie: the old value
doesn't belong to the new subject, and the failure only shows when the new subject
legitimately produces nothing — which is why it survives testing (most subjects have
values, so replacement masks the missing reset).

## The fix

Retention policies get an identity key. On subject change: reset to the empty/
placeholder state first, *then* apply hold-last-value semantics within the new
subject's lifetime. If a blank frame at switch is unacceptable, the placeholder is
what holds — never the previous subject's value.

## The ten-second identification

Stale content under a fresh title/label is the tell. Then check the code for an
**explicit** hold/retain branch ("keep previous until next arrives"): if one exists,
it's this lesson — grep it for any mention of the subject's id; absence is the bug.
If no such branch exists and you're in a webview, it's incidental DOM/compositor
reuse instead — see
[webview2-react-render-traps.md](./webview2-react-render-traps.md) Trap 2, which has
the same symptom and the same fix-shape (identity keying via `key={id}`) but no
deliberate retention rule to point at.

## The general rule

Every "remember the last X" needs an answer to "last X **of whom**" — retention scope
must equal subject scope. This is the display-layer sibling of cache invalidation:
the policy isn't wrong, its key is missing a dimension.

## Related

- [webview2-react-render-traps.md](./webview2-react-render-traps.md) — Trap 2: the incidental-caching twin (compositor/DOM reuse, no explicit hold branch).
- [derive-dont-track-ui-flags.md](./derive-dont-track-ui-flags.md) — the adjacent family: tracked state that goes stale on the reset path someone forgot; there the cure is deriving, here it's keying.
- [keep-mounted-screens-stale-external-reads.md](./keep-mounted-screens-stale-external-reads.md) — stale-snapshot family, read-timing flavor.
