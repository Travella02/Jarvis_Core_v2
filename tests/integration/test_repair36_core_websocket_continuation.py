import unittest

from core.conversation import ConversationContext, ConversationCore
from core.intelligence import ReasoningPolicy
from providers.intelligence.openai import OpenAIProvider, OpenAIProviderConfig
from tests.integration.test_openai_provider_adapter import FakeWebSocketClient, event, response


class Repair36CoreWebSocketContinuationTests(unittest.IsolatedAsyncioTestCase):
    async def test_core_breaking_on_completed_still_commits_lane_before_yield(self):
        client = FakeWebSocketClient([
            [
                event("response.created", response=response("resp_core_1")),
                event("response.output_text.delta", delta="Ready."),
                event("response.completed", response=response("resp_core_1", usage=None)),
            ],
            [
                event("response.created", response=response("resp_core_2")),
                event("response.output_text.delta", delta="Again."),
                event("response.completed", response=response("resp_core_2", usage=None)),
            ],
        ])
        provider = OpenAIProvider(
            OpenAIProviderConfig(
                api_key="test",
                model="gpt-6-luna",
                voice_transport="websocket",
                service_tier="default",
            ),
            client=client,
        )
        core = ConversationCore(
            context=ConversationContext.create(
                user_id="repair36-user",
                speaker_id="repair36-speaker",
                device_id="repair36-device",
            ),
            provider=provider,
        )

        first = await core.submit_voice(
            "Say ready.",
            reasoning_policy=ReasoningPolicy(level="none", allow_escalation=False),
        )
        first_diag = provider.latest_request_diagnostics()
        self.assertEqual(first.status, "completed")
        self.assertFalse(first_diag["continuation"])
        self.assertEqual(first_diag["continuation_reason"], "no_lane")
        self.assertTrue(first_diag["lane_committed"])

        second = await core.submit_voice(
            "Say it again.",
            reasoning_policy=ReasoningPolicy(level="none", allow_escalation=False),
        )
        second_diag = provider.latest_request_diagnostics()
        self.assertEqual(second.status, "completed")
        self.assertTrue(second_diag["continuation"])
        self.assertEqual(second_diag["continuation_reason"], "exact_chain")
        self.assertTrue(second_diag["connection_reused"])
        self.assertEqual(second_diag["input_items"], 1)

        first_call, second_call = client.ws_connection.calls
        self.assertNotIn("previous_response_id", first_call)
        self.assertEqual(second_call["previous_response_id"], "resp_core_1")
        self.assertEqual(second_call["input"], [{"role": "user", "content": "Say it again."}])
        self.assertEqual(first_call["stream_id"], second_call["stream_id"])
        await provider.close()


if __name__ == "__main__":
    unittest.main()
