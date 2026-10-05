"""Central Jarvis Core runtime host.

The runtime owns process lifecycle, settings, provider routing, health projection,
and the shared EventBus. It intentionally does *not* collapse voice presence,
conversation activity, provider transport state, and runtime health into one enum.
Those are orthogonal authorities, which avoids a major class of V1 state bugs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from time import monotonic

from core.common.ids import new_id
from core.conversation import ConversationContext, ConversationCore, CoreEvent, EventBus
from core.intelligence import ProviderHealthState
from core.runtime.commands import RuntimeCommandGateway
from core.runtime.events import RuntimeEventType
from core.runtime.health import ComponentHealthState, HealthRegistry
from core.runtime.models import (
    ConversationProjection,
    EventBatch,
    RuntimeLifecycleState,
    RuntimeSnapshot,
)
from core.runtime.providers import IntelligenceProviderRouter
from core.runtime.settings import RuntimeSettings


_PROVIDER_HEALTH_MAP = {
    ProviderHealthState.HEALTHY: ComponentHealthState.HEALTHY,
    ProviderHealthState.CONFIGURED: ComponentHealthState.CONFIGURED,
    ProviderHealthState.DEGRADED: ComponentHealthState.DEGRADED,
    ProviderHealthState.UNAVAILABLE: ComponentHealthState.UNAVAILABLE,
    ProviderHealthState.NOT_CONFIGURED: ComponentHealthState.NOT_CONFIGURED,
}


class RuntimeLifecycleError(RuntimeError):
    pass


class JarvisRuntime:
    def __init__(
        self,
        *,
        settings: RuntimeSettings | None = None,
        provider_router: IntelligenceProviderRouter | None = None,
        event_bus: EventBus | None = None,
        health_registry: HealthRegistry | None = None,
        version: str | None = None,
    ) -> None:
        self.settings = settings or RuntimeSettings()
        self.event_bus = event_bus or EventBus(history_limit=self.settings.event_history_limit)
        self.provider_router = provider_router or IntelligenceProviderRouter(
            default_route=self.settings.default_intelligence_route
        )
        self.health = health_registry or HealthRegistry()
        self.runtime_id = new_id("runtime")
        self.version = version or self._read_version()
        self._lifecycle = RuntimeLifecycleState.STOPPED
        self._conversation: ConversationCore | None = None
        self._presence_by_conversation: dict[str, str] = {}
        self._started_at: datetime | None = None
        self._started_monotonic: float | None = None
        self._lock = RLock()
        self._unsubscribe = self.event_bus.subscribe("*", self._observe_event)
        self.client_commands = RuntimeCommandGateway(self)

    @staticmethod
    def _read_version() -> str:
        target = Path(__file__).resolve().parents[2] / "VERSION"
        try:
            return target.read_text(encoding="utf-8").strip()
        except OSError:
            return "unknown"

    @property
    def lifecycle(self) -> RuntimeLifecycleState:
        with self._lock:
            return self._lifecycle

    @property
    def conversation(self) -> ConversationCore | None:
        with self._lock:
            return self._conversation

    def _set_lifecycle(self, state: RuntimeLifecycleState, *, reason: str) -> None:
        with self._lock:
            previous = self._lifecycle
            if previous is state:
                return
            self._lifecycle = state
        self.event_bus.emit(
            RuntimeEventType.LIFECYCLE_CHANGED.value,
            origin="jarvis-runtime",
            payload={"from": previous.value, "to": state.value, "reason": reason},
        )

    def start(self) -> None:
        with self._lock:
            if self._lifecycle is RuntimeLifecycleState.RUNNING:
                return
            if self._lifecycle is not RuntimeLifecycleState.STOPPED:
                raise RuntimeLifecycleError(f"cannot start runtime from {self._lifecycle.value}")
        self._set_lifecycle(RuntimeLifecycleState.STARTING, reason="runtime start requested")
        with self._lock:
            self._started_at = datetime.now(timezone.utc)
            self._started_monotonic = monotonic()
        self.health.update("runtime", ComponentHealthState.HEALTHY, detail="runtime loop ready", critical=True)
        self.event_bus.emit(
            RuntimeEventType.SETTINGS_LOADED.value,
            origin="jarvis-runtime",
            payload=dict(self.settings.public_dict()),
        )
        self._set_lifecycle(RuntimeLifecycleState.RUNNING, reason="runtime ready")

    def stop(self) -> None:
        with self._lock:
            if self._lifecycle is RuntimeLifecycleState.STOPPED:
                return
            if self._lifecycle is not RuntimeLifecycleState.RUNNING:
                raise RuntimeLifecycleError(f"cannot stop runtime from {self._lifecycle.value}")
        self._set_lifecycle(RuntimeLifecycleState.STOPPING, reason="runtime stop requested")
        with self._lock:
            self._conversation = None
            self._presence_by_conversation.clear()
            self._started_at = None
            self._started_monotonic = None
        self._set_lifecycle(RuntimeLifecycleState.STOPPED, reason="runtime stopped")

    def close(self) -> None:
        try:
            if self.lifecycle is RuntimeLifecycleState.RUNNING:
                self.stop()
        finally:
            self._unsubscribe()

    def create_conversation(
        self,
        *,
        user_id: str,
        speaker_id: str | None = None,
        device_id: str | None = None,
        route_name: str | None = None,
    ) -> ConversationCore:
        if self.lifecycle is not RuntimeLifecycleState.RUNNING:
            raise RuntimeLifecycleError("runtime must be running before creating a conversation")
        with self._lock:
            if self._conversation is not None:
                raise RuntimeLifecycleError("runtime already owns an active conversation")
        provider = self.provider_router.resolve(route_name)
        context = ConversationContext.create(
            user_id=user_id,
            speaker_id=speaker_id,
            device_id=device_id,
        )
        core = ConversationCore(context=context, provider=provider, event_bus=self.event_bus)
        with self._lock:
            self._conversation = core
        self.event_bus.emit(
            RuntimeEventType.CONVERSATION_ATTACHED.value,
            origin="jarvis-runtime",
            conversation_id=context.conversation_id,
            user_id=context.user_id,
            device_id=context.device_id,
            payload={
                "provider": provider.metadata.provider,
                "model": provider.metadata.model,
                "route": route_name or self.provider_router.default_route,
            },
        )
        return core

    def detach_conversation(self, *, reason: str = "conversation detached") -> None:
        with self._lock:
            core = self._conversation
            self._conversation = None
        if core is None:
            return
        self.event_bus.emit(
            RuntimeEventType.CONVERSATION_DETACHED.value,
            origin="jarvis-runtime",
            conversation_id=core.context.conversation_id,
            user_id=core.context.user_id,
            device_id=core.context.device_id,
            payload={"reason": reason},
        )

    def _observe_event(self, event: CoreEvent) -> None:
        # Projection only. VoicePresenceState remains authoritative inside the
        # continuous voice session; runtime merely exposes the latest committed event.
        if event.event_type != "voice.presence.changed" or not event.conversation_id:
            return
        value = str(event.payload.get("to") or "").strip()
        if value:
            with self._lock:
                self._presence_by_conversation[event.conversation_id] = value

    async def refresh_provider_health(self) -> None:
        results = await self.provider_router.health(
            timeout_seconds=self.settings.provider_health_timeout_seconds
        )
        default_route = self.provider_router.default_route
        for route, provider_health in results.items():
            mapped = _PROVIDER_HEALTH_MAP[provider_health.state]
            component_name = f"intelligence:{route}"
            previous = self.health.get(component_name)
            critical = route == default_route
            changed = (
                previous is None
                or previous.state is not mapped
                or previous.detail != provider_health.detail
                or previous.critical != critical
            )
            self.health.update(
                component_name,
                mapped,
                detail=provider_health.detail,
                critical=critical,
            )
            if changed:
                provider = self.provider_router.resolve(route)
                self.event_bus.emit(
                    RuntimeEventType.PROVIDER_HEALTH.value,
                    origin="jarvis-runtime",
                    payload={
                        "route": route,
                        "provider": provider.metadata.provider,
                        "model": provider.metadata.model,
                        "state": provider_health.state.value,
                        "detail": provider_health.detail,
                        "critical": critical,
                    },
                )

    def snapshot(self) -> RuntimeSnapshot:
        with self._lock:
            core = self._conversation
            started_at = self._started_at
            started_monotonic = self._started_monotonic
            lifecycle = self._lifecycle
            presence = (
                self._presence_by_conversation.get(core.context.conversation_id)
                if core is not None
                else None
            )
        uptime_ms = (
            max(0.0, (monotonic() - started_monotonic) * 1000.0)
            if started_monotonic is not None
            else 0.0
        )
        projection = None
        if core is not None:
            active_trace = core.active_trace
            projection = ConversationProjection(
                conversation_id=core.context.conversation_id,
                activity_state=core.state.state.value,
                presence_state=presence,
                transcript_entries=len(core.context.recent_transcript),
                active_turn_id=active_trace.turn_id if active_trace is not None else None,
            )
        return RuntimeSnapshot(
            runtime_id=self.runtime_id,
            version=self.version,
            lifecycle=lifecycle,
            health=self.health.snapshot(),
            started_at=started_at,
            uptime_ms=uptime_ms,
            event_cursor=self.event_bus.latest_sequence,
            oldest_event_sequence=self.event_bus.oldest_sequence,
            settings=self.settings.public_dict(),
            conversation=projection,
        )

    def events_after(self, sequence: int, *, limit: int | None = None) -> EventBatch:
        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        events = self.event_bus.events_after(sequence, limit=limit)
        oldest = self.event_bus.oldest_sequence
        latest = self.event_bus.latest_sequence
        gap = oldest is not None and sequence < oldest - 1
        return EventBatch(
            after_sequence=sequence,
            latest_sequence=latest,
            oldest_available_sequence=oldest,
            gap_detected=gap,
            events=events,
        )


__all__ = ["JarvisRuntime", "RuntimeLifecycleError"]
