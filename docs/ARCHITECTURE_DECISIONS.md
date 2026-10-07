# Jarvis Core v2 Architecture Decisions

## Status

Canonical foundation decisions for **0.0.1 - Foundation**. The project-root master handoff PDF remains authoritative if this summary and the PDF ever conflict.

## ADR-001 — Clean rebuild; V1 stays read-only

Jarvis Core v2 is a clean repository architecture. The existing `Jarvis_Real_Time` project and supplied V1 checkpoint are fallback/reference only. Reuse must be deliberate at the behavior, test, semantic, or isolated-implementation level; V1 architecture is not copied wholesale.

## ADR-002 — Intelligence is provider-independent

Core code depends on `IntelligenceProvider`, not a provider SDK. GPT-5.6 Luna is the initial everyday cloud model planned for 0.0.2 through an `OpenAIProvider`. Stronger cloud-model escalation is policy-driven. Future local/offline intelligence is an optional provider, not a launch dependency.

Provider/model names, endpoints, context limits, pricing, snapshots, and rate limits are configuration concerns. OpenAI-specific response/tool schemas must remain inside the OpenAI adapter.

## ADR-003 — ORVEX owns realtime voice orchestration

ORVEX Core owns streaming audio flow, VAD/endpointing, interruption/barge-in, cancellation, AEC/noise handling, turn state, and STT/TTS routing. Concrete STT/TTS engines remain replaceable adapters. 0.0.1 defines only provider-neutral speech/audio contracts; realtime behavior is intentionally deferred.

## ADR-004 — Tool authority remains outside intelligence providers

A model/provider can see `ToolDefinition` metadata and propose a typed `ToolRequest`. It never receives an executor/callback or direct machine/account authority. Permission checks, confirmations, execution, verification, auditing, safe retry, and idempotency belong to Jarvis Core.

Reasoning level/model strength never changes authority.

## ADR-005 — One authoritative conversation/context system

Typed input, voice input, providers, tools, tasks, and UI will converge on one authoritative conversation/context system. Provider switching must not reset personality, memory, referents, pending approvals, or task state. The concrete `ConversationContext`, referent resolver, and event/state machine are reserved for 0.0.3.

## ADR-006 — Correlation and cancellation cross boundaries

Provider/tool/voice contracts carry opaque trace IDs and a provider-neutral cancellation token. These are primitives only; 0.0.1 does not implement conversation lifecycle semantics.

## ADR-007 — Foundation has no runtime provider dependencies

0.0.1 uses the Python standard library only. It performs no model requests, audio capture, OS actions, account actions, or network calls. This makes architecture coupling visible before provider/runtime work begins.

## ADR-008 — Acceptance gates normal version advancement

Every candidate follows patch ZIP → root-safe apply → automated tests → focused live acceptance → same-version repair suffix if needed → exact cleanup → final verification → one focused commit. The next normal version does not begin until acceptance/commit unless explicitly overridden by Tanner.

## ADR-009 — OpenAI is an adapter, not Jarvis Core

0.0.2 implements `OpenAIProvider` under `providers/intelligence/openai/`. OpenAI SDK imports and Responses API schemas are allowed only inside that adapter package. `core/`, integrations, backend, and apps consume provider-neutral contracts or the provider class itself; they do not import the OpenAI SDK.

The initial development default is `gpt-5.6-luna`, but the model ID is provider configuration rather than a Core constant. A future cloud provider or `LocalProvider` must be able to satisfy the same `IntelligenceProvider` contract without rewriting conversation state, tools, permissions, or voice.

## ADR-010 — Responses streaming is the 0.0.2 provider path

`OpenAIProvider` uses the Responses API with streaming enabled. Provider-specific text delta, completion, error, and function-call events are translated into `IntelligenceEvent` values. Function calls become typed, non-executable `ToolRequest` intent objects; they are never invoked by the provider.

Responses are sent with `store=False` in 0.0.2. The candidate also applies a configurable 4096-token request output cap for development safety while retaining the model's actual context/output capabilities in provider metadata.

## ADR-011 — Reasoning names remain provider-neutral at the Core boundary

Core sends `ReasoningPolicy` names such as `quick`, `standard`, `high`, and `extreme`. The OpenAI adapter maps these to provider-specific reasoning effort values. Full policy routing, escalation, usage budgets, and fallback remain reserved for 0.0.6.

