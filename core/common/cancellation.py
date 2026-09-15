"""Provider-neutral cancellation primitive for Jarvis Core v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event


class OperationCancelled(RuntimeError):
    """Raised when a cooperative operation observes cancellation."""


@dataclass(slots=True)
class CancellationToken:
    """Small thread-safe cancellation token shared across contract boundaries.

    The token deliberately contains no provider SDK objects. Providers and future
    orchestration layers can cooperatively observe the same cancellation state.
    """

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
