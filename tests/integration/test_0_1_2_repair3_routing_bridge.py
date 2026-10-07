import json
import unittest

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
    def __init__(self, text="backend result"):
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


class Repair3RoutingBridgeTests(unittest.IsolatedAsyncioTestCase):
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

    async def route(self, bridge, *, route, request, call_id="route1"):
        handled = await bridge.handle_event({
            "type": "response.function_call_arguments.done",
            "name": ROUTE_TURN_TOOL_NAME,
            "call_id": call_id,
            "arguments": json.dumps({"route": route, "request": request}),
        })
        self.assertTrue(handled)

    async def test_direct_route_never_calls_core_and_continuation_has_no_tools(self):
        bridge, conversation, relay = self.make_bridge()
        await self.route(bridge, route="direct", request="Tell me a joke")
        self.assertEqual(conversation.calls, [])
        _, output, _, overrides = relay.outputs[-1]
        self.assertEqual(output["status"], "direct")
        self.assertEqual(overrides["output_modalities"], ["audio"])
        self.assertEqual(overrides["tools"], [])
        self.assertEqual(overrides["tool_choice"], "none")

    async def test_explicit_reasoning_route_uses_core_before_spoken_followup(self):
        bridge, conversation, relay = self.make_bridge()
        await self.route(
            bridge,
            route="reasoning",
            request="Explain why idempotency matters when a client reconnects to a runtime.",
        )
        await bridge.wait_idle()
        self.assertEqual(conversation.calls[0][0], "delegated")
        _, output, _, overrides = relay.outputs[-1]
        self.assertEqual(output["status"], "completed")
        self.assertEqual(output["result"], "core answer")
        self.assertEqual(overrides["tools"], [])
        self.assertEqual(overrides["tool_choice"], "none")

    async def test_long_task_route_fails_closed_without_model_fallthrough(self):
        bridge, conversation, relay = self.make_bridge()
        await self.route(
            bridge,
            route="long_task",
            request="Start a background task that builds a project while I am gone.",
        )
        await bridge.wait_idle()
        self.assertEqual(conversation.calls, [])
        _, output, _, overrides = relay.outputs[-1]
        self.assertEqual(output["status"], "unavailable")
        self.assertIn("background", output["result"].lower())
        self.assertEqual(overrides["tools"], [])
        self.assertEqual(overrides["tool_choice"], "none")

    async def test_sleep_route_is_silent_lifecycle_transition(self):
        bridge, conversation, relay = self.make_bridge()
        await self.route(bridge, route="sleep", request="That's all")
        self.assertEqual(conversation.calls, [])
        self.assertEqual(relay.outputs, [])
        self.assertEqual(relay.sleep_reasons, ["explicit_sleep"])


if __name__ == "__main__":
    unittest.main()
