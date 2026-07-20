---
stack: [rust, tauri, tokio, threads]
kind: pattern
last_verified: 2026-07-20
---

# Generation Counter for Restartable Tasks

> How to restart an owned background task (thread, async task, or child process) without leaking the previous instance.

## The Problem

Anywhere you have a "service" that can be started, stopped, and re-started:

- A polling thread that watches the filesystem / processes / events
- An async task draining a stream
- A child process you spawned and communicate with over stdio
- Anything that holds resources and runs in a loop

…you eventually hit a race. Common triggers:

- **React StrictMode** double-mounts a component → fires `start` twice in quick succession → two threads now own the same job, double-emitting events.
- **A stop-start sequence races** the sleeping loop: stop runs, but the old thread is mid-sleep; start spawns a new thread; old thread wakes up, sees `running == true` (the new thread set it), keeps running. Now you have two.
- **A child-process crash plus restart**: the old reader task is still draining stdout when you spawn the replacement; its in-flight messages get attributed to the new generation.

`Arc<AtomicBool>` for a `running` flag is not enough — it can't distinguish "I'm the current generation" from "someone bumped me into stale territory."

## The Pattern

Use an `AtomicU32` generation counter alongside the running flag. Each spawned task captures the counter value **at spawn time**, then exits the moment the counter advances past it.

```rust
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::Arc;

pub struct ServiceState {
    pub running: Arc<AtomicBool>,
    pub generation: Arc<AtomicU32>,
}

impl Default for ServiceState {
    fn default() -> Self {
        Self {
            running: Arc::new(AtomicBool::new(false)),
            generation: Arc::new(AtomicU32::new(0)),
        }
    }
}

pub fn start(state: &ServiceState) {
    // Bump the counter. Any thread spawned by a previous start sees its
    // captured generation no longer matches and exits on its next tick.
    let my_generation = state.generation.fetch_add(1, Ordering::SeqCst) + 1;
    let running = state.running.clone();
    let generation = state.generation.clone();
    running.store(true, Ordering::SeqCst);

    std::thread::spawn(move || {
        while running.load(Ordering::SeqCst)
            && generation.load(Ordering::SeqCst) == my_generation
        {
            // ... do work ...
            std::thread::sleep(std::time::Duration::from_secs(3));
        }
        eprintln!("[service] gen={} loop exited", my_generation);
    });
}

pub fn stop(state: &ServiceState) {
    // Stop sets `running = false` only. It does NOT bump the generation.
    // Generation bumps are reserved for `start` so that a late-arriving
    // stop (from a cleanup race) can't kill the surviving thread of a
    // newer start.
    state.running.store(false, Ordering::SeqCst);
}
```

## Why It Works

- **Stale tasks self-exit at their next loop tick.** No `JoinHandle.abort()` plumbing, no cancel tokens to pass around — the task just checks two atomics and returns naturally when its generation is no longer current.
- **The newest task always wins.** `fetch_add` is atomic; only one task can hold any given generation number.
- **Start asymmetry is intentional.** Only `start` bumps the generation. If `stop` bumped it too, the sequence `stop1 → start2 → stop1's-late-cleanup` would kill `start2`'s thread.
- **No locks on the hot path.** Atomics + clone-the-Arc is essentially free per iteration.

## Tuning the Tick Interval

The task exits within one loop iteration of the generation bump. If your iterations take 3 seconds (filesystem polling), worst-case stale-task lifetime is 3 seconds. That's usually fine. If you need faster exit, either:

- Shorten the sleep (cheap if the work itself is cheap)
- Sleep in shorter intervals with the check between them
- Use `tokio::select!` with a watch channel for sub-second responsiveness (overkill for most cases)

## Variant: Async Tasks (tokio)

Same idea, swap thread for `tokio::spawn`:

```rust
let my_generation = state.generation.fetch_add(1, Ordering::SeqCst) + 1;
let running = state.running.clone();
let generation = state.generation.clone();

tokio::spawn(async move {
    while running.load(Ordering::SeqCst)
        && generation.load(Ordering::SeqCst) == my_generation
    {
        // ... await something ...
        tokio::time::sleep(Duration::from_secs(3)).await;
    }
});
```

## Variant: Child Process with Stdio Reader

The generation counter solves the "stale reader" half of the problem. For child processes you also need to (a) reap the child on stop, and (b) wire reader/writer tasks to the same generation. Sketch:

