---
stack: [android, compose, kotlin, ui, theming, debugging]
kind: gotcha
last_verified: 2026-08-09
---

# Your theme sets tokens, not defaults — Compose's `LocalContentColor` falls back to **black**

**One-liner:** an app with a complete, correct dark colour scheme rendered every game title, every screen heading and every uncoloured label in **solid black on a #0E0C0E background** — invisible on every screen. The palette was fine. The cause is that `MaterialTheme` does not set `LocalContentColor`; only `Surface` does. Root your UI in a `Box` with a `background` modifier instead of a `Surface`, and the ambient text colour stays at its compositional default, which is literally `Color.Black`. It survives compilation, unit tests, and a first pass on a real device.

## The symptom

Some text renders correctly, some is invisible, and the split looks arbitrary until you line it up:

| Renders fine | Invisible |
|---|---|
| Anything passing an explicit `color = …` | Anything omitting `color` |
| Text inside `Button` / `OutlinedButton` | Screen titles, item titles |
| Text inside `Scaffold` / `Card` / `Surface` | Everything in a plain `Column` |

**The clincher that identifies it in ten seconds:** find a light-coloured background somewhere in the app — an image, a pale cover, a light card. If the "invisible" text is *perfectly legible in black* there, the text is not faded, missing, or mis-styled. It is being drawn in black on purpose.

The second tell is asymmetry between screens. If exactly one screen looks right, check what wraps it. Here the sign-in screen was the only one built on a `Scaffold`, and `Scaffold` brings a `Surface` with it — so the one correct screen in the app was correct by accident, which is also why nobody caught it earlier.

## The mechanism

Three facts, each verifiable in about a minute against the artifact you actually compile against:

1. **`LocalContentColor`'s default is `Color.Black`.** Not `Unspecified`, not "inherit" — black.
2. **`MaterialTheme` never touches it.** It provides the colour scheme, the typography and the shapes. The scheme's `onBackground` / `onSurface` are *tokens available to components*, not an ambient default for bare `Text`.
3. **`Surface` provides it**, deriving the content colour from its container colour.

So `Text("hi")` with no `color` reads `LocalContentColor`, and if nothing upstream provided one, that is black.

Verify rather than believe — decompile the exact version on your classpath:

```bash
unzip -o -q "$GRADLE_CACHE/.../material3/jars/classes.jar" 'androidx/compose/material3/*'
javap -p -c 'androidx/compose/material3/ContentColorKt$LocalContentColor$1.class' | grep Black
#   -> invokevirtual  androidx/compose/ui/graphics/Color$Companion."getBlack-0d7_KjU":()J

javap -p -c androidx/compose/material3/MaterialThemeKt.class | grep -c LocalContentColor   # -> 0
javap -p -c androidx/compose/material3/SurfaceKt.class       | grep -c LocalContentColor   # -> 4
```

That is the whole diagnosis: zero references in the theme, four in `Surface`.

## Why `Modifier.background()` is the trap

```kotlin
// Paints a colour. Declares nothing.
Box(Modifier.fillMaxSize().background(PmBgDeep)) { App() }

// Paints a colour AND declares the content colour that goes with it.
Surface(color = PmBgDeep) { App() }
```

They look equivalent in a screenshot of an empty screen, and they are not the same thing at all. `background()` is a draw instruction. `Surface` is a semantic container: colour, content colour, elevation, shape, and the ambient values that go with them.

Anyone reaching for `Box` + `background` at the app root — usually to get `Alignment.BottomCenter` for a floating nav bar, which is exactly what happened here — walks straight into it.

## The fix, and where to put it

Provide it **inside your theme wrapper**, not at the root:

```kotlin
@Composable
fun AppTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = AppColors, typography = AppType) {
        CompositionLocalProvider(LocalContentColor provides AppColors.onBackground, content = content)
    }
}
```

Root-level would fix today's bug. Theme-level fixes it for every entry point at once — the shell, sign-in, dialogs, `@Preview` — and means a future root that forgets to be a `Surface` cannot reintroduce it. Nested `Surface`s still override it normally, so nothing else changes.

## The sibling bug in the same file

While you are there: **`darkColorScheme()` fills every slot you omit with Material's own baseline palette.** An unnamed slot is not unused — it is Material's purple-tinted neutral, waiting for the first stock component that reads it. There are ~48 slots; a hand-written theme typically names 15–20.

The two that bite first, because they are what stock components actually paint with:

- **`surfaceContainerHigh`** — `AlertDialog`'s background.
- **`surfaceContainerHighest`** — `Switch`'s unchecked track.

Also set **`surfaceTint = Color.Transparent`** unless you want tonal elevation: Material blends that colour into raised surfaces to imply height, which on a hand-built dark theme washes your accent across every card.

Guard it by reflection rather than by a hand-written list, so a slot added by a future Compose release fails the build instead of silently defaulting:

```kotlin
private fun slots(scheme: ColorScheme): Map<String, Long> =
    ColorScheme::class.java.methods
        .filter { it.parameterCount == 0 && it.returnType == java.lang.Long.TYPE && it.name.startsWith("get") }
        .associate { it.name.removePrefix("get").substringBefore('-').replaceFirstChar(Char::lowercase) to it.invoke(scheme) as Long }

@Test fun `no slot is inherited from Material`() {
    val inherited = slots(AppColors).filter { (k, v) -> slots(darkColorScheme())[k] == v }.keys
    assertTrue("still Material's: $inherited", inherited.isEmpty())
}
```

**Match on return type, not on the `-0d7_KjU` name mangling.** That suffix is a hash of the value class's identity, not a contract; keying off it made the first version of this test match *nothing* and pass on an empty set. See [[negative-control-before-trusting-a-probe]] — an assertion over an empty collection is vacuously true, so pair this with a canary asserting it finds ≥40 slots.

## The general rule

**Painting a colour is not declaring a context, and a framework's implicit default may be actively hostile rather than neutral.**

A theme object that carries a complete palette invites the assumption that it has configured everything downstream reads. It hasn't — it has published tokens. What consumes those tokens is a separate mechanism, and the gap between them is where an unset ambient value sits with whatever default its author picked years ago, for a light-theme world.

The same shape recurs anywhere there is an ambient/provider system with a default:

- **React context** created with `createContext(someDefault)` — a component rendered outside the provider silently gets that default instead of erroring.
- **CSS `inherit` chains** — a value that resolves to the initial value rather than the one you set two levels up.
- **DI containers with implicit bindings**, thread-locals, request-scoped ambients.

The habit: when a default surprises you, **read the artifact you compile against** rather than the docs or your memory. One `javap`/decompile/source-jar peek settles it, and it settles it for the exact version you ship rather than for the version the blog post was written about.

## Related

- [[negative-control-before-trusting-a-probe]] — the guard test above is only a guard if it can fail; an empty set satisfies every "none of these are wrong" assertion.
- [[edge-to-edge-scrim-paints-over-your-bleed]] — the same family's other member: there the paint was a system-bar scrim over a bleed; both were debugged as structure while every structural probe answered "correct."
- [[material-tier-glassmorphism-tokens]] — the translucent-surface token system this theme sits on top of.
- [[webview2-react-render-traps]] — the same genre one platform over: framework defaults that behave differently than the environment you developed against.
