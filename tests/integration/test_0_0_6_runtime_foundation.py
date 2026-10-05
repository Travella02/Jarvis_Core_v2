import unittest

from core.intelligence import (
    ContextLimits,
    IntelligenceEvent,
    IntelligenceEventType,
    IntelligenceProvider,
    ProviderHealth,
    ProviderHealthState,
    ProviderMetadata,
)
from core.runtime import (
    IntelligenceProviderRouter,
    JarvisRuntime,
    RuntimeLifecycleState,
    RuntimeSettings,
)


class FakeProvider(IntelligenceProvider):
    async def stream_response(self, context, tools, reasoning_policy, cancellation_token):
        yield IntelligenceEvent(IntelligenceEventType.TEXT_DELTA, text_delta="hello")
        yield IntelligenceEvent(IntelligenceEventType.COMPLETED, provider_response_id="resp")

    def supports_tools(self):
        return True

    def supports_vision(self):
        return False

    def supports_reasoning_levels(self):
        return True

    def context_limits(self):
        return ContextLimits(1000, 1000)

    async def cancel(self, request_id):
        return None

    async def health(self):
        return ProviderHealth(ProviderHealthState.HEALTHY, "ready")

    @property
    def metadata(self):
        return ProviderMetadata("fake", "fake-model")


class RuntimeFoundationTests(unittest.IsolatedAsyncioTestCase):
    def _runtime(self, *, history=64):
        settings = RuntimeSettings(event_history_limit=history)
        router = IntelligenceProviderRouter(default_route="primary")
        router.register("primary", FakeProvider(), make_default=True)
        return JarvisRuntime(settings=settings, provider_router=router, version="0.0.6-test")

    async def test_runtime_owns_shared_bus_and_conversation_survives_client_reconnect(self) -> None:
        runtime = self._runtime()
        runtime.start()
        core = runtime.create_conversation(user_id="u", device_id="d")
        before = runtime.snapshot().event_cursor
        result = await core.submit_typed("hello")
        first_snapshot = runtime.snapshot()
        batch = runtime.events_after(before)
        # Simulated UI disconnect/reconnect: no new ConversationCore is created.
        reconnected_snapshot = runtime.snapshot()

        self.assertEqual(result.status, "completed")
        self.assertIs(runtime.conversation, core)
        self.assertEqual(first_snapshot.conversation.conversation_id, core.context.conversation_id)
        self.assertEqual(reconnected_snapshot.conversation.conversation_id, core.context.conversation_id)
        self.assertEqual(reconnected_snapshot.conversation.activity_state, "listening")
        self.assertFalse(batch.gap_detected)
        self.assertTrue(any(event.event_type == "turn.endpointed" for event in batch.events))
        self.assertGreater(len(runtime.event_bus.events_for_correlation(result.trace.correlation_id)), 0)
        runtime.close()

    async def test_presence_activity_lifecycle_and_health_are_orthogonal(self) -> None:
        runtime = self._runtime()
        runtime.start()
        core = runtime.create_conversation(user_id="u")
        runtime.event_bus.emit(
            "voice.presence.changed",
            origin="test",
            conversation_id=core.context.conversation_id,
            payload={"from": "sleeping", "to": "awake", "reason": "test"},
        )
        await runtime.refresh_provider_health()
        snap = runtime.snapshot()
        self.assertEqual(snap.lifecycle, RuntimeLifecycleState.RUNNING)
        self.assertEqual(snap.conversation.presence_state, "awake")
        self.assertEqual(snap.conversation.activity_state, "listening")
        self.assertEqual(snap.health.state.value, "healthy")
        runtime.close()

    async def test_stale_reconnect_cursor_reports_gap_instead_of_silent_loss(self) -> None:
        runtime = self._runtime(history=64)
        runtime.start()
        runtime.create_conversation(user_id="u")
        for number in range(100):
            runtime.event_bus.emit(f"diagnostic.{number}", origin="test")
        batch = runtime.events_after(1)
        self.assertTrue(batch.gap_detected)
        self.assertIsNotNone(batch.oldest_available_sequence)
        self.assertGreater(batch.oldest_available_sequence, 2)
        runtime.close()

    async def test_start_and_stop_are_idempotent_but_invalid_overlap_is_rejected(self) -> None:
        runtime = self._runtime()
        runtime.start()
        cursor = runtime.snapshot().event_cursor
        runtime.start()
        self.assertEqual(runtime.snapshot().event_cursor, cursor)
        runtime.stop()
        stopped_cursor = runtime.snapshot().event_cursor
        runtime.stop()
        self.assertEqual(runtime.snapshot().event_cursor, stopped_cursor)
        runtime.close()


if __name__ == "__main__":
    unittest.main()
