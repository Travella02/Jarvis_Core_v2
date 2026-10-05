"""Race-safe reconnect stream over the in-process runtime EventBus."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable

from core.conversation import CoreEvent
from core.runtime.models import RuntimeSnapshot
from core.runtime.runtime import JarvisRuntime


@dataclass(frozen=True, slots=True)
class RuntimeSync:
    snapshot: RuntimeSnapshot
    requested_after: int
    resume_accepted: bool
    reset_reason: str | None
    replay_events: tuple[CoreEvent, ...]


class RuntimeEventStream:
    """Bridge synchronous EventBus callbacks into one asyncio client queue.

    Subscription happens before the initial snapshot is captured. Events that
    race with reconnect are therefore either represented by the snapshot/replay
    watermark or buffered for live delivery; they cannot fall through a gap.
    """

    def __init__(
        self,
        runtime: JarvisRuntime,
        *,
        queue_limit: int = 256,
        max_replay_events: int = 512,
    ) -> None:
        if queue_limit <= 0:
            raise ValueError("queue_limit must be positive")
        if max_replay_events <= 0:
            raise ValueError("max_replay_events must be positive")
        self.runtime = runtime
        self.queue_limit = queue_limit
        self.max_replay_events = max_replay_events
        self._queue: asyncio.Queue[CoreEvent] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._unsubscribe: Callable[[], None] | None = None
        self._closed = False
        self._overflowed = False
        self._last_sequence = 0

    @property
    def overflowed(self) -> bool:
        return self._overflowed

    @property
    def last_sequence(self) -> int:
        return self._last_sequence

    def _enqueue_now(self, event: CoreEvent) -> None:
        if self._closed or self._queue is None:
            return
        if self._queue.full():
            self._overflowed = True
            return
        self._queue.put_nowait(event)

    def _on_event(self, event: CoreEvent) -> None:
        loop = self._loop
        if self._closed or loop is None:
            return
        try:
            loop.call_soon_threadsafe(self._enqueue_now, event)
        except RuntimeError:
            # Event loop is already closing. The transport will finalize the
            # stream; no callback should keep the runtime alive.
            return

    async def open(
        self,
        *,
        after_sequence: int = 0,
        expected_runtime_id: str | None = None,
    ) -> RuntimeSync:
        if self._unsubscribe is not None:
            raise RuntimeError("runtime event stream is already open")
        if after_sequence < 0:
            raise ValueError("after_sequence must be non-negative")
        expected = (expected_runtime_id or "").strip() or None

        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue(maxsize=self.queue_limit)
        self._unsubscribe = self.runtime.event_bus.subscribe("*", self._on_event)

        snapshot = self.runtime.snapshot()
        watermark = snapshot.event_cursor
        reset_reason: str | None = None
        replay: tuple[CoreEvent, ...] = ()

        if after_sequence > 0 and expected is None:
            reset_reason = "runtime-identity-required"
        elif expected is not None and expected != snapshot.runtime_id:
            reset_reason = "runtime-changed"
        elif after_sequence > watermark:
            reset_reason = "cursor-ahead"
        else:
            batch = self.runtime.events_after(after_sequence)
            replay_through_watermark = tuple(
                event for event in batch.events if event.sequence <= watermark
            )
            if batch.gap_detected:
                reset_reason = "history-gap"
            elif len(replay_through_watermark) > self.max_replay_events:
                reset_reason = "replay-limit"
            else:
                replay = replay_through_watermark

        self._last_sequence = watermark
        return RuntimeSync(
            snapshot=snapshot,
            requested_after=after_sequence,
            resume_accepted=reset_reason is None,
            reset_reason=reset_reason,
            replay_events=replay,
        )

    async def next_event(self) -> CoreEvent:
        queue = self._queue
        if self._closed or queue is None:
            raise RuntimeError("runtime event stream is not open")
        while True:
            event = await queue.get()
            # Events at/below the initial snapshot watermark are already covered
            # by the snapshot and optional replay.
            if event.sequence <= self._last_sequence:
                continue
            self._last_sequence = event.sequence
            return event

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        self._queue = None
        self._loop = None


__all__ = ["RuntimeEventStream", "RuntimeSync"]
