"""Minimal heard/unheard ledger skeleton for 0.0.4.

Full word/audio alignment is deliberately deferred to 0.0.5. 0.0.4 records
queued and physically written bytes so interruption work has an honest base.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PlaybackLedger:
    queued_bytes: int = 0
    played_bytes: int = 0
    interrupted: bool = False

    def queue(self, count: int) -> None:
        if count < 0:
            raise ValueError("count must be non-negative")
        self.queued_bytes += count

    def played(self, count: int) -> None:
        if count < 0:
            raise ValueError("count must be non-negative")
        self.played_bytes += count

    @property
    def unheard_bytes(self) -> int:
        return max(0, self.queued_bytes - self.played_bytes)

    def interrupt(self) -> None:
        self.interrupted = True
