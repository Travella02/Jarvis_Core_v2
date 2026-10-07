import asyncio
import unittest

from core.common.ids import CorrelationContext
from core.intelligence import (
    ContextLimits,
    DelegationMode,
    DelegationOrchestrator,
    DelegationRequest,
    DelegationStatus,
    IntelligenceEvent,
    IntelligenceEventType,
    IntelligenceProvider,
    ProviderHealth,
    ProviderHealthState,
    ProviderMetadata,
)
from core.runtime import IntelligenceProviderRouter


class FakeProvider(IntelligenceProvider):
    def __init__(self, name: str):
        self.name = name
        self.cancelled = []

    async def stream_response(self, context, tools, reasoning_policy, cancellation_token):
        yield IntelligenceEvent(IntelligenceEventType.COMPLETED)

    def supports_tools(self): return True
    def supports_vision(self): return False
    def supports_reasoning_levels(self): return True
    def context_limits(self): return ContextLimits()
    async def cancel(self, request_id): self.cancelled.append(request_id)
    async def health(self): return ProviderHealth(ProviderHealthState.HEALTHY, "ready")
    @property
    def metadata(self): return ProviderMetadata("fake", self.name)


class FakeTurn:
    def __init__(self, text="backend result", status="completed"):
        self.trace = CorrelationContext.create()
        self.status = status
        self.text = text
        self.provider_response_id = "resp_test"
        self.detail = None


class FakeConversation:
    def __init__(self):
        self.calls = []

    async def submit_delegated(self, text, *, provider, reasoning_policy=None, tools=()):
        self.calls.append((text, provider.metadata.model, reasoning_policy.level, dict(reasoning_policy.metadata)))
        return FakeTurn()


class IntelligenceRouter012Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.router = IntelligenceProviderRouter(default_route="primary")
        self.primary = FakeProvider("luna")
        self.strong = FakeProvider("strong-model")
        self.router.register("primary", self.primary, make_default=True)

    def test_routine_reasoning_stays_on_default(self):
        orchestrator = DelegationOrchestrator(provider_router=self.router, default_route="primary")
        decision = orchestrator.plan(DelegationRequest("Explain idempotency simply."))
        self.assertEqual(decision.route_name, "primary")
        self.assertEqual(decision.reasoning_policy.level, "none")
        self.assertTrue(decision.available)

    def test_hard_reasoning_uses_strong_route_when_configured(self):
        self.router.register("strong", self.strong)
        orchestrator = DelegationOrchestrator(provider_router=self.router, default_route="primary")
        request = DelegationRequest(
            "Analyze this architecture, compare the tradeoffs, debug the root cause, and design a safer multi-step migration plan."
        )
        decision = orchestrator.plan(request)
        self.assertEqual(decision.route_name, "strong")
        self.assertGreaterEqual(decision.complexity_score, 2)
        self.assertEqual(decision.reasoning_policy.level, "low")

    def test_hard_reasoning_falls_back_truthfully_when_strong_route_absent(self):
        orchestrator = DelegationOrchestrator(provider_router=self.router, default_route="primary")
        request = DelegationRequest(
            "Analyze this architecture, compare the tradeoffs, debug the root cause, and design a safer multi-step migration plan."
        )
        decision = orchestrator.plan(request)
        self.assertEqual(decision.route_name, "primary")
        self.assertIn("unavailable", decision.reason)

    async def test_selected_provider_is_per_turn_and_owned_by_core(self):
        self.router.register("strong", self.strong)
        orchestrator = DelegationOrchestrator(provider_router=self.router, default_route="primary")
        conversation = FakeConversation()
        result = await orchestrator.execute(
            DelegationRequest(
                "Analyze this architecture, compare the tradeoffs, debug the root cause, and design a safer multi-step migration plan."
            ),
            conversation=conversation,
        )
        self.assertEqual(result.status, DelegationStatus.COMPLETED)
        self.assertEqual(conversation.calls[0][1], "strong-model")
        self.assertEqual(conversation.calls[0][2], "low")

    async def test_unimplemented_action_does_not_fall_through_to_model(self):
        orchestrator = DelegationOrchestrator(provider_router=self.router, default_route="primary")
        conversation = FakeConversation()
        result = await orchestrator.execute(
            DelegationRequest("Delete the file", mode=DelegationMode.ACTION),
            conversation=conversation,
        )
        self.assertEqual(result.status, DelegationStatus.UNAVAILABLE)
        self.assertEqual(conversation.calls, [])
        self.assertIn("not available", result.text)

    async def test_registered_capability_handler_can_own_non_model_work(self):
        orchestrator = DelegationOrchestrator(provider_router=self.router, default_route="primary")
        async def memory_handler(request):
            return f"memory:{request.goal}"
        orchestrator.register_capability(DelegationMode.MEMORY, memory_handler)
        result = await orchestrator.execute(
            DelegationRequest("project preference", mode=DelegationMode.MEMORY),
            conversation=FakeConversation(),
        )
        self.assertEqual(result.status, DelegationStatus.COMPLETED)
        self.assertEqual(result.text, "memory:project preference")

    def test_current_data_is_a_distinct_core_capability(self):
        orchestrator = DelegationOrchestrator(provider_router=self.router, default_route="primary")
        decision = orchestrator.plan(DelegationRequest("latest score", mode=DelegationMode.CURRENT_DATA))
        self.assertEqual(decision.capability, "current_data")
        self.assertFalse(decision.available)


if __name__ == "__main__":
    unittest.main()
