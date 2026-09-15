"""Opaque identifiers shared by provider-neutral v2 contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CorrelationContext:
    """Trace identifiers that cross provider/tool/voice boundaries.

    Creation policy intentionally lives outside this 0.0.1 contract. The
    conversation core will own request/turn lifecycle semantics in 0.0.3.
    """

    correlation_id: str
    request_id: str
    turn_id: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("correlation_id", self.correlation_id),
            ("request_id", self.request_id),
        ):
            if not value or not value.strip():
                raise ValueError(f"{name} must be non-empty")