## ADR-012 — Provider promotion requires a Jarvis benchmark

0.0.2 seeds a provider-neutral benchmark harness and corpus. It includes an exact streaming smoke case, a provider function-call case, and the V1 natural-phrasing regression **“Can you open a new tab, please?”**. Later milestones expand the same harness with context/referent resolution, permissions, recovery, latency, interruption, and capability parity cases.

## ADR-013 — SDK version is pinned per accepted candidate

The 0.0.2 candidate pins the OpenAI Python SDK to `3.13.0` in project dependency configuration. SDK upgrades are explicit project changes with tests, rather than silent environment drift.

## ADR-014 — 0.0.2 cancellation is cooperative stream cancellation, not a remote-inference guarantee

**Decision:** `IntelligenceProvider.cancel(request_id)` in 0.0.2 must immediately stop provider output from reaching Core, close the foreground stream, and emit `CANCELLED`. The OpenAI adapter does not claim that closing a foreground SSE stream is equivalent to the background Responses cancellation endpoint.

**Why:** the provider abstraction needs cancellation now, while the realtime voice milestone will require measured barge-in latency/cost behavior and may justify a different transport. Faking stronger semantics now would be worse than recording the boundary explicitly.

**Consequence:** 0.0.4 must include a live cancellation/interrupt benchmark before choosing the long-term cloud transport for voice-driven turns.

## ADR-015 - ConversationContext is authoritative; providers receive snapshots

0.0.3 introduces one `ConversationContext` owned by Core. Typed input, future voice input, media/task/tool/UI subsystems, and provider switching must update/read this context rather than keeping competing conversational truth. `IntelligenceProvider` receives a provider-neutral snapshot containing recent transcript and context metadata; it never owns or mutates authoritative state.

The context has explicit slots for current focus, last discussed entity, recent referents, active media/task/job, last tool action, pending approval, visible UI focus, temporal context, working-memory summary, recent transcript, and response-exposure state. The snapshot contract is serializable so later persistence/UI restart work does not require replacing the model.

## ADR-016 - Referent resolution is deterministic and clarification-safe

Resolution priority is: **explicit wording -> current conversational focus -> last discussed entity -> a single compatible context candidate**. If multiple materially plausible candidates remain, Core returns `AMBIGUOUS` and the caller must ask a short clarification instead of letting media/tasks/browser race.

This directly captures the V1 regression where `resume it` resumed YouTube even though the conversation was about a task. A focused task wins over stale media state; an explicit `resume the YouTube video` still wins over task focus.

## ADR-017 - Core owns state/event identity

0.0.3 defines the canonical states from the master handoff and an in-process event bus. Events carry event IDs, UTC timestamps, origin, correlation/request/turn/cancellation trace IDs, conversation/user/device/task identifiers where available, optional parent-event links, and structured payloads.

The bus is intentionally in-process and bounded in 0.0.3. Durable event transport is not implied. State meaning is centralized now so later voice/UI/tools subscribe to the same semantics.

## ADR-018 - Every foreground turn has a targetable cancellation ID

Conversation Core creates correlation, request, turn, and cancellation IDs before provider routing. `CancellationRegistry` maps the cancellation ID to the same provider-neutral token passed into `IntelligenceProvider`. Explicit cancellation can therefore target exactly one active turn and also call the provider's cancellation boundary.

Cancelled turns may preserve partial response text that was already exposed, but pending provider tool requests do not become active referents or executed actions. Durable/background task cancellation remains a later subsystem.

## ADR-019 - 0.0.3 typed lab is the first shared-context end-to-end path

`apps.conversation_lab` is a development shell, not the final desktop UI. Multiple typed turns flow through one `ConversationCore` and one `ConversationContext`, then through the existing provider abstraction. This proves provider switching/context ownership boundaries before realtime voice is introduced in 0.0.4.

## ADR-020 — 0.0.4 starts local-first voice with replaceable candidate adapters

The first Voice Lab candidates are **whisper.cpp + `large-v3-turbo-q5_0`** for STT and **Chatterbox Turbo** for TTS. These are candidates, not permanent architectural dependencies. `ConversationCore` and `core/voice/` do not import either implementation. Swapping STT or TTS is a `VoiceProviderRegistry` change behind `SpeechToTextProvider` / `TextToSpeechProvider`.