```rust
pub struct SidecarState {
    pub child: Arc<tokio::sync::Mutex<Option<tokio::process::Child>>>,
    pub generation: Arc<AtomicU32>,
}

pub async fn spawn_sidecar(state: &SidecarState) -> Result<(), Error> {
    let my_generation = state.generation.fetch_add(1, Ordering::SeqCst) + 1;
    let mut child = tokio::process::Command::new("node")
        .arg("sidecar.cjs")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;

    let stdout = child.stdout.take().unwrap();
    let generation = state.generation.clone();

    tokio::spawn(async move {
        let mut reader = tokio::io::BufReader::new(stdout).lines();
        while generation.load(Ordering::SeqCst) == my_generation {
            match reader.next_line().await {
                Ok(Some(line)) => { /* parse, dispatch */ },
                Ok(None) => break,           // child closed stdout
                Err(_) => break,
            }
        }
        // Either child died, or we're a stale generation. Exit.
    });

    *state.child.lock().await = Some(child);
    Ok(())
}
```

On restart: bump the generation, kill the old `Child`, spawn a new one. The old reader task notices its generation is stale at its next `next_line().await` return and exits without writing to whatever shared channel feeds the rest of the app.

## What This Pattern Does NOT Solve

- **Reaping the process / freeing the resource.** You still need to call `child.kill()` (or equivalent) explicitly. Generation counter just makes the **observers** exit cleanly.
- **Ordering of "I'm dead" signals.** If your app needs to know which generation a "child exited" event came from, attach the generation number to the event payload.
- **Replay during restart.** Messages emitted by gen N after gen N+1 has started will be ignored. If you need to drain a queue before stopping, do it explicitly in stop.

## When NOT to Use This

- **One-shot tasks.** If the task runs once and exits, no generation counter needed.
- **Tasks you'd never restart.** If the only lifecycle is start-once-at-app-launch and stop-at-app-exit, an `AtomicBool` plus a `JoinHandle.abort()` is simpler.
- **Tasks where stale output is harmless.** Rare, but: if the task only emits idempotent events to a UI that doesn't care about duplicates, you can skip the ceremony.

## Related pattern: debounce a flickering liveness signal (different problem, same file)

The generation counter above solves *stale-instance cleanup on restart* — it does nothing for the opposite failure: a process-liveness poll that misreads a **momentary gap** in an otherwise-live signal as "the process stopped," when what's actually happening is a handoff between two processes (a launcher/bootstrapper exiting a beat before the real long-running process appears).

Concrete case: a game-process watcher polling "is any tracked exe still running" fired its `game_stopped` event (which drove a whole quit-ritual flow) on the very **first** poll where the watched exe was momentarily absent — which happened on *launch*, not quit, for any game whose launcher process exits and hands off to the real game exe a beat later (common with repacks, DRM wrappers, and anti-cheat self-relaunch). One missed poll, read as ground truth, fired a user-facing flow at exactly the wrong moment.

**Fix: an N-consecutive-miss counter, reset on any live sighting.**

```rust
struct Session {
    missed_polls: u32,
    // ...
}

const STOP_GRACE_POLLS: u32 = 4; // ~12s at a 3s poll interval

// each poll tick:
if exe_is_running {
    session.missed_polls = 0;
} else {
    session.missed_polls += 1;
    if session.missed_polls >= STOP_GRACE_POLLS {
        fire_game_stopped();
    }
}
```

Tune the grace window to comfortably exceed the real handoff gap you're protecting against (here, ~12s covered every observed launcher-to-game handoff), not to an arbitrary round number — too short and the false positive survives, too long and a genuine quick-exit takes longer to register.

**Generalizes beyond games:** any OS-process-lifecycle watcher that treats "process absent on this poll" as ground truth needs this — dev-server auto-restart detectors, wrapper/launcher-process patterns, health-check pollers watching a process that legitimately restarts itself. The tell that you need it: your "stopped" event fires occasionally on **launch**, not just on genuine stop.

## Origin

The pattern was extracted from Checkpoint's `apps/desktop/src-tauri/src/commands/process_watch.rs` (lines 88-368). That project hit it via React StrictMode double-mounting a hotkey-armed monitor in dev mode; the same atomic counter killed both that bug and a stop/start race in prod.

LLM Hub (sister project) adopted the same pattern for its Node sidecar's reader-task lifecycle when the sidecar crashes and gets restarted with exponential backoff. Same primitives, different application surface.

## Reference

- Original implementation: `Checkpoint/apps/desktop/src-tauri/src/commands/process_watch.rs`, MonitorState struct (line 356) and the start/stop pair around lines 88-338.
- Rust atomics docs: <https://doc.rust-lang.org/std/sync/atomic/>
