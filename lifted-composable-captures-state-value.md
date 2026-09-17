---
stack: [android, compose, navigation-compose, kotlin]
kind: gotcha
last_verified: 2026-09-16
---

# Lifting composables out of a scope turns a live delegate read into a captured value — NavHost builds its graph once, so pushed screens rendered launch-time state

**One-liner:** Inside a nav host, `val state by viewModel.state.collectAsStateWithLifecycle()` is read *inside each destination's content lambda*, at that destination's own composition, so every screen sees the live value. Move those destinations into a helper (`fun NavGraphBuilder.pushedDestinations(state: AppState, …)`) and pass `state` as a parameter, and the helper receives a **value**, captured when the builder ran. `NavHost` remembers its graph — the builder lambda runs once — so every lifted screen renders the app state from launch, forever. A mechanical, "no behaviour change" split changed behaviour.

## How it showed

Playmoir Android, 2026-09-16: the nav host was split at the 500-line cap, four pushed screens (a game's pinned Memoir, the entry reader, the write form, a new list) moved to their own file with `state` passed in. Unit tests green, the mixed timeline tab (still in the host) fresh, the game page (reads the ViewModel itself) fresh — and the pinned Memoir said "Nothing written down yet" for a game with two notes saved minutes earlier. The user caught it; the reader and the write form had the same rot, just less visibly (stale carry-forward, stale entries).

## The fix

Never pass the value into a lifted destination. Pass the **source** and read it at the destination's composition:

```kotlin
composable(Routes.GAME_MEMOIR) { entry ->
    val state by viewModel.state.collectAsStateWithLifecycle()   // here, not in the builder
    MemoirScreen(state = state, …)
}
```

Same rule for anything read at build time: a `var flightActive by remember { … }` became `flightActive: () -> Boolean`, a lambda evaluated at composition, for the same reason.

## The rule

When you lift code out of a scope, list every name it reads and ask *when* each is evaluated after the move. A `by` delegate, a `State`, a flow, a `remember`ed var — these are live where they were read and dead the moment they cross a plain parameter into something that runs once. Pass delegates, flows or lambdas across that boundary; pass values only into things that recompose with them. And test the moved screens against a change made *after* launch, not just that they render.