The default product direction is local STT + cloud intelligence + local TTS so ordinary speech does not incur recurring STT/TTS API charges. Optional hosted speech providers can be added later without becoming launch dependencies.

## ADR-021 — ORVEX owns the voice loop, not the speech models

ORVEX owns audio capture/output, audio frame format, VAD, endpointing, text chunking, playback accounting, interruption/cancellation semantics, and latency telemetry. Speech adapters only transcribe audio or synthesize speech. This boundary is intended to survive provider/model replacement years later.

0.0.4 is a Voice Lab milestone, not the final full-duplex engine. It endpoints one user utterance and then plays the streamed/chunked response. The interruption API and provider cancellation plumbing are established now; simultaneous mic + speaker operation, AEC/noise handling, reliable barge-in, and precise heard/unheard text alignment remain 0.0.5.

## ADR-022 — Heavy local speech runtimes stay out of Jarvis Core's Python environment

Whisper native binaries/model files and Chatterbox/PyTorch/model weights live under ignored `.runtime/voice/` directories. Chatterbox runs as an isolated JSON-line sidecar with its own virtual environment. This prevents PyTorch/provider dependency pins from contaminating Core and makes replacement/uninstallation bounded to one adapter runtime.

The current Chatterbox 0.1.7 package pins PyTorch 2.6 on Python 3.11, while RTX 50-series support requires newer CUDA-capable PyTorch. The supplied setup script therefore offers an isolated `modern-cuda` compatibility profile instead of changing Jarvis Core dependencies.

## ADR-023 — Product voice quality will be a downloadable package choice, not a separate Jarvis app

Future installers may recommend High Accuracy / Lightweight voice packages based on hardware, but users retain the choice. Jarvis remains one application. Model assets can be downloaded/replaced independently. Hardware detection is advisory, not an irreversible automatic quality decision.


## ADR-023 — Everyday Luna uses the fastest reasoning path

The current Jarvis default is provider-neutral `ReasoningPolicy(level="none", allow_escalation=False)`. OpenAIProvider maps that to Luna's lowest reasoning effort. Explicit higher reasoning levels remain test/development capabilities, but are not the ordinary product path. Future complex-task escalation should route through the provider/model policy layer (for example to Sol) rather than silently making everyday Luna turns slower. Tool authority remains unchanged regardless of model strength.

## ADR-024 — Voice response generation is a pipelined Core concern

Voice response streaming is split into independent model-delta, speech-chunk, TTS synthesis, and audio-playback stages. The opening speech chunk is deliberately smaller than later chunks to reduce time-to-first-audio. TTS synthesis can run ahead while already-synthesized audio is playing, and the physical output stream remains continuous for the response. Concrete TTS implementations remain behind `TextToSpeechProvider`.

## ADR-025 — Spoken text is normalized separately from display text

Conversation Core retains the authoritative provider response verbatim for transcript/display semantics. Before synthesis, the ORVEX Voice Engine applies deterministic provider-neutral speech normalization (for example stripping markdown emphasis/link syntax). Rich semantic verbalization of URLs, money, dates, code, and symbols can evolve behind the same boundary without coupling Conversation Core to a TTS vendor.

## 0.0.4-repair9 — Prosody beats artificial micro-chunking

Core must not split ordinary TTS text in the middle of a semantic clause merely to shave first-chunk latency. Providers such as Chatterbox treat each synthesis call as an utterance, so artificial chunk boundaries can reset prosody and introduce silence. Jarvis prefers complete sentence boundaries, asks the intelligence layer for a short complete opening sentence, and retains only a hard emergency cap for malformed/run-on output.

Voice latency must be evaluated in a warm multi-turn process as well as cold start. Provider/model processes and HTTP clients are intended to remain resident in the real application.

## ADR-026 — Desktop TTS winner does not dictate the mobile runtime

0.0.4-repair11 adds Qwen3-TTS 0.6B Base as a second local `TextToSpeechProvider`
for A/B testing against Chatterbox. It does not replace Chatterbox and it does
not make Qwen a Core dependency.

Desktop and mobile may select different concrete TTS runtimes while sharing the
same ORVEX voice contracts and `VoiceProfile` semantics. The full official
Qwen3-TTS Python model is appropriate for the current RTX development test, but
mobile deployment must be proven separately with a native/quantized runtime or
a lighter provider. Jarvis must not force a multi-gigabyte desktop PyTorch stack
onto phones simply to keep provider names identical.

