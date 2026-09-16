"""Deterministic Conversation Core behavioral benchmark cases."""

from __future__ import annotations

from dataclasses import dataclass

from core.common.cancellation import CancellationRegistry
from core.common.ids import CorrelationContext
from core.conversation.events import EventBus
from core.conversation.models import ConversationContext, Referent, ReferentKind
from core.conversation.referents import ReferentResolver, ResolutionStatus
from core.conversation.state_machine import CoreState, CoreStateMachine


@dataclass(frozen=True, slots=True)
class ConversationBenchmarkResult:
    name: str
    passed: bool
    detail: str = ""


def _fixtures() -> tuple[ConversationContext, Referent, Referent]:
    context = ConversationContext.create(user_id="benchmark-user")
    media = Referent(
        "media-youtube",
        ReferentKind.MEDIA,
        "YouTube video",
        source="media",
        supported_actions=frozenset({"pause", "resume"}),
    )
    task = Referent(
        "task-calendar",
        ReferentKind.TASK,
        "calendar morning task",
        source="tasks",
        supported_actions=frozenset({"pause", "resume", "cancel"}),
    )
    return context, media, task


def run_conversation_benchmark() -> tuple[ConversationBenchmarkResult, ...]:
    resolver = ReferentResolver()
    results: list[ConversationBenchmarkResult] = []

    context, media, task = _fixtures()
    context.set_active_media(media)
    context.set_active_task(task, focus=True)
    resolution = resolver.resolve(context, "it", action="resume")
    results.append(
        ConversationBenchmarkResult(
            "v1_resume_it_prefers_discussed_task",
            resolution.status is ResolutionStatus.RESOLVED and resolution.referent == task,
            resolution.reason,
        )
    )

    explicit = resolver.resolve(context, "the YouTube video", action="resume")
    results.append(
        ConversationBenchmarkResult(
            "explicit_media_outweighs_task_focus",
            explicit.status is ResolutionStatus.RESOLVED and explicit.referent == media,
            explicit.reason,
        )
    )

    ambiguous_context, media2, task2 = _fixtures()
    ambiguous_context.set_active_media(media2)
    ambiguous_context.set_active_task(task2)
    ambiguous_context.current_focus_entity = None
    ambiguous_context.last_discussed_entity = None
    ambiguous_context.recent_referents.clear()
    ambiguous = resolver.resolve(ambiguous_context, "it", action="resume")
    results.append(
        ConversationBenchmarkResult(
            "material_ambiguity_requests_clarification",
            ambiguous.status is ResolutionStatus.AMBIGUOUS and ambiguous.needs_clarification,
            ambiguous.reason,
        )
    )

    bus = EventBus()
    state_context = ConversationContext.create(user_id="benchmark-user")
    state = CoreStateMachine(state_context, bus, initial_state=CoreState.LISTENING)
    trace = CorrelationContext.create()
    state.transition(CoreState.THINKING, trace=trace)
    state.transition(CoreState.SPEAKING, trace=trace)
    state.transition(CoreState.LISTENING, trace=trace)
    results.append(
        ConversationBenchmarkResult(
            "foreground_state_round_trip",
            state.state is CoreState.LISTENING
            and sum(event.event_type == "core.state.changed" for event in bus.history) == 3,
        )
    )

    registry = CancellationRegistry()
    handle = registry.register(trace)
    cancelled = registry.cancel(handle.cancellation_id, "benchmark")
    results.append(
        ConversationBenchmarkResult(
            "cancellation_id_targets_one_turn",
            cancelled and handle.token.is_cancelled and handle.token.reason == "benchmark",
        )
    )
    registry.complete(handle.cancellation_id)

    snapshot_context, _, snapshot_task = _fixtures()
    snapshot_context.set_active_task(snapshot_task, focus=True)
    restored = ConversationContext.from_dict(snapshot_context.to_dict())
    results.append(
        ConversationBenchmarkResult(
            "context_snapshot_round_trip",
            restored.current_focus_entity is not None
            and restored.current_focus_entity.entity_id == snapshot_task.entity_id
            and restored.conversation_id == snapshot_context.conversation_id,
        )
    )
    return tuple(results)
