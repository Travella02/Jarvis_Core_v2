"""Runtime/component health projection for Jarvis Core v2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from types import MappingProxyType
from typing import Mapping


class ComponentHealthState(str, Enum):
    HEALTHY = "healthy"
    CONFIGURED = "configured"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not-configured"
    UNKNOWN = "unknown"


class RuntimeHealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    name: str
    state: ComponentHealthState
    detail: str | None = None
    critical: bool = False
    updated_at: datetime = datetime.min.replace(tzinfo=timezone.utc)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("component health name must be non-empty")
        timestamp = self.updated_at
        if timestamp == datetime.min.replace(tzinfo=timezone.utc):
            timestamp = datetime.now(timezone.utc)
        elif timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        object.__setattr__(self, "updated_at", timestamp.astimezone(timezone.utc))


@dataclass(frozen=True, slots=True)
class HealthSnapshot:
    state: RuntimeHealthState
    components: Mapping[str, ComponentHealth]

    def __post_init__(self) -> None:
        object.__setattr__(self, "components", MappingProxyType(dict(self.components)))


class HealthRegistry:
    def __init__(self) -> None:
        self._components: dict[str, ComponentHealth] = {}
        self._lock = RLock()

    def update(
        self,
        name: str,
        state: ComponentHealthState,
        *,
        detail: str | None = None,
        critical: bool = False,
    ) -> ComponentHealth:
        item = ComponentHealth(
            name=name,
            state=state,
            detail=detail,
            critical=critical,
            updated_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._components[name] = item
        return item

    def get(self, name: str) -> ComponentHealth | None:
        with self._lock:
            return self._components.get(name)

    def snapshot(self) -> HealthSnapshot:
        with self._lock:
            components = dict(self._components)
        if not components:
            return HealthSnapshot(RuntimeHealthState.UNKNOWN, components)

        critical_unavailable = any(
            item.critical and item.state is ComponentHealthState.UNAVAILABLE
            for item in components.values()
        )
        if critical_unavailable:
            state = RuntimeHealthState.ERROR
        elif any(
            item.state
            in {
                ComponentHealthState.DEGRADED,
                ComponentHealthState.UNAVAILABLE,
                ComponentHealthState.NOT_CONFIGURED,
                ComponentHealthState.UNKNOWN,
            }
            for item in components.values()
        ):
            state = RuntimeHealthState.DEGRADED
        else:
            state = RuntimeHealthState.HEALTHY
        return HealthSnapshot(state, components)


__all__ = [
    "ComponentHealth",
    "ComponentHealthState",
    "HealthRegistry",
    "HealthSnapshot",
    "RuntimeHealthState",
]
