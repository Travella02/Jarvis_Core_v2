from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from core.conversation import EventBus
from providers.voice_frontend.openai_realtime import (
    BrowserRealtimeRelay,
    OpenAIRealtimeConfig,
    RealtimeCoreBridge,
    SLEEP_TOOL_NAME,
    build_realtime_session,
)


class FakeConversation:
    def __init__(self) -> None:
        self.active_trace = None
        self.event_bus = EventBus()
        self.context = SimpleNamespace(
            conversation_id="conversation-sleep",
            user_id="user-sleep",
            device_id="desktop-sleep",
        )
        self.submitted: list[str] = []

    async def submit_voice(self, text: str, *, reasoning_policy=None):
        self.submitted.append(text)
        raise AssertionError("sleep lifecycle must not delegate to backend intelligence")

    async def cancel_active_turn(self, reason: str = "user requested cancellation") -> bool:
        return False


class RealtimeSleepLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_session_exposes_sleep_as_lifecycle_tool_not_backend_reasoning(self) -> None:
        session = build_realtime_session(OpenAIRealtimeConfig(api_key="test-key"))
        names = {tool.get("name") for tool in session["tools"]}
        self.assertIn(SLEEP_TOOL_NAME, names)
        self.assertIn("delegate_to_jarvis_core", names)
        self.assertIn("local sleeping presence state", json.dumps(session["tools"]))

    async def test_sleep_tool_requests_browser_sleep_without_calling_core_model(self) -> None:
        relay = BrowserRealtimeRelay()
        conversation = FakeConversation()
        bridge = RealtimeCoreBridge(conversation=conversation, relay=relay)
        handled = await bridge.handle_event(
            {
                "type": "response.function_call_arguments.done",
                "name": SLEEP_TOOL_NAME,
                "call_id": "sleep-call",
                "arguments": json.dumps({"reason": "user_done"}),
            }
        )
        self.assertTrue(handled)
        outgoing = await anext(relay.outgoing())
        self.assertEqual(outgoing, {"kind": "lifecycle_command", "command": "sleep", "reason": "user_done"})
        self.assertEqual(conversation.submitted, [])
        event_types = [event.event_type for event in conversation.event_bus.history]
        self.assertIn("voice.presence.sleep_requested", event_types)
        await bridge.close()
        await relay.close()

    async def test_sleep_tool_defaults_reason_safely(self) -> None:
        relay = BrowserRealtimeRelay()
        conversation = FakeConversation()
        bridge = RealtimeCoreBridge(conversation=conversation, relay=relay)
        handled = await bridge.handle_event(
            {
                "type": "response.function_call_arguments.done",
                "name": SLEEP_TOOL_NAME,
                "call_id": "sleep-call",
                "arguments": "{}",
            }
        )
        self.assertTrue(handled)
        outgoing = await anext(relay.outgoing())
        self.assertEqual(outgoing["reason"], "explicit_sleep")
        await bridge.close()
        await relay.close()


if __name__ == "__main__":
    unittest.main()
