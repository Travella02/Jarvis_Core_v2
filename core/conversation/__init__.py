"""Authoritative conversation/context system for Jarvis Core v2."""

from .benchmark import ConversationBenchmarkResult, run_conversation_benchmark
from .engine import ConversationCore, TurnResult
from .events import CoreEvent, EventBus
from .models import (
    ConversationContext,
    HeardResponseState,
    InputChannel,
    Referent,
    ReferentKind,
    TranscriptEntry,
    TranscriptRole,
)
from .referents import ReferentResolution, ReferentResolver, ResolutionStatus
from .state_machine import CoreState, CoreStateMachine, InvalidStateTransition

__all__ = [
    "ConversationBenchmarkResult",
    "ConversationContext",
    "ConversationCore",
    "CoreEvent",
    "CoreState",
    "CoreStateMachine",
    "EventBus",
    "HeardResponseState",
    "InputChannel",
    "InvalidStateTransition",
    "Referent",
    "ReferentKind",
    "ReferentResolution",
    "ReferentResolver",
    "ResolutionStatus",
    "TranscriptEntry",
    "TranscriptRole",
    "TurnResult",
    "run_conversation_benchmark",
]
