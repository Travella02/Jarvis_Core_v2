"""Adapter between OpenAI Realtime function calls and authoritative Jarvis Core.

Realtime is allowed to converse directly.  It receives one narrow application
function that asks Core for durable memory, private/current state, tools/actions,
background work, or stronger reasoning. Core executes the request and returns a
verified function result; Realtime remains only the conversational surface.
"""

from __future__ import annotations

import asyncio
import json
from time import monotonic
from typing import Any, Protocol

from core.intelligence import ReasoningPolicy
from providers.voice_frontend.openai_realtime.webrtc import BrowserRealtimeRelay, DELEGATE_TOOL_NAME


class ConversationBackend(Protocol):
    @property
    def active_trace(self): ...

    @property
    def event_bus(self): ...

    @property
    def context(self): ...

    async def submit_voice(self, text: str, *, reasoning_policy: ReasoningPolicy | None = None): ...

    async def cancel_active_turn(self, reason: str = "user requested cancellation") -> bool: ...


class RealtimeCoreBridge:
    def __init__(
        self,
        *,
        conversation: ConversationBackend,
        relay: BrowserRealtimeRelay,
        reasoning_policy: ReasoningPolicy | None = None,
    ) -> None:
        self.conversation = conversation
        self.relay = relay
        self.reasoning_policy = reasoning_policy or ReasoningPolicy(level="none", allow_escalation=False)
        self._revision = 0
        self._tasks: set[asyncio.Task[None]] = set()
        self._closed = False

    @property
    def pending_count(self) -> int:
        """Number of Core delegations still running for this live session."""
        return sum(1 for task in self._tasks if not task.done())

    async def handle_event(self, payload: dict[str, Any]) -> bool:
        if str(payload.get("type") or "") != "response.function_call_arguments.done":
            return False
        if str(payload.get("name") or "") != DELEGATE_TOOL_NAME:
            return False
        call_id = str(payload.get("call_id") or "").strip()
        if not call_id:
            return False
        try:
            arguments = json.loads(str(payload.get("arguments") or "{}"))
        except ValueError:
            arguments = {}
        request = str(arguments.get("request") or "").strip()
        mode = str(arguments.get("mode") or "reasoning").strip() or "reasoning"
        if not request:
            await self.relay.send_function_output(
                call_id,
                {"status": "failed", "error": "Jarvis Core received an empty delegated request."},
            )
            return True

        self._revision += 1
        revision = self._revision
        if self.conversation.active_trace is not None:
            await self.conversation.cancel_active_turn("superseded by newer realtime core delegation")
        task = asyncio.create_task(
            self._run_call(call_id=call_id, request=request, mode=mode, revision=revision),
            name=f"jarvis-realtime-core-{call_id}",
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return True

    async def _run_call(self, *, call_id: str, request: str, mode: str, revision: int) -> None:
        if self._closed:
            return
        context = self.conversation.context
        event_bus = self.conversation.event_bus
        received = event_bus.emit(
            "voice.realtime.core.requested",
            origin="openai-realtime-bridge",
            conversation_id=context.conversation_id,
            user_id=context.user_id,
            device_id=context.device_id,
            payload={"call_id": call_id, "mode": mode, "request_length": len(request)},
        )
        started = monotonic()
        try:
            result = await self.conversation.submit_voice(request, reasoning_policy=self.reasoning_policy)
        except Exception as exc:
            event_bus.emit(
                "voice.realtime.core.failed",
                origin="openai-realtime-bridge",
                conversation_id=context.conversation_id,
                user_id=context.user_id,
                device_id=context.device_id,
                parent_event_id=received.event_id,
                payload={"call_id": call_id, "exception_type": type(exc).__name__},
            )
            await self.relay.send_function_output(
                call_id,
                {"status": "failed", "error": "Jarvis Core failed to complete the delegated request."},
            )
            return

        if revision != self._revision:
            event_bus.emit(
                "voice.realtime.core.superseded",
                origin="openai-realtime-bridge",
                trace=result.trace,
                conversation_id=context.conversation_id,
                user_id=context.user_id,
                device_id=context.device_id,
                parent_event_id=received.event_id,
                payload={"call_id": call_id},
            )
            await self.relay.send_function_output(
                call_id,
                {"status": "superseded", "message": "A newer user request superseded this backend result. Do not present it as current."},
                continue_response=False,
            )
            return

        if result.status == "completed" and result.text.strip():
            elapsed_ms = round((monotonic() - started) * 1000.0, 1)
            await self.relay.send_function_output(
                call_id,
                {"status": "completed", "result": result.text.strip(), "backend_ms": elapsed_ms},
            )
            event_bus.emit(
                "voice.realtime.core.completed",
                origin="openai-realtime-bridge",
                trace=result.trace,
                conversation_id=context.conversation_id,
                user_id=context.user_id,
                device_id=context.device_id,
                parent_event_id=received.event_id,
                payload={"call_id": call_id, "mode": mode, "backend_ms": elapsed_ms},
            )
            return

        await self.relay.send_function_output(
            call_id,
            {"status": result.status, "result": result.text.strip()},
        )

    async def wait_idle(self) -> None:
        while self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)

    async def close(self) -> None:
        self._closed = True
        if self.conversation.active_trace is not None:
            await self.conversation.cancel_active_turn("realtime voice session closing")
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
