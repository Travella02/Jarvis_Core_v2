"""Serializable runtime snapshots and reconnect batches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from core.conversation import CoreEvent
from core.runtime.health import HealthSnapshot


class RuntimeLifecycleState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


@dataclass(frozen=True, slots=True)
class ConversationProjection:
    conversation_id: str
    activity_state: str
    presence_state: str | None
    transcript_entries: int
    active_turn_id: str | None


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    runtime_id: str
    version: str
    lifecycle: RuntimeLifecycleState
    health: HealthSnapshot
    started_at: datetime | None
    uptime_ms: float
    event_cursor: int
    oldest_event_sequence: int | None
    settings: Mapping[str, object]
    conversation: ConversationProjection | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "settings", MappingProxyType(dict(self.settings)))
        if self.started_at is not None:
            timestamp = self.started_at
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            object.__setattr__(self, "started_at", timestamp.astimezone(timezone.utc))


@dataclass(frozen=True, slots=True)
class EventBatch:
    after_sequence: int
    latest_sequence: int
    oldest_available_sequence: int | None
    gap_detected: bool
    events: tuple[CoreEvent, ...]


__all__ = [
    "ConversationProjection",
    "EventBatch",
    "RuntimeLifecycleState",
    "RuntimeSnapshot",
]
