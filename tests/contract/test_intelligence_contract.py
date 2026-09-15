import inspect
import unittest
from collections.abc import AsyncIterator, Sequence

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.intelligence import (
    ContextLimits,
    IntelligenceContext,
    IntelligenceEvent,
    IntelligenceEventType,
    IntelligenceProvider,
    ProviderHealth,
    ProviderHealthState,
    ProviderMetadata,
    ReasoningPolicy,
)
from core.tools import ToolDefinition


class FakeProvider(IntelligenceProvider):
    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(provider="fake", model="fake-model")

    async def stream_response(
        self,
        context: IntelligenceContext,
        tools: Sequence[ToolDefinition],
        reasoning_policy: ReasoningPolicy,
        cancellation_token: CancellationToken,
    ) -> AsyncIterator[IntelligenceEvent]:
        cancellation_token.raise_if_cancelled()
        yield IntelligenceEvent(IntelligenceEventType.TEXT_DELTA, text_delta="ok")
        yield IntelligenceEvent(IntelligenceEventType.COMPLETED)

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return False

    def supports_reasoning_levels(self) -> bool:
        return True

    def context_limits(self) -> ContextLimits:
        return ContextLimits(max_input_tokens=1000, max_output_tokens=100)

    async def cancel(self, request_id: str) -> None:
        return None

    async def health(self) -> ProviderHealth:
        return ProviderHealth(ProviderHealthState.HEALTHY)


class IntelligenceContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_fake_provider_satisfies_streaming_contract(self) -> None:
        provider = FakeProvider()
        context = IntelligenceContext(
            trace=CorrelationContext("corr-1", "req-1"),
            messages=({"role": "user", "content": "hello"},),
        )
        events = [
            event
            async for event in provider.stream_response(
                context,
                [ToolDefinition("example", "example tool")],
                ReasoningPolicy(),
                CancellationToken(),
            )
        ]
        self.assertEqual(events[0].text_delta, "ok")
        self.assertEqual(events[-1].event_type, IntelligenceEventType.COMPLETED)
        self.assertEqual(provider.metadata.provider, "fake")

    def test_contract_exposes_expected_provider_methods(self) -> None:
        names = {
            name
            for name, value in inspect.getmembers(IntelligenceProvider)
            if inspect.isfunction(value) or isinstance(value, property)
        }
        for required in {
            "stream_response",
            "supports_tools",
            "supports_vision",
            "supports_reasoning_levels",
            "context_limits",
            "cancel",
            "health",
            "metadata",
        }:
            self.assertIn(required, names)


if __name__ == "__main__":
    unittest.main()
