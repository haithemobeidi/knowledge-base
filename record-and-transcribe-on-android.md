---
stack: [android, kotlin, audio, whisper, speech-to-text]
kind: pattern
last_verified: 2026-08-15
---

# Record + transcribe on Android: the built-in recognizer can't do it — own the mic, bring your own engine

**One-liner:** Android's `SpeechRecognizer` is a sealed live-mic-to-text box — it cannot transcribe a file you recorded and it won't share the microphone with your own `AudioRecord` (concurrent capture is OEM-lottery; one side gets silence) — so any feature that must keep the audio clip AND produce a transcript needs your own capture plus an on-device STT engine; everything below is the measured route that shipped.

## The wall (verified, not assumed)

- `SpeechRecognizer` / `RecognizerIntent` accept **no file or stream input** on any API level through 36. Dictation works precisely because the audio is discarded.
- Running your own `AudioRecord` while the recognizer listens is unreliable across OEMs — Android's concurrent-capture policy silences one party, and which one varies by device. Not shippable as a load-bearing path.
- "Built into the phone" is an illusion anyway: Google's recognizer downloads its own per-language models (hundreds of MB) into Google's apps invisibly. Third parties can't borrow them.
- **iOS contrast:** `SFSpeechURLRecognitionRequest` transcribes files natively — this entire article is Android-shaped; the iOS port of the same feature doesn't need it.

## The architecture that works

One mic capture you own, one on-device engine fed from the same bytes:

1. **Record 16kHz mono 16-bit WAV via `AudioRecord`.** This single format choice collapses three problems: it's exactly what whisper-family models and silero VAD consume (no resample), it's universally playable by every other client (a WAV plays in any webview/`MediaPlayer` — no codec/extension allowlist churn on servers or sibling apps), and the write is a 44-byte header plus raw PCM (no codec dependency). 2 minutes ≈ 3.84MB — comfortably uploadable.
2. **Engine: sherpa-onnx running whisper (base.en int8) — as the prebuilt AAR, never a self-built JNI.** Benchmarks put onnxruntime 10–50x over naive whisper.cpp CPU builds on Android, and consuming the official AAR keeps the ggml `-march=native` trap ([[march-native-ships-an-unrunnable-binary]]) out of your repo entirely. JitPack coordinates: `com.github.k2-fsa:sherpa-onnx` — but its generated POM drags in DESKTOP native jars (~100MB of linux/osx/win binaries) AND a `-jvm` jar that duplicates every class in the AAR (dex merge fails). Exclude all seven sibling artifacts. The AAR ships 4 ABIs (~120MB together); `ndk { abiFilters += "arm64-v8a" }` — every real phone since ~2017 is arm64, and a Play bundle re-adds per-device delivery at release time.

## The three landmines inside the working route

1. **sherpa's whisper SILENTLY DISCARDS audio past 30 seconds** (`offline-recognizer-whisper-impl.h` caps at 3000 mel frames and logs a warning nobody sees). On a 2-minute memo you'd transcribe a third with no error. **Segment with silero VAD first** (sherpa ships the `Vad` API; the model is a 640KB file) — feed 512-sample windows, cap `maxSpeechDuration` well under 30s (20s), decode each speech segment, join. This is correctness, not tuning.
2. **`AudioSource.VOICE_RECOGNITION` deliberately skips the OEM auto-gain**, which is why it's the right source for ASR — and why the saved clip plays back near-inaudible at normal volume ("I maxed my speaker to hear it"). Fix post-capture: measure the raw peak during recording (you want the raw value for the silence gate anyway), then peak-normalize the file to ~95% full scale, gain capped (~15x) so a silent room's noise floor never becomes hiss. Normalize AFTER the silence check reads the raw peak.
3. **Greedy decoding has no anti-repetition fallback** — whisper.cpp's entropy/temperature fallback doesn't exist in sherpa's greedy-only whisper path, so filler speech loops ("umm as is is is is is"). Guard text-side: collapse word runs of ≥3 to one (doubles like "very very" are real speech; only a looping decoder emits five), survivor keeps the first token's casing and the last's closing punctuation. Also port whisper's known silence-hallucination phrase list ("you", "thank you for watching"…) — match against the WHOLE cleaned transcript, never substring-replace.

## Model delivery

Download on first use, never bundle (~160MB re-shipped per update for users who never touch voice): individual files from a host measured to serve non-browser clients ([[bot-challenge-blocks-your-auto-updater]] — HuggingFace `resolve/` URLs and GitHub release assets both pass; a Cloudflare-bot-managed vanity host may 403 your own HTTP client). Pin byte size + sha256 per file — HF exposes sha256 in its tree API (`lfs.oid`) so you can pin without downloading. No dev-path fallback of any kind ([[dev-path-fallback-hides-missing-bundled-asset]]).

## Related

- [[march-native-ships-an-unrunnable-binary]] — why "prebuilt AAR" is a load-bearing word above.
- [[dev-path-fallback-hides-missing-bundled-asset]] — the model-delivery UX rules (missing-asset vs operation-failed need opposite UI; gate before the mic opens, not after two minutes of speech).
- [[r2-presigned-put-size-limits]] — the upload leg for the recorded clips.