The product preference remains local TTS when hardware permits. If a future
mobile Qwen runtime meets latency, thermal, storage, cloning, and quality goals,
it can satisfy the same provider contract. Otherwise mobile can use a smaller
local TTS or an optional paired/cloud provider without changing Conversation
Core.

## Voice reference persistence (0.0.4-repair12)

Named voice references are provider-neutral runtime user data. They live under ignored `.runtime/voice/references/` and resolve to Core `VoiceProfile` objects. Provider adapters may consume the selected reference but may not define the persistence format. One profile may contain multiple reference clips so voice enrollment can improve later without breaking profile identity.


## ADR-027 — The official Jarvis voice is a provider-independent ORVEX brand identity

Jarvis must have one canonical default voice that is recognizable as Jarvis across desktop, mobile, and future runtimes. The voice identity sits above the concrete TTS engine. Qwen, Chatterbox, a native mobile runtime, or a future provider may render that identity, but none of those provider names define the brand voice.

The canonical Jarvis voice will be an ORVEX-owned/versioned system voice asset with explicit commercial synthetic-voice rights. User-selected alternatives and personal/custom clones remain optional `VoiceProfile` choices and must not overwrite the official system identity. A runtime may ship as the default Jarvis renderer only after ORVEX listening/similarity acceptance against the canonical voice.

## ADR-028 — Qwen clone failures must be isolated with an upstream-equivalent diagnostic

When Qwen Base cloning fails, Voice Lab must separate four possible causes: reference-audio quality, reference transcript/ICL conditioning, the official Qwen generation path, and Jarvis's cached/optimized adapter path. `--qwen-clone-diagnostic` validates the saved clip and runs direct full-reference and x-vector-only `generate_voice_clone` calls without Jarvis chunking, prompt caching, or speaker playback.

This diagnostic is intentionally not a production synthesis path. It exists to prevent repeated playback/audio fixes from masking a model/runtime/reference failure.

## ADR-029 — Qwen live synthesis defaults to x-vector cloning until full-reference conditioning is separately accepted

Live 0.0.4-repair16 A/B diagnostics proved the Qwen3-TTS 0.6B Base runtime, saved reference WAV, CUDA path, waveform serialization, and speaker path are capable of producing clean speech in x-vector-only mode. The same reference produced a runaway transcript-conditioned full clone (~163.8 seconds of garbage for a short diagnostic sentence) while x-vector-only produced a normal ~4.08-second sentence.

Normal Jarvis Qwen synthesis therefore defaults to x-vector cloning even when a VoiceProfile stores an exact transcript. Transcript metadata remains valuable for enrollment, diagnostics, future provider adaptations, and a later full-reference re-evaluation, but it does not automatically enable the unstable Qwen ICL/full-reference path. Full-reference conditioning is diagnostic/experimental until it passes an explicit ORVEX quality and bounded-duration acceptance test.

This decision is provider-specific. `VoiceProfile` and the canonical Jarvis voice identity remain provider-neutral. If Qwen becomes the default renderer, the canonical ORVEX Jarvis voice can use the stable x-vector path while other runtimes implement the same voice identity through their own accepted mechanism.

## 0.0.4-repair18: latency is measured per boundary, not guessed

- GPT-5.6 Luna remains the normal everyday intelligence provider at `reasoning=none`.
- Voice-specific output limits are provider-owned latency controls; they do not change the provider-neutral IntelligenceProvider contract.
- Conversation Core remains authoritative. Prompt caching and connection warmups are optimization hints only and must never become conversation truth.
- OpenAI Fast mode is an optional provider setting for A/B latency testing, not the default, because it can carry a pricing premium.
- Local TTS model health is not considered fully warm. Voice Lab may run and discard one tiny synthesis before listening so model/CUDA/prompt-cache cold-start work occurs outside the user's turn.
- Qwen remains provider-swappable. Repair18 does not introduce a third-party streaming fork into the product runtime; true incremental Qwen audio should only be adopted after its dependency/runtime is explicitly accepted.

## 2026-09-25 — Voice transport continuation remains subordinate to Conversation Core

