"""Authoritative conversation/context system for Jarvis Core v2."""

from .benchmark import ConversationBenchmarkResult, run_conversation_benchmark
from .engine import ConversationCore, TurnResult
from .events import CoreEvent, EventBus
from .persona import JARVIS_CONCISE_EXAMPLES, JARVIS_PERSONALITY_INSTRUCTIONS
from .models import (
    ConversationContext,
    HeardResponseState,
    InputChannel,
    Referent,
    ReferentKind,
    TranscriptEntry,
    TranscriptRole,
    VoiceInterruptionContext,
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
    "JARVIS_CONCISE_EXAMPLES",
    "JARVIS_PERSONALITY_INSTRUCTIONS",
    "Referent",
    "ReferentKind",
    "ReferentResolution",
    "ReferentResolver",
    "ResolutionStatus",
    "TranscriptEntry",
    "TranscriptRole",
    "TurnResult",
    "VoiceInterruptionContext",
    "run_conversation_benchmark",
]
