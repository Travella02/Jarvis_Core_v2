"""Provider-neutral delegation planning and execution for Jarvis Core v2.

Realtime and future conversational frontends may ask Core to handle a goal, but
never choose the concrete backend model/provider. This module owns that choice.
Capabilities that do not yet exist (durable memory, current-data tools, actions,
background tasks) fail truthfully instead of falling through to a language model
that could pretend the work happened.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Protocol

from core.intelligence.contracts import IntelligenceProvider, ReasoningPolicy


class DelegationMode(str, Enum):
    REASONING = "reasoning"
    MEMORY = "memory"
    ACTION = "action"
    CURRENT_DATA = "current_data"
    LONG_TASK = "long_task"


class DelegationStatus(str, Enum):
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DelegationRequest:
    goal: str
    mode: DelegationMode = DelegationMode.REASONING
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        clean = self.goal.strip()
        if not clean:
            raise ValueError("delegated goal must be non-empty")
        object.__setattr__(self, "goal", clean)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DelegationDecision:
    mode: DelegationMode
    capability: str
    route_name: str | None
    complexity_score: int
    reasoning_policy: ReasoningPolicy
    available: bool
    reason: str


@dataclass(frozen=True, slots=True)
class DelegationResult:
    status: DelegationStatus
    text: str
    decision: DelegationDecision
    provider_response_id: str | None = None
    detail: str | None = None


class ProviderResolver(Protocol):
    @property
    def default_route(self) -> str | None: ...

    def has_route(self, name: str) -> bool: ...

    def resolve(self, name: str | None = None, **requirements: Any) -> IntelligenceProvider: ...


class DelegatedConversation(Protocol):
    async def submit_delegated(
        self,
        text: str,
        *,
        provider: IntelligenceProvider,
        reasoning_policy: ReasoningPolicy | None = None,
    ): ...


CapabilityHandler = Callable[[DelegationRequest], Awaitable[str]]


_STRONG_SIGNALS = (
    "root cause",
    "tradeoff",
    "trade-off",
    "architecture",
    "debug",
    "analyze",
    "analyse",
    "compare",
    "design",
    "optimize",
    "optimise",
    "multi-step",
    "codebase",
    "reason through",
    "reason deeply",
    "prove",
)


class DelegationOrchestrator:
    """Plan delegated work and keep backend provider choice inside Core."""

    def __init__(
        self,
        *,
        provider_router: ProviderResolver,
        default_route: str | None = None,
        strong_route: str = "strong",
        strong_threshold: int = 2,
        strong_reasoning_level: str = "low",
    ) -> None:
        if strong_threshold < 1:
            raise ValueError("strong_threshold must be at least 1")
        self.provider_router = provider_router
        self.default_route = (default_route or provider_router.default_route or "").strip()
        if not self.default_route:
            raise ValueError("delegation default route must be configured")
        self.strong_route = strong_route.strip() or "strong"
        self.strong_threshold = strong_threshold
        self.strong_reasoning_level = strong_reasoning_level.strip() or "low"
        self._handlers: dict[DelegationMode, CapabilityHandler] = {}

    def register_capability(self, mode: DelegationMode, handler: CapabilityHandler) -> None:
        if mode is DelegationMode.REASONING:
            raise ValueError("reasoning is provider-routed, not a capability handler")
        self._handlers[mode] = handler

    @staticmethod
    def complexity_score(goal: str) -> int:
        text = goal.strip().lower()
        words = text.split()
        score = 0
        if len(words) >= 90:
            score += 1
        if len(text) >= 700:
            score += 1
        signal_hits = sum(1 for signal in _STRONG_SIGNALS if signal in text)
        if signal_hits >= 1:
            score += 1
        if signal_hits >= 3:
            score += 1
        return score

    def plan(self, request: DelegationRequest) -> DelegationDecision:
        if request.mode is not DelegationMode.REASONING:
            available = request.mode in self._handlers
            reason = (
                f"registered Core capability: {request.mode.value}"
                if available
                else f"Core capability not implemented yet: {request.mode.value}"
            )
            return DelegationDecision(
                mode=request.mode,
                capability=request.mode.value,
                route_name=None,
                complexity_score=0,
                reasoning_policy=ReasoningPolicy(level="none", allow_escalation=False),
                available=available,
                reason=reason,
            )

        score = self.complexity_score(request.goal)
        use_strong = score >= self.strong_threshold and self.provider_router.has_route(self.strong_route)
        route = self.strong_route if use_strong else self.default_route
        level = self.strong_reasoning_level if use_strong else "none"
        reason = (
            f"complexity score {score} met strong threshold {self.strong_threshold}"
            if use_strong
            else (
                f"strong route unavailable; using default route at complexity score {score}"
                if score >= self.strong_threshold
                else f"routine delegated reasoning at complexity score {score}"
            )
        )
        return DelegationDecision(
            mode=request.mode,
            capability="intelligence",
            route_name=route,
            complexity_score=score,
            reasoning_policy=ReasoningPolicy(
                level=level,
                allow_escalation=False,
                metadata={"delegation_mode": request.mode.value, "route": route, "complexity_score": score},
            ),
            available=True,
            reason=reason,
        )

    async def execute(self, request: DelegationRequest, *, conversation: DelegatedConversation) -> DelegationResult:
        decision = self.plan(request)
        if not decision.available:
            return DelegationResult(
                status=DelegationStatus.UNAVAILABLE,
                text=self._unavailable_message(request.mode),
                decision=decision,
            )

        if request.mode is not DelegationMode.REASONING:
            try:
                text = (await self._handlers[request.mode](request)).strip()
            except Exception as exc:
                return DelegationResult(
                    status=DelegationStatus.FAILED,
                    text="",
                    decision=decision,
                    detail=type(exc).__name__,
                )
            return DelegationResult(
                status=DelegationStatus.COMPLETED,
                text=text,
                decision=decision,
            )

        provider = self.provider_router.resolve(decision.route_name)
        turn = await conversation.submit_delegated(
            request.goal,
            provider=provider,
            reasoning_policy=decision.reasoning_policy,
        )
        try:
            status = DelegationStatus(turn.status)
        except ValueError:
            status = DelegationStatus.FAILED
        return DelegationResult(
            status=status,
            text=turn.text.strip(),
            decision=decision,
            provider_response_id=getattr(turn, "provider_response_id", None),
            detail=getattr(turn, "detail", None),
        )

    @staticmethod
    def _unavailable_message(mode: DelegationMode) -> str:
        messages = {
            DelegationMode.MEMORY: "Durable memory retrieval is not available in this Jarvis build yet.",
            DelegationMode.ACTION: "That action capability is not available in this Jarvis build yet.",
            DelegationMode.CURRENT_DATA: "A current-data lookup capability is not available in this Jarvis build yet.",
            DelegationMode.LONG_TASK: "Durable background tasks are not available in this Jarvis build yet.",
        }
        return messages.get(mode, "That Core capability is not available yet.")


__all__ = [
    "DelegationDecision",
    "DelegationMode",
    "DelegationOrchestrator",
    "DelegationRequest",
    "DelegationResult",
    "DelegationStatus",
]
