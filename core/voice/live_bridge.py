"""Bridge a full-duplex voice frontend to the authoritative Conversation Core.

The bridge deliberately owns no durable memory or tool authority.  It turns a
frontend delegation into the same ``ConversationCore.submit_voice`` call used by
the accepted local pipeline, then returns the verified Core result to the voice
frontend for natural spoken delivery.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic
from typing import Protocol

from core.intelligence import ReasoningPolicy
from core.voice.frontend import VoiceFrontendEvent, VoiceFrontendEventType, VoiceFrontendSession


@dataclass(frozen=True, slots=True)
class TranscriptFragment:
    text: str
    start_ms: int
    end_ms: int


class LiveTranscriptBuffer:
    """Ordered input transcript deltas with delegation-safe consumption.

    GPT-Live transcript deltas do not include a turn-complete marker.  Client
    delegation does include an ``offset_ms``.  We therefore consume the ordered
    transcript fragments observed up to that offset, preserving provider text
    exactly and advancing a cursor only after a delegation claims them.
    """

    def __init__(self) -> None:
        self._fragments: list[TranscriptFragment] = []
        self._cursor = 0
        self._condition = asyncio.Condition()

    async def append(self, text: str, start_ms: int | None, end_ms: int | None) -> None:
        if not text:
            return
        start = max(0, int(start_ms or 0))
        end = max(start, int(end_ms if end_ms is not None else start))
        async with self._condition:
            self._fragments.append(TranscriptFragment(text=text, start_ms=start, end_ms=end))
            self._condition.notify_all()

    @property
    def latest_end_ms(self) -> int:
        if not self._fragments:
            return 0
        return max(item.end_ms for item in self._fragments)

    async def consume_for_delegation(
        self,
        offset_ms: int,
        *,
        transcript_catchup_ms: int = 120,
        timeout_s: float = 0.35,
    ) -> str:
        """Return unconsumed text belonging to a delegation.

        Delivery can be uneven, so if the transcript timeline has not reached
        near the delegation offset we briefly allow late transcript deltas to
        arrive.  This is bounded and only affects the client-delegation path.
        """

        target = max(0, int(offset_ms) - max(0, transcript_catchup_ms))
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.0, timeout_s)
        async with self._condition:
            while self.latest_end_ms < target:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                try:
                    await asyncio.wait_for(self._condition.wait(), timeout=remaining)
                except TimeoutError:
                    break

            limit = self._cursor
            # Keep a small future tolerance because transcript intervals are
            # approximate and may straddle the delegation timestamp.
            max_end = max(0, int(offset_ms)) + max(0, transcript_catchup_ms)
            for index in range(self._cursor, len(self._fragments)):
                if self._fragments[index].start_ms <= max_end:
                    limit = index + 1
                else:
                    break

            selected = self._fragments[self._cursor:limit]
            self._cursor = limit

        return "".join(item.text for item in selected).strip()


class ConversationBackend(Protocol):
    @property
    def active_trace(self): ...

    @property
    def event_bus(self): ...

    @property
    def context(self): ...

    async def submit_voice(self, text: str, *, reasoning_policy: ReasoningPolicy | None = None): ...

    async def cancel_active_turn(self, reason: str = "user requested cancellation") -> bool: ...


class LiveConversationBridge:
    """Route GPT-Live client delegations through Conversation Core/Luna."""

    def __init__(
        self,
        *,
        conversation: ConversationBackend,
        session: VoiceFrontendSession,
        reasoning_policy: ReasoningPolicy | None = None,
    ) -> None:
        self.conversation = conversation
        self.session = session
        self.reasoning_policy = reasoning_policy or ReasoningPolicy(level="none", allow_escalation=False)
        self.transcript = LiveTranscriptBuffer()
        self._backend_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[None]] = set()
        self._closed = False
        self._revision = 0

    async def handle_event(self, event: VoiceFrontendEvent) -> None:
        if event.event_type is VoiceFrontendEventType.INPUT_TRANSCRIPT_DELTA:
            await self.transcript.append(event.text, event.start_ms, event.end_ms)
            return
        if event.event_type is not VoiceFrontendEventType.DELEGATION_REQUESTED:
            return
        if not event.delegation_id:
            return

        # Every delegation advances a bridge-owned revision.  A newer user
        # correction must be able to invalidate an older queued/running result,
        # even in the small race before Conversation Core exposes active_trace.
        # Core still owns actual provider cancellation and state transitions.
        self._revision += 1
        revision = self._revision
        if self.conversation.active_trace is not None:
            await self.conversation.cancel_active_turn("superseded by newer live delegation")

        task = asyncio.create_task(
            self._run_delegation(event.delegation_id, int(event.offset_ms or 0), revision),
            name=f"jarvis-live-delegation-{event.delegation_id}",
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run_delegation(self, delegation_id: str, offset_ms: int, revision: int) -> None:
        async with self._backend_lock:
            if self._closed:
                return
            text = await self.transcript.consume_for_delegation(offset_ms)
            if revision != self._revision:
                self._emit_superseded(delegation_id, reason="newer delegation arrived before backend start")
                return
            if not text:
                await self.session.send_commentary(
                    delegation_id,
                    "I could not recover a complete user utterance from the live transcript. Ask the user to repeat that request.",
                )
                return

            context = self.conversation.context
            event_bus = self.conversation.event_bus
            received = event_bus.emit(
                "voice.frontend.delegation.received",
                origin="voice-frontend-bridge",
                conversation_id=context.conversation_id,
                user_id=context.user_id,
                device_id=context.device_id,
                payload={"delegation_id": delegation_id, "text_length": len(text)},
            )
            backend_started = monotonic()
            # Check once more immediately before entering Core so a newer
            # delegation cannot slip through the transcript-consumption race.
            if revision != self._revision:
                self._emit_superseded(
                    delegation_id,
                    parent_event_id=received.event_id,
                    reason="newer delegation arrived before backend submission",
                )
                return
            try:
                result = await self.conversation.submit_voice(
                    text,
                    reasoning_policy=self.reasoning_policy,
                )
            except Exception as exc:
                event_bus.emit(
                    "voice.frontend.delegation.failed",
                    origin="voice-frontend-bridge",
                    conversation_id=context.conversation_id,
                    user_id=context.user_id,
                    device_id=context.device_id,
                    parent_event_id=received.event_id,
                    payload={"delegation_id": delegation_id, "exception_type": type(exc).__name__},
                )
                await self.session.send_commentary(
                    delegation_id,
                    "The Jarvis backend hit an error while handling that request. Tell the user briefly that the task failed and do not invent a result.",
                )
                return

            if revision != self._revision:
                self._emit_superseded(
                    delegation_id,
                    parent_event_id=received.event_id,
                    trace=result.trace,
                    reason="newer delegation superseded backend result",
                )
                return

            if result.status == "completed" and result.text.strip():
                await self.session.send_commentary(delegation_id, result.text.strip())
                event_bus.emit(
                    "voice.frontend.delegation.completed",
                    origin="voice-frontend-bridge",
                    trace=result.trace,
                    conversation_id=context.conversation_id,
                    user_id=context.user_id,
                    device_id=context.device_id,
                    parent_event_id=received.event_id,
                    payload={
                        "delegation_id": delegation_id,
                        "result_chars": len(result.text.strip()),
                        "backend_ms": round((monotonic() - backend_started) * 1000.0, 1),
                    },
                )
            elif result.status == "cancelled":
                event_bus.emit(
                    "voice.frontend.delegation.cancelled",
                    origin="voice-frontend-bridge",
                    trace=result.trace,
                    conversation_id=context.conversation_id,
                    user_id=context.user_id,
                    device_id=context.device_id,
                    parent_event_id=received.event_id,
                    payload={"delegation_id": delegation_id},
                )
            else:
                await self.session.send_commentary(
                    delegation_id,
                    "The Jarvis backend did not produce a completed answer. Tell the user briefly that you could not finish that request.",
                )


    def _emit_superseded(
        self,
        delegation_id: str,
        *,
        reason: str,
        parent_event_id: str | None = None,
        trace=None,
    ) -> None:
        context = self.conversation.context
        self.conversation.event_bus.emit(
            "voice.frontend.delegation.superseded",
            origin="voice-frontend-bridge",
            trace=trace,
            conversation_id=context.conversation_id,
            user_id=context.user_id,
            device_id=context.device_id,
            parent_event_id=parent_event_id,
            payload={"delegation_id": delegation_id, "reason": reason},
        )

    async def wait_idle(self) -> None:
        """Wait for all currently scheduled backend delegations to settle."""
        while self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)

    async def close(self) -> None:
        self._closed = True
        if self.conversation.active_trace is not None:
            await self.conversation.cancel_active_turn("live voice session closing")
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
