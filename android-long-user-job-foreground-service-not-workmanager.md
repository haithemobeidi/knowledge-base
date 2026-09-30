---
stack: [android, kotlin, background-work, play-store]
kind: decision
last_verified: 2026-09-19
---

# A long job the user just tapped to start: a directly started foreground service, not WorkManager's long-running worker (and Play wants a video)

**One-liner:** Playmoir's Android app runs a long "Summarize all" catch-up in the background with a progress notification and a Stop button. The mock specified WorkManager's long-running worker. Research found that on **Android 16+ a long-running worker can exhaust the app's job-runtime quota**, and Google's own guidance recommends starting the foreground service directly in that case. So the job became a `dataSync` foreground service the app starts itself at the tap. Declaring that service type then required a **Play Console declaration with a video** before release.

*Decided 2026-09-17, user-verified on a Pixel Fold (Android 17); the Play declaration was accepted 2026-09-19. The original research quotes lived in a scratch file that no longer exists; this rests on the recorded decision and the verified build.*

## The rule

- **User-initiated, long, visible now** (the user tapped "do this" and expects progress): start a foreground service directly, of the right type (`dataSync` here), and mirror the job's state into its notification with a Stop action.
- **Deferred or constraint-gated work** (run when charging, when on Wi-Fi, later): WorkManager is still the answer.

## Details that mattered

- **Notification permission:** ask `POST_NOTIFICATIONS` at the tap. If refused, the job still runs and only the progress notification is skipped. Don't block the work on it.
- **Time budget:** Android 15 gives `dataSync` services a **six-hour** budget, which arrives as `onTimeout`. Design the job to stop cleanly between units of work and resume from where it left off next time.
- **No scheduler between the tap and the run** also removed a dependency on reflection-based worker construction surviving R8 minification.

## The Play side

Declaring `FOREGROUND_SERVICE_DATA_SYNC` makes Play Console ask for a foreground-service declaration: the task type (Network processing → Other here) and **a link to a video demonstrating the feature**. It was recorded from the device over ADB and uploaded unlisted. Plan for it before the first release that adds the service type, or the submission waits on it.

## Related

- `record-and-transcribe-on-android.md`: another long-running Android job, audio.
- `play-billing-sideload-testing.md`: other Play-side requirements.
