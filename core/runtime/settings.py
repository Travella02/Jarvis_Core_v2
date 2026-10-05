"""Provider-neutral runtime settings.

Only non-secret orchestration settings belong here. Provider credentials remain in
provider adapters and are never surfaced in RuntimeSnapshot.
"""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


class RuntimeSettingsError(ValueError):
    pass


def _parse_env_file(path: str | Path | None) -> dict[str, str]:
    if path is None:
        return {}
    target = Path(path)
    if not target.is_file():
        return {}
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise RuntimeSettingsError(f"invalid runtime .env entry on line {line_number}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _parse_int(value: str, *, name: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeSettingsError(f"{name} must be an integer") from exc
    if not minimum <= parsed <= maximum:
        raise RuntimeSettingsError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _parse_float(value: str, *, name: str, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise RuntimeSettingsError(f"{name} must be a number") from exc
    if not minimum <= parsed <= maximum:
        raise RuntimeSettingsError(f"{name} must be between {minimum} and {maximum}")
    return parsed


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    environment: str = "development"
    default_intelligence_route: str = "primary"
    event_history_limit: int = 1024
    provider_health_timeout_seconds: float = 2.0
    api_host: str = "127.0.0.1"
    api_port: int = 8766
    api_event_queue_limit: int = 256
    api_max_replay_events: int = 512
    api_heartbeat_seconds: float = 15.0

    def __post_init__(self) -> None:
        if not self.environment.strip():
            raise RuntimeSettingsError("environment must be non-empty")
        if not self.default_intelligence_route.strip():
            raise RuntimeSettingsError("default_intelligence_route must be non-empty")
        if self.event_history_limit < 64:
            raise RuntimeSettingsError("event_history_limit must be at least 64")
        if self.provider_health_timeout_seconds <= 0:
            raise RuntimeSettingsError("provider_health_timeout_seconds must be positive")
        host = self.api_host.strip().lower()
        if not host:
            raise RuntimeSettingsError("api_host must be non-empty")
        if host != "localhost":
            try:
                address = ipaddress.ip_address(host)
            except ValueError as exc:
                raise RuntimeSettingsError("api_host must be localhost or a loopback IP") from exc
            if not address.is_loopback:
                raise RuntimeSettingsError(
                    "Runtime API is loopback-only; remote/device transport requires authenticated exposure"
                )
        if not 1 <= self.api_port <= 65535:
            raise RuntimeSettingsError("api_port must be between 1 and 65535")
        if self.api_event_queue_limit < 16:
            raise RuntimeSettingsError("api_event_queue_limit must be at least 16")
        if self.api_max_replay_events < 16:
            raise RuntimeSettingsError("api_max_replay_events must be at least 16")
        if self.api_heartbeat_seconds <= 0:
            raise RuntimeSettingsError("api_heartbeat_seconds must be positive")

    @classmethod
    def from_env(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        env_file: str | Path | None = None,
    ) -> "RuntimeSettings":
        # V1 lesson: an explicit test mapping is an overlay only when the caller
        # also explicitly opts into a file. We never silently read project .env.
        source = dict(os.environ if environment is None else environment)
        merged = _parse_env_file(env_file)
        merged.update({key: str(value) for key, value in source.items() if value is not None})

        defaults = cls()
        return cls(
            environment=(merged.get("JARVIS_ENV", defaults.environment).strip() or defaults.environment),
            default_intelligence_route=(
                merged.get("JARVIS_DEFAULT_INTELLIGENCE_ROUTE", defaults.default_intelligence_route).strip()
                or defaults.default_intelligence_route
            ),
            event_history_limit=_parse_int(
                merged.get("JARVIS_RUNTIME_EVENT_HISTORY", str(defaults.event_history_limit)),
                name="JARVIS_RUNTIME_EVENT_HISTORY",
                minimum=64,
                maximum=100_000,
            ),
            provider_health_timeout_seconds=_parse_float(
                merged.get(
                    "JARVIS_PROVIDER_HEALTH_TIMEOUT_SECONDS",
                    str(defaults.provider_health_timeout_seconds),
                ),
                name="JARVIS_PROVIDER_HEALTH_TIMEOUT_SECONDS",
                minimum=0.05,
                maximum=30.0,
            ),
            api_host=(merged.get("JARVIS_RUNTIME_API_HOST", defaults.api_host).strip() or defaults.api_host),
            api_port=_parse_int(
                merged.get("JARVIS_RUNTIME_API_PORT", str(defaults.api_port)),
                name="JARVIS_RUNTIME_API_PORT", minimum=1, maximum=65535,
            ),
            api_event_queue_limit=_parse_int(
                merged.get("JARVIS_RUNTIME_API_EVENT_QUEUE", str(defaults.api_event_queue_limit)),
                name="JARVIS_RUNTIME_API_EVENT_QUEUE", minimum=16, maximum=100_000,
            ),
            api_max_replay_events=_parse_int(
                merged.get("JARVIS_RUNTIME_API_MAX_REPLAY", str(defaults.api_max_replay_events)),
                name="JARVIS_RUNTIME_API_MAX_REPLAY", minimum=16, maximum=100_000,
            ),
            api_heartbeat_seconds=_parse_float(
                merged.get("JARVIS_RUNTIME_API_HEARTBEAT_SECONDS", str(defaults.api_heartbeat_seconds)),
                name="JARVIS_RUNTIME_API_HEARTBEAT_SECONDS", minimum=1.0, maximum=120.0,
            ),
        )

    def public_dict(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "environment": self.environment,
                "default_intelligence_route": self.default_intelligence_route,
                "event_history_limit": self.event_history_limit,
                "provider_health_timeout_seconds": self.provider_health_timeout_seconds,
                "api_host": self.api_host,
                "api_port": self.api_port,
                "api_event_queue_limit": self.api_event_queue_limit,
                "api_max_replay_events": self.api_max_replay_events,
                "api_heartbeat_seconds": self.api_heartbeat_seconds,
                "api_exposure": "loopback-only",
            }
        )


__all__ = ["RuntimeSettings", "RuntimeSettingsError"]
