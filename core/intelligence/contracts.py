"""Provider-independent intelligence contracts for Jarvis Core v2."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.tools import ToolDefinition, ToolRequest


class ProviderHealthState(str, Enum):
    HEALTHY = "healthy"
    CONFIGURED = "configured"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not-configured"


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    provider: str
    model: str
    model_snapshot: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    tools: bool = False
    vision: bool = False
    reasoning_levels: bool = False


@dataclass(frozen=True, slots=True)
class ContextLimits:
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    state: ProviderHealthState
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class ReasoningPolicy:
    """Provider-neutral policy hint; routing semantics arrive in milestone 0.0.6."""

    level: str = "auto"
    allow_escalation: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class IntelligenceContext:
    """Opaque provider-neutral context envelope.

    The authoritative ConversationContext itself is intentionally deferred to
    0.0.3. Providers receive a serializable snapshot through this boundary.
    """

    trace: CorrelationContext
    messages: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        frozen_messages = tuple(MappingProxyType(dict(item)) for item in self.messages)
        object.__setattr__(self, "messages", frozen_messages)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class IntelligenceEventType(str, Enum):
    TEXT_DELTA = "text_delta"
    TOOL_REQUEST = "tool_request"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DEGRADED = "degraded"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class IntelligenceEvent:
    event_type: IntelligenceEventType
    text_delta: str | None = None
    tool_request: ToolRequest | None = None
    detail: str | None = None
    provider_response_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class IntelligenceProvider(ABC):
    """Replaceable cloud/local intelligence provider contract."""

    @abstractmethod
    async def stream_response(
        self,
        context: IntelligenceContext,
        tools: Sequence[ToolDefinition],
        reasoning_policy: ReasoningPolicy,
        cancellation_token: CancellationToken,
    ) -> AsyncIterator[IntelligenceEvent]:
        """Stream provider-neutral events for one intelligence request."""
        raise NotImplementedError

    @abstractmethod
    def supports_tools(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def supports_vision(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def supports_reasoning_levels(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def context_limits(self) -> ContextLimits:
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, request_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def health(self) -> ProviderHealth:
        raise NotImplementedError

    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError
