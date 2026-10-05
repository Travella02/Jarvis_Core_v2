# Jarvis Core v2 0.0.6 — Runtime State & Event Foundation

## Summary

0.0.6 moves the accepted 0.0.5 voice/conversation path under a central Jarvis runtime host without changing the accepted speech pipeline. The runtime now owns process lifecycle, non-secret runtime settings, explicit intelligence-provider routing, health projection, the shared EventBus, reconnect snapshots, and trace replay.

The accepted voice path remains:

`Silero speech presence -> whisper.cpp STT -> Conversation Core -> GPT-6 Luna -> whole-response local Qwen3-TTS`

No tools, memory, UI, autonomous jobs, or new working/researching/error product modes are added here.

## V1 reference review before implementation

The read-only 0.3.6 V1 checkpoint was inspected before this patch. 0.0.6 deliberately preserves useful behavior while avoiding several V1 coupling patterns:

- V1's `CoreState` mixed sleeping/waking, foreground conversation, execution, background work, degraded health, and error into one enum. V2 keeps runtime lifecycle, runtime health, voice presence, and Conversation Core activity as separate axes.
- V1's `RealtimeRuntime` translated raw desktop/provider event names directly into authoritative Core state. V2 runtime never treats provider/transport events as conversation truth; Conversation Core and VoicePresenceState keep their existing authorities.
- V1 eventually required durable-event redaction fixes because operational events reached persistence sinks. 0.0.6 event replay is memory-only and bounded; a durable journal is intentionally deferred until a dedicated redacted persistence boundary exists.
- V1 had stale/double runtime and event-loop starvation failures. 0.0.6 runtime lifecycle is idempotent, reconnect state is snapshot/cursor based, and provider-health probes run concurrently with bounded timeouts instead of blocking runtime state reads.
- V1 test environments could inherit private `.env` values unexpectedly. 0.0.6 runtime settings do not silently read the project `.env`; callers must explicitly provide an env file, and explicit environment mappings are deterministic.

The V1 code is reference-only and is not imported by v2.

## Added

### Central runtime host

`core/runtime/JarvisRuntime` now owns:

- runtime lifecycle: `stopped -> starting -> running -> stopping -> stopped`;
- the shared authoritative in-process EventBus;
- one active Conversation Core instance;
- runtime settings projection;
- intelligence provider router;
- provider/component health projection;
- reconnect snapshots and event replay.

Runtime lifecycle is intentionally separate from:

- voice presence (`sleeping` / `awake`);
- Conversation Core activity (`listening`, `thinking`, `speaking`, etc.);
- component/provider health.

### Event cursors and trace replay

`CoreEvent` now receives a monotonically increasing in-process sequence number. `EventBus` adds:

- `latest_sequence`;
- `oldest_sequence`;
- `events_after(sequence)`;
- `events_for_correlation(correlation_id)`.

A reconnecting client can take a runtime snapshot, remember its cursor, and later request only newer events. If its cursor is older than the retained bounded history, `JarvisRuntime.events_after()` reports `gap_detected=True` instead of silently pretending the replay is complete.

### Explicit provider router

`IntelligenceProviderRouter` registers named provider routes and selects them explicitly. It does not silently:

- switch providers;
- escalate to a stronger model;
- switch service tiers;
- fall back to a more expensive route.

This preserves manual/cost control while creating the routing boundary needed for later policy-driven escalation.

### Runtime health

`HealthRegistry` tracks component health separately from lifecycle/activity state. Provider health probes:

- are bounded by a configured timeout;
- run concurrently;
- convert adapter exceptions into safe exception-type diagnostics;
- do not hold runtime/provider-router locks while awaiting provider code.

### Runtime settings

`RuntimeSettings` centralizes only non-secret orchestration settings:

- environment name;
- default intelligence route;
- bounded event history size;
- provider-health timeout.

Credentials remain provider-owned and are not included in runtime snapshots.

### Voice Lab runtime wiring

Normal Voice Lab sessions now create Conversation Core through `JarvisRuntime` and share the runtime EventBus. The accepted 0.0.5 wake/sleep/interruption path is otherwise unchanged.

### Runtime Lab

`python -m apps.runtime_lab` provides a no-network/no-audio diagnostic that verifies:

- runtime lifecycle;
- provider health;
- Conversation Core creation;
- one deterministic turn;
- reconnect cursor replay;
- correlation trace replay.

## Deferred

- network/local HTTP or WebSocket API transport;
- desktop UI process supervision;
- durable event journal;
- automatic provider/model escalation;
- tool execution gateway;
- memory/task persistence;
- production AEC/noise suppression;
- fuzzy/phonetic wake-word correction such as `Jervis -> Jarvis`.

## Automated validation

Focused runtime foundation tests plus the full project suite are required before live acceptance. See `docs/TESTING_GUIDE_0.0.6.md`.
