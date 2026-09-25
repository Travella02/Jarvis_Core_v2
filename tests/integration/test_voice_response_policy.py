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
)


class CapturingProvider(IntelligenceProvider):
    def __init__(self):
        self.context = None
        self.policy = None

    @property
    def metadata(self): return ProviderMetadata("fake", "fake")
    def supports_tools(self): return False
    def supports_vision(self): return False
    def supports_reasoning_levels(self): return True
    def context_limits(self): return ContextLimits(1000, 1000)
    async def health(self): return ProviderHealth(ProviderHealthState.HEALTHY)
    async def cancel(self, request_id): return None

    async def stream_response(self, context, tools, reasoning_policy, cancellation_token):
        self.context = context
        self.policy = reasoning_policy
        yield IntelligenceEvent(IntelligenceEventType.TEXT_DELTA, text_delta="Short answer.")
        yield IntelligenceEvent(IntelligenceEventType.COMPLETED)


class VoiceResponsePolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_voice_turn_gets_concise_spoken_instruction_and_fastest_default(self):
        provider = CapturingProvider()
        core = ConversationCore(context=ConversationContext("conv", "user"), provider=provider)
        await core.submit_voice("Tell me something interesting")
        self.assertEqual(provider.policy.level, "none")
        self.assertFalse(provider.policy.allow_escalation)
        first = provider.context.messages[0]
        self.assertEqual(first["role"], "developer")
        self.assertIn("spoken Jarvis turn", first["content"])
        self.assertIn("one to three", first["content"])
        self.assertIn("first sentence short, complete", first["content"])
        self.assertEqual(provider.context.metadata["input_channel"], "voice")

    async def test_typed_turn_does_not_get_voice_only_instruction(self):
        provider = CapturingProvider()
        core = ConversationCore(context=ConversationContext("conv", "user"), provider=provider)
        await core.submit_typed("Hello")
        self.assertNotEqual(provider.context.messages[0]["role"], "developer")


if __name__ == "__main__":
    unittest.main()
