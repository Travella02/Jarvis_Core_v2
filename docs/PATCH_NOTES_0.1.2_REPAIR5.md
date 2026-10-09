# Jarvis Core v2 0.1.2-repair5 — Conversation Trace + Long-Task Routing Precision

Repair5 preserves Repair3/4's successful pre-speech ownership boundary. It does not change the routing gate itself. This repair makes live debugging self-explanatory and fixes the background-build request that Repair4 classified as generic `action` instead of `long_task`.

## What changed

### 1. Development terminal now shows the actual conversation

When development conversation tracing is enabled, the desktop prints clearly labeled turn text alongside route/Core/latency telemetry:

```text
[USER SPEECH] turn=3 | source=voice | text="Jarvis, what planet is known as the Red Planet?"
[Jarvis Route] turn=3 | route=direct | owner=realtime | route_ms=...
[Jarvis Direct] turn=3 | realtime-only | call_id=...
[JARVIS REPLY] turn=3 | source=realtime | text="Mars."
[Desktop latency] turn=3 | ...
```

Core-owned turns use `source=core` on the final reply.

Typed text is logged directly. Wake-preserved text is labeled `source=wake_transcript`. Awake microphone speech uses Realtime input transcription only for the development trace.

### 2. Voice trace transcription is asynchronous and optional

`JARVIS_DESKTOP_CONVERSATION_TRACE=1` enables the development trace by default in the current alpha.

For awake microphone turns, the Realtime session requests `gpt-realtime-whisper` input transcription with minimal transcription delay. This ASR stream is independent from Realtime's native audio understanding and is not used to decide routing or create responses. It can be disabled without changing Jarvis behavior:

```text
JARVIS_DESKTOP_CONVERSATION_TRACE=0
```

The transcription model remains configurable with:

```text
JARVIS_REALTIME_INPUT_TRANSCRIPTION_MODEL=gpt-realtime-whisper
```

Because this is a separate provider transcription stream, it should remain development/debug observability rather than an unconditional production logging feature.

### 3. Background execution now outranks generic action routing

The router contract now distinguishes execution lifetime:

- `action`: external/device/tool work intended to execute and finish in the current interaction;
- `long_task`: durable, autonomous, queued, background, or extended work that must continue beyond the immediate interaction.

If a request is both an action and background/durable work, `long_task` wins.

So:

> “Start a background task that builds a project while I'm gone.”

should route as:

```text
route=long_task | owner=core
```

not `route=action`.

### 4. Why `action -> long_task` is not represented as a nested subtype yet

Conceptually, `action` describes **what** Jarvis is doing while `background/long-running` describes **how long/how durably** it executes. A future task system should likely model these as separate dimensions such as capability=`action` + execution=`background`.

The current 0.1.2 `DelegationMode` contract is intentionally flat and Core has distinct capability handlers for `action` and `long_task`. Repair5 therefore keeps the existing contract stable and routes durable background work directly to `long_task` instead of introducing a wider task-schema refactor inside a repair.

## V1 lesson carried forward

The included V1 0.3.6 reference treated exact transcripts and provider event ownership as first-class debugging evidence. It also kept transcription optional because transcription is a separate metered/provider operation. Repair5 follows that pattern: conversation tracing is explicit development observability and never becomes the authority for what Realtime understood.

## Automated validation

- Focused Repair5 + routing/delegation/desktop policy suite: 68 tests passed.
- Full suite: 527 tests passed, 1 existing skip.
- `python -m core.diagnostics`: `Status: ok`.
- `npm run desktop:check`: passed.
- TSX syntax transpilation check passed with the installed TypeScript compiler. Full Vite/React build remains part of live acceptance because this build environment does not contain the project's `node_modules` tree.
