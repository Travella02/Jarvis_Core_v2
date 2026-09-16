"""In-process authoritative event bus for Jarvis Core v2."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
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
        timestamp = self.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        object.__setattr__(self, "timestamp", timestamp.astimezone(timezone.utc))
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


EventSubscriber = Callable[[CoreEvent], None]


class EventBus:
    """Small synchronous event bus with immutable bounded history.

    It is intentionally in-process for 0.0.3. Durable/event-stream transport is
    a later concern; Core owns event meaning now so voice/UI/tools can share it.
    """

    def __init__(self, *, history_limit: int = 512) -> None:
        if history_limit <= 0:
            raise ValueError("history_limit must be positive")
        self._history: deque[CoreEvent] = deque(maxlen=history_limit)
        self._subscribers: dict[str, list[EventSubscriber]] = defaultdict(list)
        self._lock = RLock()

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

    def publish(self, event: CoreEvent) -> None:
        with self._lock:
            self._history.append(event)
            callbacks = tuple(self._subscribers.get(event.event_type, ())) + tuple(
                self._subscribers.get("*", ())
            )
        for callback in callbacks:
            callback(event)

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
        self.publish(event)
        return event

    @property
    def history(self) -> tuple[CoreEvent, ...]:
        with self._lock:
            return tuple(self._history)
