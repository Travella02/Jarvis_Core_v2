# Jarvis Core v2 — 0.1.3 Repair16 Repair2

## Scope
- Repair the test-only Core hold audio cue using a Windows-native, in-memory PCM WAV (two notes) played by `winsound` on the **Windows default audio playback device**. The renderer still displays the interrupt banner but no longer relies on an AudioContext created from the WebSocket callback on Windows. A renderer fallback is attempted if the native playback API reports failure. On non-Windows, the existing browser cue remains.
- Hold interval is **8 seconds after the cue completes**; Core remains authoritative and private audio cannot play during the hold. Cancellation and stale-result discard rules are unchanged.
- Increase the default *desktop Core/Luna delegated-voice* output budget from 256 to **1024** while preserving a larger existing generic limit. An explicit `JARVIS_DESKTOP_LUNA_VOICE_MAX_OUTPUT_TOKENS` override (128–8192) can be used for A/B comparisons. A legacy `.env` value of `JARVIS_OPENAI_VOICE_MAX_OUTPUT_TOKENS=256` does not prevent the desktop delegation increase.
- No changes to GPT-Realtime Mini output limits, its routing behavior, wake/sleep recognition, trimmed PCM, or live non-test audio.

## What logs mean
- `phase=cue_playback | state=playback_api_completed` means Windows accepted and returned from playback, **not** proof headphones were audible. If sound is not heard, verify the Windows **default** playback device/volume and run `python -m apps.desktop_cancel_cue` to troubleshoot without spending API tokens.
- `phase=interrupt_window_open | seconds=8` is the moment the full eight-second window begins. `outcome=PASS` only when a held result was discarded safely; `NOT_TESTED` if it was released at expiry.
- `[Jarvis Luna Budget] output_limit=1024` on a delegated request confirms the Core provider budget in actual use. A larger explicit override is also valid.

## Risks and limitations
- `winsound` uses the Windows default output rather than an application-specific audio sink. A disabled/muted/default-mismatched device can still make the cue inaudible; the native API cannot detect what a person hears.
- Windows native playback must be accepted live; automated tests mock `winsound`, they do not access the user's headphones.
- A larger Core output budget may increase Core API usage and response time on complex tasks. It does not affect the common direct Mini path.
- Electron production build must be checked on the user's Windows environment.

Preserve backups, existing patch files, and committed Repair15 checkpoint; do not commit this repair until live accepted.
