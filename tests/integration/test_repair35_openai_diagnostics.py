import unittest

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.intelligence import IntelligenceContext, IntelligenceEventType, ReasoningPolicy
from providers.intelligence.openai import OpenAIProvider, OpenAIProviderConfig
from tests.integration.test_openai_provider_adapter import (
    FakeWebSocketClient,
    event,
    response,
)


class Repair35OpenAIDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_second_websocket_turn_reports_incremental_continuation(self):
        completed1 = response("resp_diag_1", usage=None)
        completed1.service_tier = "default"
        completed2 = response("resp_diag_2", usage=None)
        completed2.service_tier = "priority"

        client = FakeWebSocketClient(
            [
                [
                    event("response.created", response=response("resp_diag_1")),
                    event("response.output_text.delta", delta="Hello."),
                    event("response.completed", response=completed1),
                ],
                [
                    event("response.created", response=response("resp_diag_2")),
                    event("response.output_text.delta", delta="Again."),
                    event("response.completed", response=completed2),
                ],
            ]
        )
        provider = OpenAIProvider(
            OpenAIProviderConfig(
                api_key="test",
                voice_transport="websocket",
                service_tier="fast",
            ),
            client=client,
        )
        metadata = {"input_channel": "voice", "conversation_id": "diag-conversation"}

        first_context = IntelligenceContext(
            trace=CorrelationContext.create(),
            messages=(
                {"role": "developer", "content": "Speak naturally."},
                {"role": "user", "content": "Hello"},
            ),
            metadata=metadata,
        )
        first_events = [
            item async for item in provider.stream_response(
                first_context, (), ReasoningPolicy(level="none"), CancellationToken()
            )
        ]
        first_diag = provider.request_diagnostics(first_context.trace.request_id)
        self.assertFalse(first_diag["continuation"])
        self.assertEqual(first_diag["input_items"], 2)
        self.assertEqual(first_diag["actual_service_tier"], "default")

        second_context = IntelligenceContext(
            trace=CorrelationContext.create(),
            messages=(
                {"role": "developer", "content": "Speak naturally."},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hello."},
                {"role": "user", "content": "Again"},
            ),
            metadata=metadata,
        )
        second_events = [
            item async for item in provider.stream_response(
                second_context, (), ReasoningPolicy(level="none"), CancellationToken()
            )
        ]
        second_diag = provider.request_diagnostics(second_context.trace.request_id)
        self.assertTrue(second_diag["continuation"])
        self.assertTrue(second_diag["connection_reused"])
        self.assertEqual(second_diag["input_items"], 1)
        self.assertEqual(second_diag["requested_service_tier"], "fast")
        self.assertEqual(second_diag["actual_service_tier"], "priority")
        self.assertEqual(first_events[-1].event_type, IntelligenceEventType.COMPLETED)
        self.assertEqual(second_events[-1].event_type, IntelligenceEventType.COMPLETED)
        await provider.close()


if __name__ == "__main__":
    unittest.main()
