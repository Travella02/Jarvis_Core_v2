"""Monotonic latency telemetry for Voice Lab."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic_ns


@dataclass(slots=True)
class VoiceLatencyTrace:
    marks_ns: dict[str, int] = field(default_factory=dict)

    def mark(self, name: str, *, now_ns: int | None = None) -> None:
        if not name.strip():
            raise ValueError("latency mark name must be non-empty")
        self.marks_ns.setdefault(name, now_ns if now_ns is not None else monotonic_ns())

    def elapsed_ms(self, start: str, end: str) -> float | None:
        if start not in self.marks_ns or end not in self.marks_ns:
            return None
        return (self.marks_ns[end] - self.marks_ns[start]) / 1_000_000.0

    def as_milliseconds(self) -> dict[str, float]:
        if not self.marks_ns:
            return {}
        origin = min(self.marks_ns.values())
        return {
            name: round((value - origin) / 1_000_000.0, 3)
            for name, value in sorted(self.marks_ns.items(), key=lambda item: item[1])
        }
