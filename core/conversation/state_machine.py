"""Authoritative foreground Core state machine."""

from __future__ import annotations

from enum import Enum

from core.common.ids import CorrelationContext
from core.conversation.events import EventBus
from core.conversation.models import ConversationContext


class CoreState(str, Enum):
    SLEEPING = "sleeping"
    WAKING = "waking"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    EXECUTING = "executing"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    BACKGROUND_WORK = "background_work"
    DEGRADED = "degraded"
    ERROR = "error"


class InvalidStateTransition(RuntimeError):
    pass


_ALLOWED: dict[CoreState, frozenset[CoreState]] = {
    CoreState.SLEEPING: frozenset({CoreState.WAKING, CoreState.DEGRADED, CoreState.ERROR}),
    CoreState.WAKING: frozenset({CoreState.LISTENING, CoreState.SLEEPING, CoreState.DEGRADED, CoreState.ERROR}),
    CoreState.LISTENING: frozenset({CoreState.THINKING, CoreState.SLEEPING, CoreState.BACKGROUND_WORK, CoreState.DEGRADED, CoreState.ERROR}),
    CoreState.THINKING: frozenset({CoreState.SPEAKING, CoreState.EXECUTING, CoreState.WAITING_FOR_APPROVAL, CoreState.LISTENING, CoreState.DEGRADED, CoreState.ERROR}),
    CoreState.SPEAKING: frozenset({CoreState.LISTENING, CoreState.THINKING, CoreState.EXECUTING, CoreState.WAITING_FOR_APPROVAL, CoreState.DEGRADED, CoreState.ERROR}),
    CoreState.EXECUTING: frozenset({CoreState.LISTENING, CoreState.SPEAKING, CoreState.WAITING_FOR_APPROVAL, CoreState.BACKGROUND_WORK, CoreState.DEGRADED, CoreState.ERROR}),
    CoreState.WAITING_FOR_APPROVAL: frozenset({CoreState.EXECUTING, CoreState.LISTENING, CoreState.SLEEPING, CoreState.DEGRADED, CoreState.ERROR}),
    CoreState.BACKGROUND_WORK: frozenset({CoreState.LISTENING, CoreState.THINKING, CoreState.SPEAKING, CoreState.EXECUTING, CoreState.DEGRADED, CoreState.ERROR}),
    CoreState.DEGRADED: frozenset({CoreState.LISTENING, CoreState.SLEEPING, CoreState.ERROR}),
    CoreState.ERROR: frozenset({CoreState.LISTENING, CoreState.SLEEPING, CoreState.DEGRADED}),
}


class CoreStateMachine:
    def __init__(
        self,
        context: ConversationContext,
        event_bus: EventBus,
        *,
        initial_state: CoreState,
    ) -> None:
        self.context = context
        self.event_bus = event_bus
        self._state = initial_state

    @property
    def state(self) -> CoreState:
        return self._state

    def can_transition(self, target: CoreState) -> bool:
        return target is self._state or target in _ALLOWED[self._state]

    def transition(
        self,
        target: CoreState,
        *,
        trace: CorrelationContext | None = None,
        reason: str | None = None,
    ) -> None:
        if target is self._state:
            return
        if not self.can_transition(target):
            raise InvalidStateTransition(f"{self._state.value} -> {target.value} is not allowed")
        previous = self._state
        self._state = target
        self.event_bus.emit(
            "core.state.changed",
            origin="conversation-core",
            trace=trace,
            conversation_id=self.context.conversation_id,
            user_id=self.context.user_id,
            device_id=self.context.device_id,
            payload={
                "from": previous.value,
                "to": target.value,
                "reason": reason,
            },
        )