Voice may use a persistent provider transport such as OpenAI Responses WebSocket mode, but provider-side continuation is only a latency cache. Conversation Core remains authoritative. A provider may send incremental input with a prior response ID only when the current Core snapshot exactly extends the previously completed provider turn; otherwise it must reset and send full context. Transport state can always be discarded without losing Jarvis conversation truth.


## ADR-030 — Presence lifecycle is separate from future activity/status modes

0.0.5 introduces a `VoicePresenceState` with only `sleeping` and `awake`. It is not a replacement for Conversation Core foreground activity and must not become the bucket for future modes such as working, researching, thinking, waiting, authenticating, or error. Those can later coexist with an awake Jarvis. This separation prevents wake/sleep policy from being rewritten as richer activity UX arrives.

## ADR-031 — Wake phrases are configuration and may carry the command in the same utterance

The default wake phrases are `hey jarvis` and `jarvis`, but wake detection is provider-neutral configuration. While sleeping, local STT may hear complete utterances, but no cloud intelligence request is made unless the utterance begins with a configured wake phrase. The matched invocation is removed and any remaining text is immediately submitted as the same user command. Future product settings may change wake phrases without replacing Conversation Core or the voice engine.

## ADR-032 — Physical hearing state is distinct from generated assistant text

A completed Luna response is not automatically a response the user heard. Conversation Core keeps the full generated assistant transcript for semantic continuity. Voice playback separately commits `complete` or `interrupted` hearing state. On interruption, Core stores the physical PCM playback duration/bytes and an explicitly approximate heard-text prefix. The next voice request receives a private developer playback note so the model does not assume the unplayed remainder was heard. OpenAI `previous_response_id` continuation is preserved when the authoritative transcript chain still matches.

## ADR-033 — 0.0.5 barge-in is full-duplex but headset-first

The microphone resumes while TTS playback is active. Endpoint-confirmed user speech stops local playback immediately, while the same microphone capture continues through endpointing/STT and becomes the next turn. This establishes correct interruption/cancellation semantics without coupling Core to a concrete TTS provider. Production AEC/noise suppression remains a later audio integration because speaker echo can otherwise resemble user speech; 0.0.5 live acceptance should use a headset.

## ADR-034 — Runtime lifecycle, health, voice presence, and conversation activity are orthogonal

0.0.6 introduces `JarvisRuntime` as the process/runtime host, but it does not recreate V1's single all-purpose state enum. Runtime lifecycle (`stopped/starting/running/stopping`), runtime/component health, voice presence (`sleeping/awake`), and Conversation Core foreground activity remain separate authorities.

`JarvisRuntime.snapshot()` composes those truths for future clients without allowing one axis to overwrite another. An awake Jarvis may later research, wait for approval, or report degraded provider health without forcing those facts into one mutually exclusive state.

## ADR-035 — Reconnecting clients consume snapshots plus bounded event cursors

The shared `EventBus` remains authoritative and in-process. 0.0.6 adds monotonic event sequence numbers, replay after a cursor, correlation trace replay, and explicit history-gap detection.

A UI/client restart must not create a second Conversation Core or reconstruct state from provider transport events. It receives a runtime snapshot, remembers the latest cursor, and then consumes newer events. If the cursor predates retained history, Core reports the gap rather than silently pretending replay is complete.

A network/local API transport is deferred; the reconnect contract is established before choosing HTTP/WebSocket implementation details.

## ADR-036 — Durable event persistence is deferred until its redaction boundary is explicit

0.0.6 event replay is bounded memory only. V1 eventually needed persistence-boundary redaction because operational events could carry sensitive values into durable JSONL/SQLite artifacts. V2 will not introduce a durable event journal until retention, redaction, secret handling, user-data policy, and migration semantics are specified and tested together.

## ADR-037 — Provider routing is explicit and cost-stable by default

`IntelligenceProviderRouter` provides named routes and capability validation. It does not silently switch providers, models, reasoning strength, or service tiers. Automatic escalation/fallback remains a later policy layer and must preserve the user's cost/latency controls.

Provider health probes are concurrent and timeout-bounded; a slow health check is not allowed to block runtime snapshots or realtime conversation work.

## ADR-038 — Runtime settings contain orchestration policy, never provider secrets

