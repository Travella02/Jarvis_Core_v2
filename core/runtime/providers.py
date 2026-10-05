"""Explicit provider routing for Jarvis Core v2.

0.0.6 deliberately does not silently escalate models, switch service tiers, or
fall back to another paid route. Selection is explicit so latency/cost policy can
be added later without surprising users.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType
from typing import Mapping

from core.intelligence import (
    IntelligenceProvider,
    ProviderHealth,
    ProviderHealthState,
    ProviderMetadata,
)


class ProviderRouteError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderRoute:
    name: str
    metadata: ProviderMetadata
    is_default: bool


class IntelligenceProviderRouter:
    def __init__(self, *, default_route: str | None = None) -> None:
        self._providers: dict[str, IntelligenceProvider] = {}
        self._default_route = default_route.strip() if default_route else None
        self._lock = RLock()

    @property
    def default_route(self) -> str | None:
        with self._lock:
            return self._default_route

    def register(
        self,
        name: str,
        provider: IntelligenceProvider,
        *,
        make_default: bool = False,
    ) -> None:
        route = name.strip()
        if not route:
            raise ProviderRouteError("provider route name must be non-empty")
        with self._lock:
            if route in self._providers:
                raise ProviderRouteError(f"provider route already registered: {route}")
            self._providers[route] = provider
            if make_default or self._default_route is None:
                self._default_route = route

    def set_default(self, name: str) -> None:
        route = name.strip()
        with self._lock:
            if route not in self._providers:
                raise ProviderRouteError(f"unknown provider route: {route}")
            self._default_route = route

    def resolve(
        self,
        name: str | None = None,
        *,
        require_tools: bool = False,
        require_vision: bool = False,
        require_reasoning_levels: bool = False,
    ) -> IntelligenceProvider:
        with self._lock:
            route = (name or self._default_route or "").strip()
            provider = self._providers.get(route)
        if provider is None:
            raise ProviderRouteError(f"unknown provider route: {route or '[unset]'}")
        if require_tools and not provider.supports_tools():
            raise ProviderRouteError(f"provider route {route!r} does not support tools")
        if require_vision and not provider.supports_vision():
            raise ProviderRouteError(f"provider route {route!r} does not support vision")
        if require_reasoning_levels and not provider.supports_reasoning_levels():
            raise ProviderRouteError(f"provider route {route!r} does not support reasoning levels")
        return provider

    def routes(self) -> tuple[ProviderRoute, ...]:
        with self._lock:
            default = self._default_route
            items = tuple(self._providers.items())
        return tuple(
            ProviderRoute(name=name, metadata=provider.metadata, is_default=name == default)
            for name, provider in items
        )

    async def health(
        self,
        *,
        timeout_seconds: float,
    ) -> Mapping[str, ProviderHealth]:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        with self._lock:
            items = tuple(self._providers.items())

        async def probe(name: str, provider: IntelligenceProvider) -> tuple[str, ProviderHealth]:
            try:
                result = await asyncio.wait_for(provider.health(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                result = ProviderHealth(
                    state=ProviderHealthState.DEGRADED,
                    detail=f"health probe exceeded {timeout_seconds:.2f}s",
                )
            except Exception as exc:  # adapters should not be able to crash runtime health
                result = ProviderHealth(
                    state=ProviderHealthState.DEGRADED,
                    detail=f"health probe failed: {type(exc).__name__}",
                )
            return name, result

        results = await asyncio.gather(*(probe(name, provider) for name, provider in items))
        return MappingProxyType(dict(results))


__all__ = ["IntelligenceProviderRouter", "ProviderRoute", "ProviderRouteError"]
