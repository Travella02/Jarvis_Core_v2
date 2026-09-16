"""Provider-neutral cancellation primitives for Jarvis Core v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, RLock

from core.common.ids import CorrelationContext, new_id


class OperationCancelled(RuntimeError):
    """Raised when a cooperative operation observes cancellation."""


@dataclass(slots=True)
class CancellationToken:
    """Small thread-safe cancellation token shared across contract boundaries."""

    _event: Event = field(default_factory=Event, repr=False)
    _reason: str | None = field(default=None, init=False, repr=False)

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str | None:
        return self._reason

    def cancel(self, reason: str | None = None) -> None:
        if not self._event.is_set():
            self._reason = reason
            self._event.set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            message = "Operation cancelled"
            if self._reason:
                message = f"{message}: {self._reason}"
            raise OperationCancelled(message)


@dataclass(frozen=True, slots=True)
class CancellationHandle:
    """Conversation-owned cancellation identity plus its cooperative token."""

    cancellation_id: str
    request_id: str
    token: CancellationToken


class CancellationRegistry:
    """Tracks live cancellation handles by stable cancellation/request IDs.

    The registry is deliberately in-memory in 0.0.3. Durable task cancellation
    arrives with the task subsystem; this registry owns only active turn scopes.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._by_cancel_id: dict[str, CancellationHandle] = {}
        self._cancel_id_by_request: dict[str, str] = {}

    def register(self, trace: CorrelationContext) -> CancellationHandle:
        cancellation_id = trace.cancellation_id or new_id("cancel")
        handle = CancellationHandle(
            cancellation_id=cancellation_id,
            request_id=trace.request_id,
            token=CancellationToken(),
        )
        with self._lock:
            if cancellation_id in self._by_cancel_id:
                raise ValueError(f"Duplicate cancellation_id: {cancellation_id}")
            if trace.request_id in self._cancel_id_by_request:
                raise ValueError(f"Duplicate request_id: {trace.request_id}")
            self._by_cancel_id[cancellation_id] = handle
            self._cancel_id_by_request[trace.request_id] = cancellation_id
        return handle

    def get(self, cancellation_id: str) -> CancellationHandle | None:
        with self._lock:
            return self._by_cancel_id.get(cancellation_id)

    def get_for_request(self, request_id: str) -> CancellationHandle | None:
        with self._lock:
            cancellation_id = self._cancel_id_by_request.get(request_id)
            return self._by_cancel_id.get(cancellation_id) if cancellation_id else None

    def cancel(self, cancellation_id: str, reason: str | None = None) -> bool:
        handle = self.get(cancellation_id)
        if handle is None:
            return False
        handle.token.cancel(reason)
        return True

    def cancel_request(self, request_id: str, reason: str | None = None) -> bool:
        handle = self.get_for_request(request_id)
        if handle is None:
            return False
        handle.token.cancel(reason)
        return True

    def complete(self, cancellation_id: str) -> None:
        with self._lock:
            handle = self._by_cancel_id.pop(cancellation_id, None)
            if handle is not None:
                self._cancel_id_by_request.pop(handle.request_id, None)

    def active_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._by_cancel_id)