`RuntimeSettings` centralizes non-secret runtime orchestration values such as the default provider route, event-history size, and health timeout. API keys and provider account credentials remain inside provider adapters/configuration and are never copied into `RuntimeSnapshot`.

Runtime settings do not silently read project `.env`; callers explicitly opt into an env file. This keeps tests deterministic and avoids V1's environment-contamination regressions.

## ADR-039 — Client protocol is platform-neutral; network exposure is a separate trust decision

0.0.7 defines `jarvis-runtime` protocol version 1 as JSON over standard HTTP/WebSocket. The contract must not depend on Electron IPC, Windows named pipes, Python object serialization, or a provider-specific realtime transport.

A native Windows, macOS, Linux, iOS, or Android app may consume the same protocol. A client-reported platform/device label is descriptive only and never grants authority, changes permissions, or selects a provider.

0.0.7 binds the unauthenticated local API to loopback only. This is a security boundary, not a desktop-only architectural assumption. LAN/WAN/mobile-to-desktop exposure requires authenticated device/account authority plus TLS or a secure relay. The future remote transport should carry the same protocol rather than fork Jarvis Core by UI platform.

## ADR-040 — Reconnect authority is the pair runtime_id + event cursor

An event sequence is meaningful only inside one `JarvisRuntime` lifetime. A reconnecting client that supplies a nonzero cursor must also supply the runtime identity that issued it.

If Core restarted, the cursor is ahead, bounded history has rolled over, or the replay size exceeds the safe reconnect limit, Core returns a reset reason and the current authoritative snapshot. A client must not merge an old derived state into a new runtime merely because numeric cursors happen to overlap.

The event adapter subscribes before snapshot capture. The snapshot cursor becomes a watermark: replay covers missed events through that watermark, while later events are already buffered for live delivery. This prevents the snapshot/subscription race from silently losing an event.

## ADR-041 — UI/client lifetime never owns Jarvis Core lifetime

`apps.runtime_api.create_app(runtime)` receives an already-owned runtime. It does not start another Core, replace Conversation Core on connect, or stop Core on client disconnect.

This directly applies the V1 lesson from duplicate Core startup/port conflicts and stale UI recovery. Future desktop/mobile shells may supervise or launch a Core according to deployment topology, but there must be exactly one process owner and client reconnection must not be mistaken for Core reconstruction.

Slow-client backpressure is also explicit. If a live client cannot keep up with its bounded queue, it is told to resynchronize; events are never silently dropped while the connection still claims to be synchronized.

## ADR-042 — Client commands are requests into Core, never a second state authority

0.0.8 allows local clients to submit typed user input through the Runtime API, but the transport does not own transcript, turn state, provider routing, or cancellation truth. Every accepted command enters the existing `ConversationCore` typed-input path. The Runtime API may issue a server-owned correlation bundle so clients can correlate acknowledgements and events, but network clients never choose Jarvis `correlation_id`, `request_id`, `turn_id`, or `cancellation_id` values.

A client submission must name the current `runtime_id` and `conversation_id`. A stale runtime or conversation is rejected before execution. This prevents an uncertain retry from silently landing in a restarted Core or a replacement conversation.

## ADR-043 — Runtime-scoped client_request_id provides transport idempotency

A reconnecting client may not know whether an HTTP acknowledgement was lost after Core accepted its command. 0.0.8 therefore binds one `client_request_id` to one normalized typed-command payload for the lifetime of one `JarvisRuntime`.

Retrying the same accepted request returns the same command ID and Core trace without a second provider execution. Reusing the same request ID for different text/conversation is an explicit conflict. The idempotency record is bounded/in-memory and does not claim durability across Core restart; a new `runtime_id` is a new authority lifetime.

This follows V1's duplicate-response lessons without using content similarity to collapse legitimate repeated user utterances. Transport retry identity and semantic/user-intent deduplication remain separate mechanisms.

## ADR-044 — Client cancellation delegates to Conversation Core cooperative cancellation

A client may cancel the active command it submitted, but it does not set Conversation Core state directly and does not terminate provider tasks by force. The Runtime command gateway delegates cancellation to `ConversationCore.cancel_active_turn`, which owns the cancellation registry/token and provider cancel request.

0.0.8 intentionally does not add a generic client command queue or arbitrary state-control RPCs. If a foreground turn is already active, a second client command is rejected as busy. Future multimodal/UI scheduling may add an explicit queue policy, but it must remain Core-owned and observable rather than being hidden in a desktop/mobile client.

