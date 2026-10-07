import asyncio
import unittest

from core.conversation import ConversationContext, ConversationCore
from core.intelligence import (
    ContextLimits,
    IntelligenceEvent,
    IntelligenceEventType,
    IntelligenceProvider,
    ProviderHealth,
    ProviderHealthState,
    ProviderMetadata,
    ReasoningPolicy,
)


class FakeProvider(IntelligenceProvider):
    def __init__(self, model, *, slow=False):
        self.model = model
        self.slow = slow
        self.calls = 0
        self.cancelled = []
    async def stream_response(self, context, tools, reasoning_policy, cancellation_token):
        self.calls += 1
        if self.slow:
            while not cancellation_token.is_cancelled:
                await asyncio.sleep(0.001)
            yield IntelligenceEvent(IntelligenceEventType.CANCELLED, detail=cancellation_token.reason)
            return
        yield IntelligenceEvent(IntelligenceEventType.TEXT_DELTA, text_delta=self.model)
        yield IntelligenceEvent(IntelligenceEventType.COMPLETED)
    def supports_tools(self): return True
    def supports_vision(self): return False
    def supports_reasoning_levels(self): return True
    def context_limits(self): return ContextLimits()
    async def cancel(self, request_id): self.cancelled.append(request_id)
    async def health(self): return ProviderHealth(ProviderHealthState.HEALTHY)
    @property
    def metadata(self): return ProviderMetadata("fake", self.model)


class ConversationProviderOverride012Tests(unittest.IsolatedAsyncioTestCase):
    async def test_delegated_provider_override_is_per_turn_only(self):
        primary = FakeProvider("primary")
        strong = FakeProvider("strong")
        core = ConversationCore(context=ConversationContext("conv", "user"), provider=primary)
        routed = await core.submit_delegated(
            "hard delegated request",
            provider=strong,
            reasoning_policy=ReasoningPolicy(level="low"),
        )
        self.assertEqual(routed.text, "strong")
        normal = await core.submit_voice("normal request")
        self.assertEqual(normal.text, "primary")
        self.assertEqual(strong.calls, 1)
        self.assertEqual(primary.calls, 1)

    async def test_cancellation_targets_active_override_provider(self):
        primary = FakeProvider("primary")
        strong = FakeProvider("strong", slow=True)
        core = ConversationCore(context=ConversationContext("conv", "user"), provider=primary)
        task = asyncio.create_task(core.submit_delegated("long delegated request", provider=strong))
        for _ in range(100):
            if core.active_trace is not None:
                break
            await asyncio.sleep(0.001)
        trace = core.active_trace
        self.assertIsNotNone(trace)
        self.assertTrue(await core.cancel_active_turn("superseded"))
        result = await task
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(strong.cancelled, [trace.request_id])
        self.assertEqual(primary.cancelled, [])


if __name__ == "__main__":
    unittest.main()
