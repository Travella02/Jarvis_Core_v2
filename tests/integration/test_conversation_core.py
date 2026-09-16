import asyncio
import unittest

from core.common.ids import CorrelationContext
from core.conversation import ConversationContext, ConversationCore, CoreState, HeardResponseState
from core.intelligence import (
    ContextLimits,
    IntelligenceEvent,
    IntelligenceEventType,
    IntelligenceProvider,
    ProviderCapabilities,
    ProviderHealth,
    ProviderHealthState,
    ProviderMetadata,
)
from core.tools import ToolRequest


class FakeProvider(IntelligenceProvider):
    def __init__(self, turns):
        self.turns = list(turns)
        self.contexts = []
        self.tokens = []
        self.cancelled_requests = []

    async def stream_response(self, context, tools, reasoning_policy, cancellation_token):
        self.contexts.append(context)
        self.tokens.append(cancellation_token)
        events = self.turns.pop(0)
        for event in events:
            await asyncio.sleep(0)
            yield event

    def supports_tools(self):
        return True

    def supports_vision(self):
        return True

    def supports_reasoning_levels(self):
        return True

    def context_limits(self):
        return ContextLimits(1000, 1000)

    async def cancel(self, request_id):
        self.cancelled_requests.append(request_id)

    async def health(self):
        return ProviderHealth(ProviderHealthState.HEALTHY)

    @property
    def metadata(self):
        return ProviderMetadata("fake", "fake-model")


def text_turn(text):
    return [
        IntelligenceEvent(IntelligenceEventType.TEXT_DELTA, text_delta=text),
        IntelligenceEvent(IntelligenceEventType.COMPLETED, provider_response_id="resp"),
    ]


class ConversationCoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_typed_turns_share_one_authoritative_history(self) -> None:
        provider = FakeProvider([text_turn("bluejay stored"), text_turn("bluejay")])
        context = ConversationContext("conv", "user")
        core = ConversationCore(context=context, provider=provider)
        first = await core.submit_typed("Remember bluejay")
        second = await core.submit_typed("What word?")
        self.assertEqual(first.status, "completed")
        self.assertEqual(second.text, "bluejay")
        self.assertEqual(
            [item["content"] for item in provider.contexts[1].messages],
            ["Remember bluejay", "bluejay stored", "What word?"],
        )
        self.assertEqual(core.state.state, CoreState.LISTENING)
        self.assertEqual(context.heard_response_state, HeardResponseState.COMPLETE)
        self.assertEqual(core.cancellations.active_ids(), ())

    async def test_provider_tool_request_stays_intent_only(self) -> None:
        request = ToolRequest(
            trace=CorrelationContext.create(),
            tool_name="demo_tool",
            operation="invoke",
            arguments={"value": 1},
            provider_call_id="call-1",
        )
        provider = FakeProvider([
            [
                IntelligenceEvent(IntelligenceEventType.TOOL_REQUEST, tool_request=request),
                IntelligenceEvent(IntelligenceEventType.COMPLETED),
            ]
        ])
        core = ConversationCore(context=ConversationContext("conv", "user"), provider=provider)
        result = await core.submit_typed("request tool")
        self.assertEqual(result.tool_requests, (request,))
        self.assertIsNone(core.context.last_tool_action)
        requested = [event for event in core.event_bus.history if event.event_type == "tool.requested"]
        self.assertEqual(requested[0].payload["authority"], "intent-only")

    async def test_cancel_active_turn_targets_provider_and_token(self) -> None:
        class SlowProvider(FakeProvider):
            async def stream_response(self, context, tools, reasoning_policy, cancellation_token):
                self.contexts.append(context)
                self.tokens.append(cancellation_token)
                while not cancellation_token.is_cancelled:
                    await asyncio.sleep(0.001)
                yield IntelligenceEvent(
                    IntelligenceEventType.CANCELLED,
                    detail=cancellation_token.reason,
                )

        provider = SlowProvider([])
        core = ConversationCore(context=ConversationContext("conv", "user"), provider=provider)
        task = asyncio.create_task(core.submit_typed("long request"))
        for _ in range(100):
            if core.active_trace is not None:
                break
            await asyncio.sleep(0.001)
        trace = core.active_trace
        self.assertIsNotNone(trace)
        self.assertTrue(await core.cancel_active_turn("user interruption"))
        result = await task
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(provider.cancelled_requests, [trace.request_id])
        self.assertEqual(core.state.state, CoreState.LISTENING)
        self.assertEqual(core.context.heard_response_state, HeardResponseState.INTERRUPTED)

    async def test_stream_without_terminal_event_fails_honestly(self) -> None:
        provider = FakeProvider([[IntelligenceEvent(IntelligenceEventType.TEXT_DELTA, text_delta="partial")]])
        core = ConversationCore(context=ConversationContext("conv", "user"), provider=provider)
        result = await core.submit_typed("hello")
        self.assertEqual(result.status, "error")
        self.assertIn("without a terminal event", result.detail)
        self.assertEqual(core.state.state, CoreState.ERROR)
        self.assertEqual(core.context.heard_response_state, HeardResponseState.INTERRUPTED)

    async def test_cancelled_turn_discards_pending_tool_plan(self) -> None:
        request = ToolRequest(
            trace=CorrelationContext.create(),
            tool_name="demo_tool",
            operation="invoke",
            arguments={"value": 1},
            provider_call_id="call-1",
        )
        provider = FakeProvider([[
            IntelligenceEvent(IntelligenceEventType.TOOL_REQUEST, tool_request=request),
            IntelligenceEvent(IntelligenceEventType.CANCELLED, detail="interrupted"),
        ]])
        core = ConversationCore(context=ConversationContext("conv", "user"), provider=provider)
        result = await core.submit_typed("request then cancel")
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(result.tool_requests, ())
        self.assertTrue(any(e.event_type == "tool.plan.discarded" for e in core.event_bus.history))


    async def test_degraded_provider_moves_core_to_degraded(self) -> None:
        provider = FakeProvider([
            [IntelligenceEvent(IntelligenceEventType.DEGRADED, detail="provider unavailable")]
        ])
        core = ConversationCore(context=ConversationContext("conv", "user"), provider=provider)
        result = await core.submit_typed("hello")
        self.assertEqual(result.status, "degraded")
        self.assertEqual(core.state.state, CoreState.DEGRADED)


if __name__ == "__main__":
    unittest.main()
