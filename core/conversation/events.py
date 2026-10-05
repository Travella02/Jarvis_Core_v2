"""In-process authoritative event bus for Jarvis Core v2."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from threading import RLock
from types import MappingProxyType
from typing import Any

from core.common.ids import CorrelationContext, new_id


@dataclass(frozen=True, slots=True)
class CoreEvent:
    event_id: str
    event_type: str
    timestamp: datetime
    origin: str
    sequence: int = 0
    trace: CorrelationContext | None = None
    conversation_id: str | None = None
    user_id: str | None = None
    device_id: str | None = None
    task_id: str | None = None
    parent_event_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.event_type.strip() or not self.origin.strip():
            raise ValueError("event_id, event_type, and origin must be non-empty")
        if self.sequence < 0:
            raise ValueError("event sequence must be non-negative")
        timestamp = self.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        object.__setattr__(self, "timestamp", timestamp.astimezone(timezone.utc))
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


EventSubscriber = Callable[[CoreEvent], None]


class EventBus:
    """Small synchronous event bus with immutable bounded history.

    0.0.6 adds a monotonically increasing in-process sequence number and replay
    cursor helpers so a future local UI/API can reconnect without becoming a
    second state authority. The bus remains memory-only; durable event persistence
    is deliberately deferred until a redacted persistence boundary is designed.
    """

    def __init__(self, *, history_limit: int = 512) -> None:
        if history_limit <= 0:
            raise ValueError("history_limit must be positive")
        self._history: deque[CoreEvent] = deque(maxlen=history_limit)
        self._subscribers: dict[str, list[EventSubscriber]] = defaultdict(list)
        self._lock = RLock()
        self._next_sequence = 1

    def subscribe(self, event_type: str, callback: EventSubscriber) -> Callable[[], None]:
        if not event_type.strip():
            raise ValueError("event_type must be non-empty")
        with self._lock:
            self._subscribers[event_type].append(callback)

        def unsubscribe() -> None:
            with self._lock:
                callbacks = self._subscribers.get(event_type, [])
                if callback in callbacks:
                    callbacks.remove(callback)

        return unsubscribe

    def publish(self, event: CoreEvent) -> CoreEvent:
        with self._lock:
            if event.sequence == 0:
                event = replace(event, sequence=self._next_sequence)
                self._next_sequence += 1
            else:
                if event.sequence < self._next_sequence:
                    raise ValueError("event sequence must be monotonic")
                self._next_sequence = event.sequence + 1
            self._history.append(event)
            callbacks = tuple(self._subscribers.get(event.event_type, ())) + tuple(
                self._subscribers.get("*", ())
            )
        for callback in callbacks:
            callback(event)
        return event

    def emit(
        self,
        event_type: str,
        *,
        origin: str,
        trace: CorrelationContext | None = None,
        conversation_id: str | None = None,
        user_id: str | None = None,
        device_id: str | None = None,
        task_id: str | None = None,
        parent_event_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> CoreEvent:
        event = CoreEvent(
            event_id=new_id("event"),
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            origin=origin,
            trace=trace,
            conversation_id=conversation_id,
            user_id=user_id,
            device_id=device_id,
            task_id=task_id,
            parent_event_id=parent_event_id,
            payload=payload or {},
        )
        return self.publish(event)

    @property
    def history(self) -> tuple[CoreEvent, ...]:
        with self._lock:
            return tuple(self._history)

    @property
    def latest_sequence(self) -> int:
        with self._lock:
            return self._next_sequence - 1

    @property
    def oldest_sequence(self) -> int | None:
        with self._lock:
            return self._history[0].sequence if self._history else None

    def events_after(self, sequence: int, *, limit: int | None = None) -> tuple[CoreEvent, ...]:
        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        if limit is not None and limit <= 0:
            raise ValueError("limit must be positive when provided")
        with self._lock:
            items = tuple(event for event in self._history if event.sequence > sequence)
        return items if limit is None else items[:limit]

    def events_for_correlation(self, correlation_id: str) -> tuple[CoreEvent, ...]:
        value = correlation_id.strip()
        if not value:
            raise ValueError("correlation_id must be non-empty")
        with self._lock:
            return tuple(
                event
                for event in self._history
                if event.trace is not None and event.trace.correlation_id == value
            )
