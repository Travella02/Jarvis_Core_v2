# 0.1.2 Repair6 — Parallel Intelligence Shadow Probe (Phase 1)

**EXPERIMENTAL.** This is a safe instrumentation step toward concurrent routing, Realtime generation, and Luna thinking. It DOES NOT yet play buffered speculative speech or shorten first-audio latency. The existing Repair5 silent gate and single-authority answers are unchanged.

## Why this stage exists

The active desktop Realtime connection uses WebRTC with one remote audio track. Sending a second audio response and simply toggling mute risks the exact premature-speech/duplicate-answer problems that Repairs1–3 solved. Before designing an isolated PCM stream/buffer, we need actual measurements of overlapping model requests, speech-to-transcript delay and cancellation behavior on the installed desktop.

## Changes

- `JARVIS_PARALLEL_SHADOW_PROBE=0` (default). Explicit opt-in only; do not enable in production.
- While the normal gate routes, one independent **out-of-band, text-only**, no-tools Realtime candidate is requested. It cannot speak, affect captions or write to the default Realtime conversation. A response-specific cancellation occurs when ownership is decided.
- When a final user transcript arrives before the gate settles, a small **stateless, read-only** Luna candidate starts over a separate HTTP provider. Its output is never shown, acted on, stored, or used for user-facing authority; it is canceled at the route decision. No Memory/Action/LongTask tools are used.
- Logs include transcript delay, Realtime speculative first-token time, Luna speculative first-token time, candidate elapsed duration, provider usage and whether transcript arrived too late.
- Existing Repair5 response generation, real Core delegation, speech captions, interruption, permissions and history remain authoritative and unchanged.

## Live acceptance criteria

1. With flag OFF: old Repair5 results unchanged, with no `[Jarvis Parallel]` logs and no new cloud calls.
2. With flag ON: for each turn there is exactly one **audible** reply, and no speculative text appears onscreen. `[Jarvis Parallel]` logs expose overlap/timing. Negative/later ASR timings are data, not failure.
3. Interrupt/cancel/sleep/new-turn all stop stale candidates; an unseen speculative answer must never leak audio, text, memory, actions, or content into future turns.
4. This probe's timing cannot prove an audio 500ms first-word target. Next phase requires a separate verifiably isolated, truly buffered audio stream and exact ownership promotion or rejection.

## V1 comparison

V1 0.3.6 reference keeps cloud sideband and Realtime session lifecycle under explicit app/backend authority. Repair6 likewise keeps response ownership in the app, not in model-generated narration. Speculative work never controls actions or user-visible audio.

## Privacy and cost

Enabling the probe incurs extra Realtime text output and potentially extra Luna inference. Accepted STT transcript is sent to the independent Luna provider. Do not leave opt-in enabled in production. The probe is deliberately capped to 96 output tokens and a 3-second per-turn deadline for Luna; cancellation reduces but cannot retroactively refund generated tokens.
