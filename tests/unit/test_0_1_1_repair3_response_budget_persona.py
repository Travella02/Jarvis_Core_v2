from __future__ import annotations

import asyncio
import unittest

from core.conversation.persona import JARVIS_PERSONALITY_INSTRUCTIONS
from providers.voice_frontend.openai_realtime.bridge import RealtimeCoreBridge
from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig
from providers.voice_frontend.openai_realtime.webrtc import (
    BrowserRealtimeRelay,
    DEFAULT_REALTIME_MAX_OUTPUT_TOKENS,
    EXPANDED_REALTIME_MAX_OUTPUT_TOKENS,
    EXPAND_RESPONSE_TOOL_NAME,
    build_realtime_session,
)


class _Context:
    conversation_id = "conv-test"
    user_id = "user-test"
    device_id = "device-test"


class _Events:
    def emit(self, *args, **kwargs):
        class E:
            event_id = "event-test"
        return E()


class _Conversation:
    active_trace = None
    event_bus = _Events()
    context = _Context()

    async def submit_voice(self, text, *, reasoning_policy=None):
        raise AssertionError("expanded budget must not call Core")

    async def cancel_active_turn(self, reason=""):
        return False


class ResponseBudgetPersonaTests(unittest.IsolatedAsyncioTestCase):
    def test_normal_realtime_session_has_non_clipping_guardrail(self) -> None:
        config = OpenAIRealtimeConfig(api_key="test")
        session = build_realtime_session(config)
        self.assertEqual(session["max_output_tokens"], 1024)
        self.assertEqual(DEFAULT_REALTIME_MAX_OUTPUT_TOKENS, 1024)

    def test_persona_has_smart_dry_wit_without_forcing_jokes(self) -> None:
        self.assertIn("exceptionally intelligent", JARVIS_PERSONALITY_INSTRUCTIONS)
        self.assertIn("dry, understated wit", JARVIS_PERSONALITY_INSTRUCTIONS)
        self.assertIn("Light sarcasm is welcome occasionally", JARVIS_PERSONALITY_INSTRUCTIONS)
        self.assertIn("Never force a joke", JARVIS_PERSONALITY_INSTRUCTIONS)

    async def test_expanded_response_tool_gets_larger_one_response_budget(self) -> None:
        relay = BrowserRealtimeRelay()
        bridge = RealtimeCoreBridge(conversation=_Conversation(), relay=relay)
        handled = await bridge.handle_event({
            "type": "response.function_call_arguments.done",
            "name": EXPAND_RESPONSE_TOOL_NAME,
            "call_id": "call-expand",
            "arguments": '{"reason":"user asked for detail"}',
        })
        self.assertTrue(handled)
        first = await anext(relay.outgoing())
        second = await anext(relay.outgoing())
        self.assertEqual(first["event"]["item"]["type"], "function_call_output")
        self.assertEqual(second["event"]["type"], "response.create")
        self.assertEqual(second["event"]["response"]["max_output_tokens"], EXPANDED_REALTIME_MAX_OUTPUT_TOKENS)
        self.assertEqual(EXPANDED_REALTIME_MAX_OUTPUT_TOKENS, 2048)
        await bridge.close()
        await relay.close()

    def test_expansion_tool_is_available_alongside_core_and_sleep_tools(self) -> None:
        session = build_realtime_session(OpenAIRealtimeConfig(api_key="test"))
        names = {tool["name"] for tool in session["tools"]}
        self.assertIn("delegate_to_jarvis_core", names)
        self.assertIn("sleep_jarvis", names)
        self.assertIn("request_expanded_response", names)


if __name__ == "__main__":
    unittest.main()
