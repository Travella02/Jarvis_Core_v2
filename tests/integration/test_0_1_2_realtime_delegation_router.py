import asyncio
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


class FakeProvider(IntelligenceProvider):
    def __init__(self, model): self._model = model
    async def stream_response(self, context, tools, reasoning_policy, cancellation_token):
        yield IntelligenceEvent(IntelligenceEventType.COMPLETED)
    def supports_tools(self): return True
    def supports_vision(self): return False
    def supports_reasoning_levels(self): return True
    def context_limits(self): return ContextLimits()
    async def cancel(self, request_id): return None
    async def health(self): return ProviderHealth(ProviderHealthState.HEALTHY)
    @property
    def metadata(self): return ProviderMetadata("fake", self._model)


class FakeContext:
    conversation_id = "conversation"
    user_id = "user"
    device_id = "desktop"


class FakeTurn:
    def __init__(self, text):
        self.trace = CorrelationContext.create()
        self.status = "completed"
        self.text = text
        self.provider_response_id = "resp"
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
        self.calls.append(("legacy", text, None))
        return FakeTurn("legacy")
    async def submit_delegated(self, text, *, provider, reasoning_policy=None, tools=()):
        self.calls.append(("routed", text, provider.metadata.model))
        return FakeTurn(f"answer from {provider.metadata.model}")


class FakeRelay:
    def __init__(self): self.outputs = []
    async def send_function_output(self, call_id, output, continue_response=True, response_overrides=None):
        self.outputs.append((call_id, output, continue_response, response_overrides))
    async def request_browser_sleep(self, *, reason): pass


class RealtimeDelegationRouter012Tests(unittest.IsolatedAsyncioTestCase):
    def make_bridge(self, *, strong=True):
        router = IntelligenceProviderRouter(default_route="primary")
        router.register("primary", FakeProvider("luna"), make_default=True)
        if strong:
            router.register("strong", FakeProvider("strong-model"))
        orchestrator = DelegationOrchestrator(provider_router=router, default_route="primary")
        conversation = FakeConversation()
        relay = FakeRelay()
        bridge = RealtimeCoreBridge(
            conversation=conversation,
            relay=relay,
            delegation_orchestrator=orchestrator,
        )
        return bridge, conversation, relay

    async def test_realtime_does_not_choose_concrete_model(self):
        bridge, conversation, relay = self.make_bridge(strong=True)
        await bridge.handle_event({
            "type": "response.function_call_arguments.done",
            "name": "delegate_to_jarvis_core",
            "call_id": "call1",
            "arguments": json.dumps({
                "request": "Analyze this architecture, compare tradeoffs, debug the root cause, and design a multi-step solution.",
                "mode": "reasoning",
            }),
        })
        await bridge.wait_idle()
        self.assertEqual(conversation.calls[0][2], "strong-model")
        self.assertEqual(relay.outputs[-1][1]["route"], "strong")

    async def test_action_without_executor_returns_unavailable_not_fake_success(self):
        bridge, conversation, relay = self.make_bridge()
        await bridge.handle_event({
            "type": "response.function_call_arguments.done",
            "name": "delegate_to_jarvis_core",
            "call_id": "call2",
            "arguments": json.dumps({"request": "Open the app", "mode": "action"}),
        })
        await bridge.wait_idle()
        self.assertEqual(conversation.calls, [])
        self.assertEqual(relay.outputs[-1][1]["status"], "unavailable")
        self.assertEqual(relay.outputs[-1][1]["capability"], "action")

    async def test_current_data_mode_is_accepted_by_bridge(self):
        bridge, conversation, relay = self.make_bridge()
        await bridge.handle_event({
            "type": "response.function_call_arguments.done",
            "name": "delegate_to_jarvis_core",
            "call_id": "call3",
            "arguments": json.dumps({"request": "Get the latest value", "mode": "current_data"}),
        })
        await bridge.wait_idle()
        self.assertEqual(relay.outputs[-1][1]["status"], "unavailable")
        self.assertEqual(relay.outputs[-1][1]["capability"], "current_data")


if __name__ == "__main__":
    unittest.main()
