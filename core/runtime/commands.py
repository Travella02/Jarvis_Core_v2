"""Authoritative runtime-side handling for client-submitted typed commands.

Clients may request work, retry a request after reconnect, and cancel a command they
submitted. They never create Conversation Core state or supply Jarvis trace IDs.
Those identities are generated on the Core side and returned only as correlation
handles for the client.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import TYPE_CHECKING

from core.common.ids import CorrelationContext, new_id
from core.runtime.events import RuntimeEventType

if TYPE_CHECKING:
    from core.conversation import ConversationCore
    from core.runtime.runtime import JarvisRuntime


class ClientCommandStatus(str, Enum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DEGRADED = "degraded"
    ERROR = "error"

    @property
    def terminal(self) -> bool:
        return self in {
            ClientCommandStatus.COMPLETED,
            ClientCommandStatus.CANCELLED,
            ClientCommandStatus.DEGRADED,
            ClientCommandStatus.ERROR,
        }


class ClientCommandError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(slots=True)
class ClientCommandRecord:
    command_id: str
    client_request_id: str
    client_id: str
    runtime_id: str
    conversation_id: str
    user_id: str
    device_id: str | None
    trace: CorrelationContext
    input_fingerprint: str
    status: ClientCommandStatus = ClientCommandStatus.ACCEPTED
    cancel_requested: bool = False
    result_status: str | None = None
    detail_code: str | None = None


@dataclass(frozen=True, slots=True)
class ClientCommandReceipt:
    record: ClientCommandRecord
    duplicate: bool = False


@dataclass(frozen=True, slots=True)
class ClientCancelReceipt:
    record: ClientCommandRecord
    accepted: bool
    duplicate: bool = False
    already_terminal: bool = False


def _clean_required(value: str, *, name: str, maximum: int) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ClientCommandError("invalid-request", f"{name} must be non-empty", status_code=400)
    if len(cleaned) > maximum:
        raise ClientCommandError(
            "invalid-request",
            f"{name} must be <= {maximum} characters",
            status_code=400,
        )
    return cleaned


def _fingerprint(*, conversation_id: str, text: str) -> str:
    payload = f"typed\0{conversation_id}\0{text}".encode("utf-8")
    return sha256(payload).hexdigest()


class RuntimeCommandGateway:
    """Bounded, reconnect-safe client request adapter over one JarvisRuntime.

    The gateway owns transport idempotency only. Conversation Core still owns
    transcript, activity state, provider routing, turn lifecycle, and cancellation.
    """

    def __init__(self, runtime: "JarvisRuntime", *, history_limit: int = 256) -> None:
        if history_limit < 16:
            raise ValueError("history_limit must be at least 16")
        self.runtime = runtime
        self.history_limit = history_limit
        self._records_by_request: OrderedDict[str, ClientCommandRecord] = OrderedDict()
        self._records_by_command: dict[str, ClientCommandRecord] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._active_command_id: str | None = None
        self._lock = asyncio.Lock()

    def _core(self) -> "ConversationCore":
        core = self.runtime.conversation
        if core is None:
            raise ClientCommandError(
                "conversation-unavailable",
                "runtime has no active conversation",
                status_code=409,
            )
        return core

    def _validate_authority(self, *, runtime_id: str, conversation_id: str) -> "ConversationCore":
        expected_runtime = _clean_required(runtime_id, name="runtime_id", maximum=200)
        expected_conversation = _clean_required(
            conversation_id,
            name="conversation_id",
            maximum=200,
        )
        if expected_runtime != self.runtime.runtime_id:
            raise ClientCommandError(
                "runtime-changed",
                "client command targets a different runtime",
                status_code=409,
            )
        core = self._core()
        if expected_conversation != core.context.conversation_id:
            raise ClientCommandError(
                "conversation-changed",
                "client command targets a different conversation",
                status_code=409,
            )
        return core

    def _emit(self, event_type: RuntimeEventType, record: ClientCommandRecord, **payload: object) -> None:
        core = self.runtime.conversation
        self.runtime.event_bus.emit(
            event_type.value,
            origin="runtime-client-command",
            trace=record.trace,
            conversation_id=record.conversation_id,
            user_id=record.user_id,
            device_id=record.device_id,
            payload={
                "command_id": record.command_id,
                "client_request_id": record.client_request_id,
                "client_id": record.client_id,
                "status": record.status.value,
                **payload,
            },
        )

    def _prune_locked(self) -> None:
        while len(self._records_by_request) > self.history_limit:
            request_id, record = next(iter(self._records_by_request.items()))
            if not record.status.terminal:
                break
            self._records_by_request.pop(request_id, None)
            self._records_by_command.pop(record.command_id, None)
            self._tasks.pop(record.command_id, None)

    async def submit_typed(
        self,
        *,
        runtime_id: str,
        conversation_id: str,
        client_request_id: str,
        client_id: str,
        text: str,
    ) -> ClientCommandReceipt:
        core = self._validate_authority(runtime_id=runtime_id, conversation_id=conversation_id)
        request_id = _clean_required(client_request_id, name="client_request_id", maximum=240)
        clean_client_id = _clean_required(client_id, name="client_id", maximum=120)
        clean_text = _clean_required(text, name="text", maximum=20_000)
        fingerprint = _fingerprint(conversation_id=core.context.conversation_id, text=clean_text)

        async with self._lock:
            existing = self._records_by_request.get(request_id)
            if existing is not None:
                if existing.input_fingerprint != fingerprint:
                    raise ClientCommandError(
                        "idempotency-conflict",
                        "client_request_id is already bound to different input",
                        status_code=409,
                    )
                self._records_by_request.move_to_end(request_id)
                return ClientCommandReceipt(existing, duplicate=True)

            if self._active_command_id is not None:
                active = self._records_by_command.get(self._active_command_id)
                if active is not None and not active.status.terminal:
                    raise ClientCommandError(
                        "foreground-busy",
                        "another client command is already active",
                        status_code=409,
                    )
                self._active_command_id = None

            # A voice or other in-process foreground turn remains authoritative.
            if core.active_trace is not None or core.state.state.value != "listening":
                raise ClientCommandError(
                    "foreground-busy",
                    "Conversation Core is already handling a foreground turn",
                    status_code=409,
                )

            trace = CorrelationContext.create()
            record = ClientCommandRecord(
                command_id=new_id("cmd"),
                client_request_id=request_id,
                client_id=clean_client_id,
                runtime_id=self.runtime.runtime_id,
                conversation_id=core.context.conversation_id,
                user_id=core.context.user_id,
                device_id=core.context.device_id,
                trace=trace,
                input_fingerprint=fingerprint,
            )
            self._records_by_request[request_id] = record
            self._records_by_command[record.command_id] = record
            self._active_command_id = record.command_id
            self._emit(RuntimeEventType.CLIENT_COMMAND_ACCEPTED, record)
            task = asyncio.create_task(self._run(record, clean_text), name=f"jarvis-{record.command_id}")
            self._tasks[record.command_id] = task
            self._prune_locked()
            return ClientCommandReceipt(record)

    async def _run(self, record: ClientCommandRecord, text: str) -> None:
        try:
            if record.cancel_requested:
                record.status = ClientCommandStatus.CANCELLED
                record.result_status = "cancelled"
                self._emit(RuntimeEventType.CLIENT_COMMAND_CANCELLED, record, phase="pre-start")
                return

            record.status = ClientCommandStatus.RUNNING
            self._emit(RuntimeEventType.CLIENT_COMMAND_STARTED, record)
            core = self._core()
            result = await core.submit_typed(text, _trace=record.trace)
            record.result_status = result.status
            if result.status == "completed":
                record.status = ClientCommandStatus.COMPLETED
                self._emit(
                    RuntimeEventType.CLIENT_COMMAND_COMPLETED,
                    record,
                    response_chars=len(result.text),
                )
            elif result.status == "cancelled":
                record.status = ClientCommandStatus.CANCELLED
                self._emit(RuntimeEventType.CLIENT_COMMAND_CANCELLED, record, phase="active")
            elif result.status == "degraded":
                record.status = ClientCommandStatus.DEGRADED
                record.detail_code = "provider-degraded"
                self._emit(RuntimeEventType.CLIENT_COMMAND_FAILED, record, reason="provider-degraded")
            else:
                record.status = ClientCommandStatus.ERROR
                record.detail_code = "turn-error"
                self._emit(RuntimeEventType.CLIENT_COMMAND_FAILED, record, reason="turn-error")
        except Exception as exc:
            record.status = ClientCommandStatus.ERROR
            record.result_status = "error"
            record.detail_code = type(exc).__name__
            self._emit(
                RuntimeEventType.CLIENT_COMMAND_FAILED,
                record,
                reason="execution-error",
                exception_type=type(exc).__name__,
            )
        finally:
            async with self._lock:
                if self._active_command_id == record.command_id:
                    self._active_command_id = None
                self._prune_locked()

    async def cancel(
        self,
        *,
        command_id: str,
        runtime_id: str,
        conversation_id: str,
        reason: str = "client requested cancellation",
    ) -> ClientCancelReceipt:
        core = self._validate_authority(runtime_id=runtime_id, conversation_id=conversation_id)
        clean_command_id = _clean_required(command_id, name="command_id", maximum=200)
        clean_reason = reason.strip()[:240] or "client requested cancellation"

        async with self._lock:
            record = self._records_by_command.get(clean_command_id)
            if record is None:
                raise ClientCommandError("command-not-found", "client command was not found", status_code=404)
            if record.conversation_id != core.context.conversation_id:
                raise ClientCommandError(
                    "conversation-changed",
                    "client command belongs to a different conversation",
                    status_code=409,
                )
            if record.status.terminal:
                return ClientCancelReceipt(record, accepted=False, already_terminal=True)
            if record.cancel_requested:
                return ClientCancelReceipt(record, accepted=True, duplicate=True)
            record.cancel_requested = True
            record.status = ClientCommandStatus.CANCELLING
            self._emit(RuntimeEventType.CLIENT_COMMAND_CANCEL_REQUESTED, record, reason=clean_reason)
            active_matches = (
                core.active_trace is not None
                and core.active_trace.request_id == record.trace.request_id
            )

        if active_matches:
            cancelled = await core.cancel_active_turn(clean_reason)
            return ClientCancelReceipt(record, accepted=cancelled)
        # The task may still be between acceptance and entering Conversation Core.
        return ClientCancelReceipt(record, accepted=True)

    async def get(self, command_id: str) -> ClientCommandRecord | None:
        clean = command_id.strip()
        if not clean:
            return None
        async with self._lock:
            return self._records_by_command.get(clean)

    async def wait(self, command_id: str, *, timeout: float = 10.0) -> ClientCommandRecord:
        async with self._lock:
            task = self._tasks.get(command_id)
            record = self._records_by_command.get(command_id)
        if record is None:
            raise ClientCommandError("command-not-found", "client command was not found", status_code=404)
        if task is not None:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        return record


def command_record_to_dict(record: ClientCommandRecord, *, duplicate: bool = False) -> dict[str, object]:
    return {
        "runtime_id": record.runtime_id,
        "conversation_id": record.conversation_id,
        "command_id": record.command_id,
        "client_request_id": record.client_request_id,
        "client_id": record.client_id,
        "status": record.status.value,
        "duplicate": duplicate,
        "trace": {
            "correlation_id": record.trace.correlation_id,
            "request_id": record.trace.request_id,
            "turn_id": record.trace.turn_id,
            "cancellation_id": record.trace.cancellation_id,
        },
        "result_status": record.result_status,
        "detail_code": record.detail_code,
    }


__all__ = [
    "ClientCancelReceipt",
    "ClientCommandError",
    "ClientCommandReceipt",
    "ClientCommandRecord",
    "ClientCommandStatus",
    "RuntimeCommandGateway",
    "command_record_to_dict",
]
