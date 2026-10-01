"""Heard/unheard playback accounting for realtime voice."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PlaybackLedger:
    queued_bytes: int = 0
    played_bytes: int = 0
    queued_duration_ms: float = 0.0
    played_duration_ms: float = 0.0
    interrupted: bool = False

    def queue(self, count: int, *, duration_ms: float = 0.0) -> None:
        if count < 0 or duration_ms < 0:
            raise ValueError("queued playback counts/duration must be non-negative")
        self.queued_bytes += count
        self.queued_duration_ms += duration_ms

    def played(self, count: int, *, duration_ms: float = 0.0) -> None:
        if count < 0 or duration_ms < 0:
            raise ValueError("played playback counts/duration must be non-negative")
        self.played_bytes += count
        self.played_duration_ms += duration_ms

    @property
    def unheard_bytes(self) -> int:
        return max(0, self.queued_bytes - self.played_bytes)

    @property
    def heard_fraction(self) -> float:
        if self.queued_bytes <= 0:
            return 0.0
        return min(1.0, max(0.0, self.played_bytes / self.queued_bytes))

    def interrupt(self) -> None:
        self.interrupted = True
