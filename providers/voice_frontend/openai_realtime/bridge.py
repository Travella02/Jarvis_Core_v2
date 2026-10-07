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

from core.intelligence import (
    DelegationMode,
    DelegationOrchestrator,
    DelegationRequest,
    DelegationStatus,
    ReasoningPolicy,
)
from providers.voice_frontend.openai_realtime.webrtc import (
    BrowserRealtimeRelay,
    CORE_RESULT_RESPONSE_INSTRUCTIONS,
    DEFAULT_REALTIME_MAX_OUTPUT_TOKENS,
    DELEGATE_TOOL_NAME,
    EXPANDED_REALTIME_MAX_OUTPUT_TOKENS,
    EXPANDED_RESPONSE_INSTRUCTIONS,
    EXPAND_RESPONSE_TOOL_NAME,
    SLEEP_TOOL_NAME,
)


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
        delegation_orchestrator: DelegationOrchestrator | None = None,
    ) -> None:
        self.conversation = conversation
        self.relay = relay
        self.reasoning_policy = reasoning_policy or ReasoningPolicy(level="none", allow_escalation=False)
        self.delegation_orchestrator = delegation_orchestrator
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
        name = str(payload.get("name") or "")
        call_id = str(payload.get("call_id") or "").strip()
        if not call_id:
            return False
        if name == EXPAND_RESPONSE_TOOL_NAME:
            await self.relay.send_function_output(
                call_id,
                {"status": "approved", "mode": "expanded"},
                response_overrides={
                    "max_output_tokens": EXPANDED_REALTIME_MAX_OUTPUT_TOKENS,
                    "instructions": EXPANDED_RESPONSE_INSTRUCTIONS,
                },
            )
            return True
        if name == SLEEP_TOOL_NAME:
            try:
                arguments = json.loads(str(payload.get("arguments") or "{}"))
            except ValueError:
                arguments = {}
            reason = str(arguments.get("reason") or "explicit_sleep").strip() or "explicit_sleep"
            self.conversation.event_bus.emit(
                "voice.presence.sleep_requested",
                origin="openai-realtime-bridge",
                conversation_id=self.conversation.context.conversation_id,
                user_id=self.conversation.context.user_id,
                device_id=self.conversation.context.device_id,
                payload={"call_id": call_id, "reason": reason},
            )
            await self.relay.request_browser_sleep(reason=reason)
            return True
        if name != DELEGATE_TOOL_NAME:
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
            if self.delegation_orchestrator is None:
                result = await self.conversation.submit_voice(request, reasoning_policy=self.reasoning_policy)
                routed_status = result.status
                routed_text = result.text.strip()
                routed_trace = result.trace
                route_name = "legacy-default"
                complexity_score = 0
                route_reason = "legacy bridge path"
            else:
                try:
                    delegation_mode = DelegationMode(mode)
                except ValueError:
                    delegation_mode = DelegationMode.REASONING
                routed = await self.delegation_orchestrator.execute(
                    DelegationRequest(goal=request, mode=delegation_mode),
                    conversation=self.conversation,
                )
                routed_status = routed.status.value
                routed_text = routed.text.strip()
                routed_trace = getattr(self.conversation, "active_trace", None)
                route_name = routed.decision.route_name or routed.decision.capability
                complexity_score = routed.decision.complexity_score
                route_reason = routed.decision.reason
                if routed.status is DelegationStatus.UNAVAILABLE:
                    elapsed_ms = round((monotonic() - started) * 1000.0, 1)
                    await self.relay.send_function_output(
                        call_id,
                        {
                            "status": "unavailable",
                            "result": routed.text,
                            "capability": routed.decision.capability,
                            "backend_ms": elapsed_ms,
                        },
                        response_overrides={
                            "max_output_tokens": DEFAULT_REALTIME_MAX_OUTPUT_TOKENS,
                            "instructions": CORE_RESULT_RESPONSE_INSTRUCTIONS,
                        },
                    )
                    event_bus.emit(
                        "voice.realtime.core.unavailable",
                        origin="openai-realtime-bridge",
                        conversation_id=context.conversation_id,
                        user_id=context.user_id,
                        device_id=context.device_id,
                        parent_event_id=received.event_id,
                        payload={
                            "call_id": call_id,
                            "mode": mode,
                            "capability": routed.decision.capability,
                            "route": route_name,
                        },
                    )
                    return
                result = routed
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
                trace=getattr(result, "trace", None),
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

        if routed_status == "completed" and routed_text:
            elapsed_ms = round((monotonic() - started) * 1000.0, 1)
            await self.relay.send_function_output(
                call_id,
                {
                    "status": "completed",
                    "result": routed_text,
                    "backend_ms": elapsed_ms,
                    "route": route_name,
                },
                response_overrides={
                    "max_output_tokens": DEFAULT_REALTIME_MAX_OUTPUT_TOKENS,
                    "instructions": CORE_RESULT_RESPONSE_INSTRUCTIONS,
                },
            )
            event_bus.emit(
                "voice.realtime.core.completed",
                origin="openai-realtime-bridge",
                trace=getattr(result, "trace", None),
                conversation_id=context.conversation_id,
                user_id=context.user_id,
                device_id=context.device_id,
                parent_event_id=received.event_id,
                payload={
                    "call_id": call_id,
                    "mode": mode,
                    "backend_ms": elapsed_ms,
                    "route": route_name,
                    "complexity_score": complexity_score,
                    "route_reason": route_reason,
                },
            )
            return

        await self.relay.send_function_output(
            call_id,
            {"status": routed_status, "result": routed_text, "route": route_name},
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