## ADR-045 — Native full-duplex voice is a replaceable frontend, not Jarvis authority

0.0.9 introduces `VoiceFrontendProvider` above concrete speech transports. A native conversational voice model may own low-latency listening, speaking, backchannels, and interruption inside its session, but it does not own Jarvis reasoning, memory, tools, permissions, tasks, or durable state.

OpenAI GPT-Live is the first adapter and uses **client delegation**. Meaningful user requests are reconstructed from Live transcript timing and enter the existing `ConversationCore.submit_voice()` path. The configured `IntelligenceProvider` (Luna by default) remains the reasoning backend. Verified backend results return to the Live session as commentary for natural spoken presentation.

This intentionally applies V1 lessons from voice/reasoning coupling and ungrounded Realtime action responses. For future consequential tools, the backend action state remains authoritative; a voice frontend may not independently claim that an action succeeded. Exact confirmation/presentation ownership requires its own acceptance work before tool execution is enabled through the Live path.

The accepted Whisper/Luna/Qwen pipeline remains available and is not forced through the new native-session contract in 0.0.9. That avoids destabilizing accepted local behavior merely to make two very different transports look identical. The common product-level strategy is provider selection above both implementations; future native full-duplex providers can implement `VoiceFrontendProvider` without modifying Conversation Core.

A bridge-owned delegation revision prevents an older backend result from being spoken after a newer user correction. Conversation Core still owns cooperative cancellation and provider state; the frontend revision only controls whether an obsolete result may be presented.

0.0.9 is explicitly an A/B prototype. Production wake/sleep lifecycle, exact physical-playback reconciliation, durable Live transcript/memory reconciliation, tools/permissions through Live, remote WebRTC clients, and custom voices remain separate milestones.

## ADR-046 - Client GPT-Live media uses WebRTC; server/debug audio may use WebSockets

0.0.9 Repair2 separates **voice frontend provider** from **media transport**. OpenAI GPT-Live remains the current full-duplex provider, but a user-facing browser/desktop/mobile client should carry microphone and speaker media through WebRTC rather than routing raw PCM through the Python Core.

For WebRTC, the trusted Python service brokers session creation and keeps the OpenAI project API key private. The client owns negotiated media tracks. JSON transcripts and client-delegation events cross the WebRTC data channel and are relayed to the same provider-neutral `VoiceFrontendEvent`/`LiveConversationBridge` boundary. Jarvis Core, memory, permissions, tasks, and IntelligenceProvider routing therefore do not depend on WebRTC.

The existing primary WebSocket implementation remains valid for server-owned audio, deterministic transport tests, diagnostics, and fallback. It is not deleted merely because WebRTC becomes the preferred client-media transport.

This follows the V1 architectural lesson that the desktop interaction layer should use WebRTC while the Python Core continues independently. The Repair2 browser is intentionally loopback-only development infrastructure; authenticated remote clients and a production sideband/control topology remain separate security work.


## ADR-047 — Realtime Mini is the current default conversational frontend, not Jarvis authority

0.0.9 live acceptance selects `gpt-realtime-2.1-mini` over WebRTC as the current default conversational frontend because it delivered the preferred naturalness, interruption behavior, responsiveness, and cost profile in direct A/B testing. This is a provider choice, not a permanent architectural dependency.

Realtime may answer ordinary conversation and general knowledge directly. It receives only a narrow `delegate_to_jarvis_core` capability for work that depends on durable/private memory, application state, tools/actions, permissions, background tasks, current-data workflows, or materially stronger reasoning. Realtime never chooses the concrete backend provider. Jarvis Core remains free to route delegated work to Luna, Sol, local/future models, tools, memory, or a task worker.

GPT-Live, full Realtime 2.1, and the local Whisper/Qwen chain remain alternatives behind the conversational-frontend boundary. A later provider can replace Realtime Mini without moving memory, task, permission, or tool authority.

## ADR-048 — Client WebRTC is product transport, browser is only the 0.0.9 harness

The successful 0.0.9 WebRTC test establishes negotiated client media as the preferred user-device transport. The development browser page is not a product requirement. The planned desktop app may host the same WebRTC media/data-channel flow inside Electron/React while Jarvis Core remains a separate authoritative process/service.

