import unittest

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.intelligence import IntelligenceContext, ReasoningPolicy
from providers.intelligence.openai import OpenAIProvider, OpenAIProviderConfig
from tests.integration.test_openai_provider_adapter import (
    FakeWebSocketClient,
    event,
    response,
)


class InterruptionContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_websocket_continuation_adds_playback_note_without_losing_chain(self):
        client = FakeWebSocketClient(
            [
                [
                    event("response.created", response=response("resp_1")),
                    event("response.output_text.delta", delta="First full answer."),
                    event("response.completed", response=response("resp_1", usage=None)),
                ],
                [
                    event("response.created", response=response("resp_2")),
                    event("response.output_text.delta", delta="Follow-up."),
                    event("response.completed", response=response("resp_2", usage=None)),
                ],
            ]
        )
        provider = OpenAIProvider(
            OpenAIProviderConfig(
                api_key="test",
                model="gpt-6-luna",
                voice_transport="websocket",
                service_tier="default",
            ),
            client=client,
        )
        metadata = {"input_channel": "voice", "conversation_id": "interrupt-conv"}
        first_messages = (
            {"role": "developer", "content": "Speak naturally."},
            {"role": "user", "content": "Explain Venus."},
        )
        first = IntelligenceContext(
            trace=CorrelationContext.create(),
            messages=first_messages,
            metadata=metadata,
        )
        _ = [
            item async for item in provider.stream_response(
                first, (), ReasoningPolicy(level="none"), CancellationToken()
            )
        ]

        second = IntelligenceContext(
            trace=CorrelationContext.create(),
            messages=(
                *first_messages,
                {"role": "assistant", "content": "First full answer."},
                {"role": "user", "content": "Okay, but why?"},
            ),
            metadata={
                **metadata,
                "voice_interruption": {
                    "response_turn_id": "turn-1",
                    "generated_text": "First full answer.",
                    "heard_text": "First full",
                    "playback_ms": 820.0,
                    "played_bytes": 100,
                    "queued_bytes": 200,
                    "alignment_method": "pcm-fraction",
                },
            },
        )
        _ = [
            item async for item in provider.stream_response(
                second, (), ReasoningPolicy(level="none"), CancellationToken()
            )
        ]

        second_call = client.ws_connection.calls[1]
        self.assertEqual(second_call["previous_response_id"], "resp_1")
        self.assertEqual(len(second_call["input"]), 2)
        self.assertEqual(second_call["input"][0]["role"], "developer")
        self.assertIn("user interrupted your previous turn", second_call["input"][0]["content"])
        self.assertIn("during the speaking phase", second_call["input"][0]["content"])
        self.assertIn("820 ms", second_call["input"][0]["content"])
        self.assertEqual(second_call["input"][1], {"role": "user", "content": "Okay, but why?"})
        diag = provider.latest_request_diagnostics()
        self.assertTrue(diag["continuation"])
        self.assertEqual(diag["continuation_reason"], "exact_chain")
        self.assertTrue(diag["interruption_context"])
        self.assertEqual(diag["input_items"], 2)
        await provider.close()


if __name__ == "__main__":
    unittest.main()
