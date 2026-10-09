from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from core.common.ids import CorrelationContext
from core.conversation.events import EventBus
from core.intelligence import (
    ContextLimits,
    DelegationOrchestrator,
    IntelligenceEvent,
    IntelligenceEventType,
    IntelligenceProvider,
    ProviderHealth,
    ProviderHealthState,
    ProviderMetadata,
)
from core.runtime import IntelligenceProviderRouter
from providers.voice_frontend.openai_realtime.bridge import RealtimeCoreBridge
from providers.voice_frontend.openai_realtime.webrtc import ROUTE_TURN_TOOL_NAME


class FakeProvider(IntelligenceProvider):
    async def stream_response(self, context, tools, reasoning_policy, cancellation_token):
        yield IntelligenceEvent(IntelligenceEventType.TEXT_DELTA, text="core answer")
        yield IntelligenceEvent(IntelligenceEventType.COMPLETED)
    def supports_tools(self): return True
    def supports_vision(self): return False
    def supports_reasoning_levels(self): return True
    def context_limits(self): return ContextLimits()
    async def cancel(self, request_id): return None
    async def health(self): return ProviderHealth(ProviderHealthState.HEALTHY)
    @property
    def metadata(self): return ProviderMetadata("fake", "luna")


class FakeContext:
    conversation_id = "conversation"
    user_id = "user"
    device_id = "desktop"


class FakeTurn:
    def __init__(self, text="core answer"):
        self.trace = CorrelationContext.create()
        self.status = "completed"
        self.text = text
        self.provider_response_id = "resp_backend"
        self.detail = None


class FakeConversation:
    def __init__(self):
        self.active_trace = None
        self.event_bus = EventBus()
        self.context = FakeContext()
        self.calls = []
    async def cancel_active_turn(self, reason="cancelled"):
        return False
    async def submit_voice(self, text, *, reasoning_policy=None):
        self.calls.append(("legacy", text))
        return FakeTurn()
    async def submit_delegated(self, text, *, provider, reasoning_policy=None, tools=()):
        self.calls.append(("delegated", text, provider.metadata.model))
        return FakeTurn("core answer")


class FakeRelay:
    def __init__(self):
        self.outputs = []
        self.sleep_reasons = []
    async def send_function_output(self, call_id, output, continue_response=True, response_overrides=None):
        self.outputs.append((call_id, output, continue_response, response_overrides))
    async def request_browser_sleep(self, *, reason):
        self.sleep_reasons.append(reason)


class Repair4RouteTelemetryTests(unittest.IsolatedAsyncioTestCase):
    def make_bridge(self):
        router = IntelligenceProviderRouter(default_route="primary")
        router.register("primary", FakeProvider(), make_default=True)
        orchestrator = DelegationOrchestrator(provider_router=router, default_route="primary")
        conversation = FakeConversation()
        relay = FakeRelay()
        bridge = RealtimeCoreBridge(
            conversation=conversation,
            relay=relay,
            delegation_orchestrator=orchestrator,
        )
        return bridge, conversation, relay

    async def test_direct_route_succeeds_without_request_and_never_calls_core(self):
        bridge, conversation, relay = self.make_bridge()
        bridge.note_route_telemetry(call_id="direct-call", turn=3)
        handled = await bridge.handle_event({
            "type": "response.function_call_arguments.done",
            "name": ROUTE_TURN_TOOL_NAME,
            "call_id": "direct-call",
            "arguments": json.dumps({"route": "direct"}),
        })
        self.assertTrue(handled)
        self.assertEqual(conversation.calls, [])
        self.assertEqual(relay.outputs[-1][1], {"status": "direct"})
        self.assertIsNone(bridge._turn_for_call("direct-call"))

    async def test_core_route_requires_request_and_fails_closed_if_router_omits_it(self):
        bridge, conversation, relay = self.make_bridge()
        bridge.note_route_telemetry(call_id="bad-core", turn=4)
        out = StringIO()
        with redirect_stdout(out):
            handled = await bridge.handle_event({
                "type": "response.function_call_arguments.done",
                "name": ROUTE_TURN_TOOL_NAME,
                "call_id": "bad-core",
                "arguments": json.dumps({"route": "reasoning"}),
            })
        self.assertTrue(handled)
        self.assertEqual(conversation.calls, [])
        self.assertEqual(relay.outputs[-1][1]["status"], "failed")
        self.assertIn("turn=4", out.getvalue())
        self.assertIn("blocked_missing_request", out.getvalue())

    async def test_core_call_console_uses_same_turn_number_as_router_telemetry(self):
        bridge, conversation, relay = self.make_bridge()
        bridge.note_route_telemetry(call_id="reason-call", turn=7)
        out = StringIO()
        with redirect_stdout(out):
            handled = await bridge.handle_event({
                "type": "response.function_call_arguments.done",
                "name": ROUTE_TURN_TOOL_NAME,
                "call_id": "reason-call",
                "arguments": json.dumps({"route": "reasoning", "request": "Explain idempotency."}),
            })
            self.assertTrue(handled)
            await bridge.wait_idle()
        logs = out.getvalue()
        self.assertIn("[Jarvis Core Call] turn=7 | mode=reasoning | status=started", logs)
        self.assertIn("[Jarvis Core Call] turn=7 | mode=reasoning | status=completed", logs)
        self.assertEqual(conversation.calls[0][0], "delegated")


if __name__ == "__main__":
    unittest.main()
