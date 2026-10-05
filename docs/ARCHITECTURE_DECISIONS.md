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
