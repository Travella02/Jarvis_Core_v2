"""Provider-independent Conversation Core orchestration for typed and voice turns."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from core.common.cancellation import CancellationRegistry
from core.common.ids import CorrelationContext
from core.conversation.events import EventBus
from core.conversation.models import (
    ConversationContext,
    HeardResponseState,
    InputChannel,
    TranscriptEntry,
    TranscriptRole,
    VoiceInterruptionContext,
)
from core.conversation.state_machine import CoreState, CoreStateMachine
from core.intelligence import (
    IntelligenceContext,
    IntelligenceEventType,
    IntelligenceProvider,
    ReasoningPolicy,
)
from core.tools import ToolDefinition, ToolRequest


VOICE_RESPONSE_INSTRUCTION = (
    "This is a spoken Jarvis turn. Respond naturally and concisely, usually in one to three "
    "short sentences unless the user asks for detail. Make the first sentence short, complete, "
    "direct, and easy to speak: target three to six spoken words and put its sentence-ending "
    "punctuation immediately after it. The first sentence should answer the user's intent, not be "
    "filler such as 'Sure', 'Of course', or another setup phrase, and never be a fragment that "
    "needs the next phrase to make sense. Then elaborate naturally if useful. Prefer plain spoken "
    "language and natural punctuation, and avoid markdown formatting, headings, bullets, tables, "
    "or code fences unless they are essential."
)


@dataclass(frozen=True, slots=True)
class TurnResult:
    trace: CorrelationContext
    status: str
    text: str
    tool_requests: tuple[ToolRequest, ...] = ()
    provider_response_id: str | None = None
    detail: str | None = None


class ConversationCore:
    """Own one ConversationContext and route user turns through a provider.

    The provider sees a snapshot; Core owns transcript, state, referents, event
    correlation, and cancellation. Voice text enters through the same path as
    typed text after STT so speech never creates a second conversation truth.
    """

    def __init__(
        self,
        *,
        context: ConversationContext,
        provider: IntelligenceProvider,
        event_bus: EventBus | None = None,
        cancellations: CancellationRegistry | None = None,
    ) -> None:
        self.context = context
        self.provider = provider
        self.event_bus = event_bus or EventBus()
        self.cancellations = cancellations or CancellationRegistry()
        self.state = CoreStateMachine(
            context,
            self.event_bus,
            initial_state=CoreState.LISTENING,
        )
        self._active_trace: CorrelationContext | None = None

    @property
    def active_trace(self) -> CorrelationContext | None:
        return self._active_trace

    async def submit_typed(
        self,
        text: str,
        *,
        tools: Sequence[ToolDefinition] = (),
        reasoning_policy: ReasoningPolicy | None = None,
        _trace: CorrelationContext | None = None,
    ) -> TurnResult:
        """Submit typed text through the authoritative Conversation Core.

        ``_trace`` is reserved for trusted in-process adapters such as the Runtime
        API. Network clients never supply Jarvis correlation/request/turn IDs.
        """

        return await self._submit_text(
            text,
            channel=InputChannel.TYPED,
            tools=tools,
            reasoning_policy=reasoning_policy,
            trace=_trace,
        )

    async def submit_voice(
        self,
        text: str,
        *,
        tools: Sequence[ToolDefinition] = (),
        reasoning_policy: ReasoningPolicy | None = None,
    ) -> TurnResult:
        return await self._submit_text(
            text,
            channel=InputChannel.VOICE,
            tools=tools,
            reasoning_policy=reasoning_policy,
        )

    async def _submit_text(
        self,
        text: str,
        *,
        channel: InputChannel,
        tools: Sequence[ToolDefinition] = (),
        reasoning_policy: ReasoningPolicy | None = None,
        trace: CorrelationContext | None = None,
    ) -> TurnResult:
        prompt = text.strip()
        if not prompt:
            raise ValueError(f"{channel.value} input cannot be empty")
        if self._active_trace is not None:
            raise RuntimeError("a foreground turn is already active")
        if self.state.state is not CoreState.LISTENING:
            raise RuntimeError(f"cannot accept {channel.value} input while core state={self.state.state.value}")

        trace = trace or CorrelationContext.create()
        handle = self.cancellations.register(trace)
        self._active_trace = trace
        chunks: list[str] = []
        tool_requests: list[ToolRequest] = []
        provider_response_id: str | None = None
        terminal_status: str | None = None
        terminal_detail: str | None = None
        response_started = False
        pending_voice_interruption = (
            self.context.pending_voice_interruption
            if channel is InputChannel.VOICE
            else None
        )
        if channel is InputChannel.VOICE:
            # Generated model text is not the same thing as audio the user heard.
            # VoiceEngine records COMPLETE/INTERRUPTED only after physical playback.
            self.context.heard_response_state = HeardResponseState.NONE
            self.context.heard_response_text = ""

        user_entry = TranscriptEntry.create(
            role=TranscriptRole.USER,
            content=prompt,
            channel=channel,
            turn_id=trace.turn_id,
        )
        self.context.append_transcript(user_entry)
        input_event = self.event_bus.emit(
            "user.text.received",
            origin=channel.value,
            trace=trace,
            conversation_id=self.context.conversation_id,
            user_id=self.context.user_id,
            device_id=self.context.device_id,
            payload={"entry_id": user_entry.entry_id, "channel": channel.value},
        )
        self.event_bus.emit(
            "turn.endpointed",
            origin="conversation-core",
            trace=trace,
            conversation_id=self.context.conversation_id,
            user_id=self.context.user_id,
            device_id=self.context.device_id,
            parent_event_id=input_event.event_id,
            payload={"channel": channel.value},
        )
        self.state.transition(CoreState.THINKING, trace=trace, reason=f"{channel.value} turn accepted")
        self.event_bus.emit(
            "intelligence.routed",
            origin="conversation-core",
            trace=trace,
            conversation_id=self.context.conversation_id,
            user_id=self.context.user_id,
            device_id=self.context.device_id,
            payload={
                "provider": self.provider.metadata.provider,
                "model": self.provider.metadata.model,
            },
        )

        try:
            snapshot = self.context.to_intelligence_context(trace)
            if channel is InputChannel.VOICE:
                metadata = {**dict(snapshot.metadata), "input_channel": "voice"}
                if pending_voice_interruption is not None:
                    metadata["voice_interruption"] = pending_voice_interruption.to_dict()
                snapshot = IntelligenceContext(
                    trace=snapshot.trace,
                    messages=(
                        {"role": "developer", "content": VOICE_RESPONSE_INSTRUCTION},
                        *snapshot.messages,
                    ),
                    metadata=metadata,
                )
                # The interruption note belongs to this next voice turn only. It
                # remains in OpenAI's previous_response_id chain once submitted.
                self.context.pending_voice_interruption = None
            async for event in self.provider.stream_response(
                context=snapshot,
                tools=tools,
                reasoning_policy=reasoning_policy or ReasoningPolicy(),
                cancellation_token=handle.token,
            ):
                if event.provider_response_id:
                    provider_response_id = event.provider_response_id

                if event.event_type is IntelligenceEventType.TEXT_DELTA and event.text_delta:
                    if not response_started:
                        self.state.transition(
                            CoreState.SPEAKING,
                            trace=trace,
                            reason="response stream started",
                        )
                        response_started = True
                    chunks.append(event.text_delta)
                    if channel is InputChannel.TYPED:
                        self.context.heard_response_state = HeardResponseState.PARTIAL
                        self.context.heard_response_text = "".join(chunks)
                    self.event_bus.emit(
                        "response.text.delta",
                        origin="intelligence-provider",
                        trace=trace,
                        conversation_id=self.context.conversation_id,
                        user_id=self.context.user_id,
                        device_id=self.context.device_id,
                        payload={"text_delta": event.text_delta},
                    )
                    continue

                if event.event_type is IntelligenceEventType.TOOL_REQUEST and event.tool_request:
                    tool_requests.append(event.tool_request)
                    self.event_bus.emit(
                        "tool.requested",
                        origin="intelligence-provider",
                        trace=trace,
                        conversation_id=self.context.conversation_id,
                        user_id=self.context.user_id,
                        device_id=self.context.device_id,
                        payload={
                            "tool_name": event.tool_request.tool_name,
                            "call_id": event.tool_request.provider_call_id,
                            "authority": "intent-only",
                        },
                    )
                    continue

                if event.event_type is IntelligenceEventType.COMPLETED:
                    terminal_status = "completed"
                    break
                if event.event_type is IntelligenceEventType.CANCELLED:
                    terminal_status = "cancelled"
                    terminal_detail = event.detail
                    break
                if event.event_type is IntelligenceEventType.DEGRADED:
                    terminal_status = "degraded"
                    terminal_detail = event.detail
                    break
                if event.event_type is IntelligenceEventType.ERROR:
                    terminal_status = "error"
                    terminal_detail = event.detail
                    break

            if terminal_status is None:
                terminal_status = "error"
                terminal_detail = "provider stream ended without a terminal event"

            response_text = "".join(chunks).strip()
            if response_text:
                interrupted = terminal_status != "completed"
                self.context.append_transcript(
                    TranscriptEntry.create(
                        role=TranscriptRole.ASSISTANT,
                        content=response_text,
                        channel=channel,
                        turn_id=trace.turn_id,
                        interrupted=interrupted,
                    )
                )

            if terminal_status == "completed":
                if channel is InputChannel.TYPED:
                    self.context.heard_response_state = HeardResponseState.COMPLETE
                    self.context.heard_response_text = response_text
                self.event_bus.emit(
                    "response.completed",
                    origin="conversation-core",
                    trace=trace,
                    conversation_id=self.context.conversation_id,
                    user_id=self.context.user_id,
                    device_id=self.context.device_id,
                    payload={
                        "channel": channel.value,
                        "provider_response_id": provider_response_id,
                        "tool_request_count": len(tool_requests),
                    },
                )
                if self.state.state in {CoreState.THINKING, CoreState.SPEAKING}:
                    self.state.transition(CoreState.LISTENING, trace=trace, reason="turn complete")
            elif terminal_status == "cancelled":
                if channel is InputChannel.TYPED:
                    self.context.heard_response_state = HeardResponseState.INTERRUPTED
                    self.context.heard_response_text = response_text
                self.event_bus.emit(
                    "response.interrupted",
                    origin="conversation-core",
                    trace=trace,
                    conversation_id=self.context.conversation_id,
                    user_id=self.context.user_id,
                    device_id=self.context.device_id,
                    payload={"reason": terminal_detail},
                )
                if self.state.state in {CoreState.THINKING, CoreState.SPEAKING}:
                    self.state.transition(CoreState.LISTENING, trace=trace, reason="turn cancelled")
            elif terminal_status == "degraded":
                if channel is InputChannel.TYPED:
                    self.context.heard_response_state = HeardResponseState.INTERRUPTED
                    self.context.heard_response_text = response_text
                self.state.transition(CoreState.DEGRADED, trace=trace, reason=terminal_detail)
                self.event_bus.emit(
                    "provider.degraded",
                    origin="conversation-core",
                    trace=trace,
                    conversation_id=self.context.conversation_id,
                    user_id=self.context.user_id,
                    device_id=self.context.device_id,
                    payload={"detail": terminal_detail},
                )
            else:
                if channel is InputChannel.TYPED:
                    self.context.heard_response_state = HeardResponseState.INTERRUPTED
                    self.context.heard_response_text = response_text
                self.state.transition(CoreState.ERROR, trace=trace, reason=terminal_detail)
                self.event_bus.emit(
                    "core.error",
                    origin="conversation-core",
                    trace=trace,
                    conversation_id=self.context.conversation_id,
                    user_id=self.context.user_id,
                    device_id=self.context.device_id,
                    payload={"detail": terminal_detail},
                )

            if terminal_status == "cancelled" and tool_requests:
                self.event_bus.emit(
                    "tool.plan.discarded",
                    origin="conversation-core",
                    trace=trace,
                    conversation_id=self.context.conversation_id,
                    user_id=self.context.user_id,
                    device_id=self.context.device_id,
                    payload={"count": len(tool_requests), "reason": "turn cancelled"},
                )
                tool_requests.clear()

            return TurnResult(
                trace=trace,
                status=terminal_status,
                text=response_text,
                tool_requests=tuple(tool_requests),
                provider_response_id=provider_response_id,
                detail=terminal_detail,
            )
        except Exception as exc:
            if self.state.state is not CoreState.ERROR:
                try:
                    self.state.transition(CoreState.ERROR, trace=trace, reason=type(exc).__name__)
                except Exception:
                    pass
            self.event_bus.emit(
                "core.error",
                origin="conversation-core",
                trace=trace,
                conversation_id=self.context.conversation_id,
                user_id=self.context.user_id,
                device_id=self.context.device_id,
                payload={"exception_type": type(exc).__name__},
            )
            raise
        finally:
            self.cancellations.complete(handle.cancellation_id)
            self._active_trace = None

    def record_voice_playback(
        self,
        *,
        response_turn_id: str | None,
        generated_text: str,
        heard_text: str,
        interrupted: bool,
        playback_ms: float,
        played_bytes: int,
        queued_bytes: int,
        alignment_method: str,
        interruption_phase: str = "speaking",
    ) -> None:
        """Commit what was physically heard, separately from generated text."""

        clean_generated = generated_text.strip()
        clean_heard = heard_text.strip()
        if interrupted:
            self.context.heard_response_state = HeardResponseState.INTERRUPTED
            self.context.heard_response_text = clean_heard
            interruption = VoiceInterruptionContext(
                response_turn_id=response_turn_id,
                generated_text=clean_generated,
                heard_text=clean_heard,
                playback_ms=max(0.0, playback_ms),
                played_bytes=max(0, played_bytes),
                queued_bytes=max(0, queued_bytes),
                alignment_method=alignment_method,
                interruption_phase=interruption_phase,
            )
            self.context.pending_voice_interruption = interruption
            event_type = "voice.playback.interrupted"
            payload = interruption.to_dict()
        else:
            self.context.heard_response_state = HeardResponseState.COMPLETE
            self.context.heard_response_text = clean_generated
            self.context.pending_voice_interruption = None
            event_type = "voice.playback.completed"
            payload = {
                "response_turn_id": response_turn_id,
                "playback_ms": max(0.0, playback_ms),
                "played_bytes": max(0, played_bytes),
                "queued_bytes": max(0, queued_bytes),
            }

        self.event_bus.emit(
            event_type,
            origin="voice-engine",
            conversation_id=self.context.conversation_id,
            user_id=self.context.user_id,
            device_id=self.context.device_id,
            payload=payload,
        )

    async def cancel_active_turn(self, reason: str = "user requested cancellation") -> bool:
        trace = self._active_trace
        if trace is None or trace.cancellation_id is None:
            return False
        cancelled = self.cancellations.cancel(trace.cancellation_id, reason)
        if not cancelled:
            return False
        self.event_bus.emit(
            "turn.cancel.requested",
            origin="conversation-core",
            trace=trace,
            conversation_id=self.context.conversation_id,
            user_id=self.context.user_id,
            device_id=self.context.device_id,
            payload={"reason": reason},
        )
        await self.provider.cancel(trace.request_id)
        return True
