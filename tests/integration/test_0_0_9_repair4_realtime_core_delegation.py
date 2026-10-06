from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace

from core.common.ids import CorrelationContext
from core.conversation import EventBus, TurnResult
from providers.voice_frontend.openai_realtime import BrowserRealtimeRelay, RealtimeCoreBridge


class FakeConversation:
    def __init__(self) -> None:
        self.active_trace = None
        self.event_bus = EventBus()
        self.context = SimpleNamespace(
            conversation_id="conversation-test",
            user_id="user-test",
            device_id="device-test",
        )
        self.submitted: list[str] = []
        self.cancel_reasons: list[str] = []

    async def submit_voice(self, text: str, *, reasoning_policy=None):
        self.submitted.append(text)
        return TurnResult(trace=CorrelationContext.create(), status="completed", text="Verified Core answer.")

    async def cancel_active_turn(self, reason: str = "user requested cancellation") -> bool:
        self.cancel_reasons.append(reason)
        self.active_trace = None
        return True


class BlockingConversation(FakeConversation):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def submit_voice(self, text: str, *, reasoning_policy=None):
        self.submitted.append(text)
        self.active_trace = CorrelationContext.create()
        trace = self.active_trace
        self.started.set()
        try:
            await self.release.wait()
        finally:
            self.active_trace = None
        return TurnResult(trace=trace, status="completed", text=f"Answer for {text}")

    async def cancel_active_turn(self, reason: str = "user requested cancellation") -> bool:
        self.cancel_reasons.append(reason)
        self.release.set()
        return True


async def drain_outgoing(relay: BrowserRealtimeRelay, count: int) -> list[dict]:
    result = []
    iterator = relay.outgoing()
    for _ in range(count):
        result.append(await asyncio.wait_for(anext(iterator), timeout=1.0))
    await iterator.aclose()
    return result


class Repair4RealtimeCoreDelegationTests(unittest.IsolatedAsyncioTestCase):
    async def test_realtime_function_call_routes_through_existing_conversation_core(self) -> None:
        relay = BrowserRealtimeRelay()
        conversation = FakeConversation()
        bridge = RealtimeCoreBridge(conversation=conversation, relay=relay)

        handled = await bridge.handle_event(
            {
                "type": "response.function_call_arguments.done",
                "name": "delegate_to_jarvis_core",
                "call_id": "call_123",
                "arguments": json.dumps({"request": "Check my project memory.", "mode": "memory"}),
            }
        )
        self.assertTrue(handled)
        await bridge.wait_idle()
        outgoing = await drain_outgoing(relay, 2)

        self.assertEqual(conversation.submitted, ["Check my project memory."])
        self.assertEqual(outgoing[0]["event"]["type"], "conversation.item.create")
        item = outgoing[0]["event"]["item"]
        self.assertEqual(item["type"], "function_call_output")
        self.assertEqual(item["call_id"], "call_123")
        decoded = json.loads(item["output"])
        self.assertEqual(decoded["status"], "completed")
        self.assertEqual(decoded["result"], "Verified Core answer.")
        self.assertEqual(outgoing[1]["event"]["type"], "response.create")
        event_types = [event.event_type for event in conversation.event_bus.history]
        self.assertIn("voice.realtime.core.requested", event_types)
        self.assertIn("voice.realtime.core.completed", event_types)
        await bridge.close()
        await relay.close()

    async def test_unrelated_realtime_events_are_not_treated_as_core_calls(self) -> None:
        relay = BrowserRealtimeRelay()
        conversation = FakeConversation()
        bridge = RealtimeCoreBridge(conversation=conversation, relay=relay)
        handled = await bridge.handle_event({"type": "response.done", "response": {"status": "completed"}})
        self.assertFalse(handled)
        self.assertEqual(conversation.submitted, [])
        await bridge.close()
        await relay.close()

    async def test_newer_core_delegation_supersedes_stale_result(self) -> None:
        relay = BrowserRealtimeRelay()
        conversation = BlockingConversation()
        bridge = RealtimeCoreBridge(conversation=conversation, relay=relay)
        await bridge.handle_event(
            {
                "type": "response.function_call_arguments.done",
                "name": "delegate_to_jarvis_core",
                "call_id": "old",
                "arguments": json.dumps({"request": "Do the old task", "mode": "reasoning"}),
            }
        )
        await conversation.started.wait()
        await bridge.handle_event(
            {
                "type": "response.function_call_arguments.done",
                "name": "delegate_to_jarvis_core",
                "call_id": "new",
                "arguments": json.dumps({"request": "Do the corrected task", "mode": "reasoning"}),
            }
        )
        await bridge.wait_idle()
        self.assertIn("superseded by newer realtime core delegation", conversation.cancel_reasons)
        self.assertEqual(conversation.submitted, ["Do the old task", "Do the corrected task"])
        event_types = [event.event_type for event in conversation.event_bus.history]
        self.assertIn("voice.realtime.core.superseded", event_types)
        await bridge.close()
        await relay.close()


if __name__ == "__main__":
    unittest.main()
