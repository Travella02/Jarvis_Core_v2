"""Opaque identifiers shared by provider-neutral v2 contracts."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4


def new_id(prefix: str) -> str:
    """Create an opaque, locally unique identifier with a readable type prefix."""

    normalized = prefix.strip().lower().replace("_", "-")
    if not normalized or any(not (char.isalnum() or char == "-") for char in normalized):
        raise ValueError("prefix must contain only letters, numbers, or hyphens")
    return f"{normalized}-{uuid4().hex}"


@dataclass(frozen=True, slots=True)
class CorrelationContext:
    """Trace identifiers that cross conversation/provider/tool/voice boundaries.

    Conversation Core owns lifecycle creation beginning in 0.0.3. The fields
    remain opaque to providers; adapters may log/echo them but must not derive
    authorization from them.
    """

    correlation_id: str
    request_id: str
    turn_id: str | None = None
    cancellation_id: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("correlation_id", self.correlation_id),
            ("request_id", self.request_id),
        ):
            if not value or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        for name, value in (
            ("turn_id", self.turn_id),
            ("cancellation_id", self.cancellation_id),
        ):
            if value is not None and not value.strip():
                raise ValueError(f"{name} must be non-empty when provided")

    @classmethod
    def create(cls) -> "CorrelationContext":
        """Create one trace bundle for a new foreground turn."""

        return cls(
            correlation_id=new_id("corr"),
            request_id=new_id("req"),
            turn_id=new_id("turn"),
            cancellation_id=new_id("cancel"),
        )
