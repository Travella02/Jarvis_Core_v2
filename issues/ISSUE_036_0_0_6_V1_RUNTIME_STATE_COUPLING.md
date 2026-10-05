# ISSUE 036 — V1 runtime state coupling would recreate old lifecycle bugs

## Risk

The V1 reference runtime used one `CoreState` enum for sleep/wake, listening/thinking/speaking, execution/background work, degraded health, and error. Raw desktop/provider events were also mapped directly into that state machine.

Reusing that structure in v2 would make future modes fight each other. Jarvis could be awake and researching while a provider is degraded, or speaking while background work exists; those are not mutually exclusive facts.

## V1 failures reviewed

The 0.3.6 reference history also documents related failure classes:

- stale/manual Core instances causing double-start conflicts;
- status polling starving the realtime event loop;
- provider/transport timing causing visible state flicker;
- speculative wake completing so quickly that presentation skipped a meaningful lifecycle stage;
- sensitive event data reaching durable persistence sinks;
- tests inheriting private `.env` values unexpectedly.

## 0.0.6 decision

V2 keeps four independent authorities:

1. runtime lifecycle — owned by `JarvisRuntime`;
2. runtime/component health — owned by `HealthRegistry`;
3. voice presence — owned by `ContinuousVoiceSession`/`VoicePresenceState`;
4. foreground conversation activity — owned by `ConversationCore/CoreStateMachine`.

`JarvisRuntime.snapshot()` composes these truths for future clients; it does not merge them into one state enum.

Event replay is bounded and memory-only. Provider-health work is timeout-bounded and concurrent. Runtime settings expose no secrets. Provider routing is explicit and never silently changes cost/model tier.

## Acceptance

- runtime remains `running` while conversation activity changes;
- voice presence can be `awake` while activity is `listening`;
- degraded provider health does not rewrite conversation activity;
- reconnect replay reports a history gap rather than silently losing events;
- accepted 0.0.5 voice behavior remains unchanged.