Raw WebSocket PCM remains valid for server-owned media, diagnostics, and fallback. Transport selection is independent from conversational frontend selection and backend intelligence routing.


## ADR-049 — Desktop is a thin client over authoritative Core

0.1.0 introduces the first native Jarvis desktop shell. Electron owns native application lifecycle and exactly one supervised loopback Python host. React owns presentation, client WebRTC media, progressive speech captions, and user input presentation. Neither Electron nor React owns durable Jarvis state, memory, permissions, tools, tasks, or backend intelligence selection.

This applies the V1 lessons from browser-tab lifecycle and duplicate Core startup: the native shell performs a loopback health/port preflight before spawning Core, uses a single-instance lock, and only terminates the Core process it owns. A renderer reload/disconnect is a client lifecycle event, not a reason to reconstruct Jarvis Core.

The renderer never receives `OPENAI_API_KEY`. The trusted Python host brokers OpenAI Realtime WebRTC session creation and carries the existing `RealtimeCoreBridge` for selective delegation. The successful browser WebRTC flow from 0.0.9 is therefore embedded in the desktop product without moving provider credentials or Core authority into the UI.

Typed input intentionally enters the same Realtime session as microphone input using Realtime conversation events. This avoids a UI-specific second conversation path while preserving the existing Core delegation boundary. The versioned Runtime API is mounted beneath the desktop host so later memory/task/tool/settings surfaces can grow against Core-owned contracts instead of duplicating business logic in React.

The 0.1.0 avatar is a replaceable code-native placeholder. Visual state (`idle`, `listening`, `thinking`, `speaking`, `working`, `error`) is presentation only and must never become authoritative runtime state.

## ADR-050 — Sleep is local presence; awake Realtime is a replaceable conversational lane

0.1.1 separates **presence lifecycle** from foreground voice activity. `sleeping/awake` belongs to Jarvis lifecycle; `listening/thinking/speaking/working/error` remains activity/presentation. A desktop renderer may display both, but it may not invent Core authority from either.

While sleeping, no OpenAI Realtime call is active. The one physical microphone remains owned by the client and 16 kHz mono PCM is sent only to the loopback Core host. A provider-neutral `LocalWakeListener` combines replaceable local speech-presence, local STT, and the existing `WakePhraseDetector`. Only a completed local wake decision may open Realtime. The wake phrase is stripped from the beginning of the complete utterance and the remainder is preserved as the opening command, so `Jarvis, do X` never requires a second repetition.

While awake, Realtime Mini + Cedar + WebRTC remains the current conversational lane. Clear end-of-interaction intent is mapped by the Realtime adapter to a **lifecycle-only** sleep signal; it does not call backend intelligence and cannot mutate memory/tools/tasks. A 60-second local inactivity timer provides the second sleep path. Sleeping tears down Realtime before re-arming local wake.

The local wake provider is replaceable. whisper.cpp is accepted for the desktop alpha because it already exists, can preserve full-command wake text, and keeps sleeping audio local. It is heavier than a dedicated keyword-spotting engine and is not presumed to be the final production/mobile implementation.

## ADR-051 — Core owns delegated capability and backend model routing

0.1.2 introduces a provider-neutral `DelegationOrchestrator` between conversational frontends and backend intelligence/capabilities. A frontend such as Realtime Mini may decide that authoritative Core help is required and may describe a coarse capability category, but it may not select Luna, a stronger model, a concrete tool provider, memory implementation, current-data source, or task worker.

Routine delegated reasoning uses the configured default intelligence route. A separately configured `strong` provider may be selected by Core for materially harder reasoning using an observable local policy. The selected provider is a per-turn override inside Conversation Core; it never mutates the conversation's default provider route.

Memory, action, current-data, and long-task delegation are explicit Core capability slots. Until an authoritative handler is registered for one of those slots, the request fails `unavailable`. It must not silently fall through to a language model that could invent a memory, current fact, completed action, or background task. This follows V1's strongest routing lesson: once work is positively routed to a capability, failure remains inside that capability boundary rather than falling through into another one.

The first complexity policy is intentionally deterministic and local. Jarvis does not pay a second classifier-model call on every delegation merely to choose another model. The policy may be replaced later if routing telemetry demonstrates a materially better approach, but the provider-neutral contract remains.
