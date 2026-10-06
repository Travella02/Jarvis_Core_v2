from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from core.common.ids import CorrelationContext
from core.conversation import EventBus, TurnResult
from core.voice.frontend import VoiceFrontendEvent, VoiceFrontendEventType
from core.voice.live_bridge import LiveConversationBridge


class FakeSession:
    def __init__(self) -> None:
        self.commentary: list[tuple[str, str]] = []
        self.thinking: list[tuple[str, str]] = []

    @property
    def session_id(self):
        return "live-test"

    async def send_audio(self, pcm_bytes: bytes) -> None:
        pass

    async def send_commentary(self, delegation_id: str, content: str) -> None:
        self.commentary.append((delegation_id, content))

    async def send_thinking(self, delegation_id: str, content: str) -> None:
        self.thinking.append((delegation_id, content))

    async def append_instructions(self, content: str) -> None:
        pass

    async def events(self):
        if False:
            yield None

    async def close(self) -> None:
        pass


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
        trace = CorrelationContext.create()
        return TurnResult(trace=trace, status="completed", text="Core answer.")

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
        return TurnResult(trace=trace, status="completed", text=f"Answer for: {text}")

    async def cancel_active_turn(self, reason: str = "user requested cancellation") -> bool:
        self.cancel_reasons.append(reason)
        self.release.set()
        return True


class LiveClientDelegationTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_delegation_routes_through_existing_conversation_core_boundary(self) -> None:
        session = FakeSession()
        conversation = FakeConversation()
        bridge = LiveConversationBridge(conversation=conversation, session=session)

        await bridge.handle_event(
            VoiceFrontendEvent(
                VoiceFrontendEventType.INPUT_TRANSCRIPT_DELTA,
                text="What is two plus two?",
                start_ms=100,
                end_ms=500,
            )
        )
        await bridge.handle_event(
            VoiceFrontendEvent(
                VoiceFrontendEventType.DELEGATION_REQUESTED,
                delegation_id="delegation-1",
                offset_ms=520,
            )
        )
        await bridge.wait_idle()

        self.assertEqual(conversation.submitted, ["What is two plus two?"])
        self.assertEqual(session.commentary, [("delegation-1", "Core answer.")])
        event_types = [event.event_type for event in conversation.event_bus.history]
        self.assertIn("voice.frontend.delegation.received", event_types)
        self.assertIn("voice.frontend.delegation.completed", event_types)
        await bridge.close()

    async def test_new_delegation_cancels_existing_core_turn_before_queueing_next(self) -> None:
        session = FakeSession()
        conversation = FakeConversation()
        conversation.active_trace = CorrelationContext.create()
        bridge = LiveConversationBridge(conversation=conversation, session=session)

        await bridge.handle_event(
            VoiceFrontendEvent(
                VoiceFrontendEventType.INPUT_TRANSCRIPT_DELTA,
                text="Actually, change that.",
                start_ms=600,
                end_ms=900,
            )
        )
        await bridge.handle_event(
            VoiceFrontendEvent(
                VoiceFrontendEventType.DELEGATION_REQUESTED,
                delegation_id="delegation-2",
                offset_ms=920,
            )
        )
        await bridge.wait_idle()

        self.assertEqual(conversation.cancel_reasons, ["superseded by newer live delegation"])
        self.assertEqual(conversation.submitted, ["Actually, change that."])
        await bridge.close()

    async def test_newer_delegation_suppresses_stale_backend_commentary(self) -> None:
        session = FakeSession()
        conversation = BlockingConversation()
        bridge = LiveConversationBridge(conversation=conversation, session=session)

        await bridge.handle_event(
            VoiceFrontendEvent(
                VoiceFrontendEventType.INPUT_TRANSCRIPT_DELTA,
                text="Book Friday.",
                start_ms=100,
                end_ms=400,
            )
        )
        await bridge.handle_event(
            VoiceFrontendEvent(
                VoiceFrontendEventType.DELEGATION_REQUESTED,
                delegation_id="delegation-old",
                offset_ms=420,
            )
        )
        await conversation.started.wait()

        await bridge.handle_event(
            VoiceFrontendEvent(
                VoiceFrontendEventType.INPUT_TRANSCRIPT_DELTA,
                text="Actually, Thursday.",
                start_ms=500,
                end_ms=760,
            )
        )
        await bridge.handle_event(
            VoiceFrontendEvent(
                VoiceFrontendEventType.DELEGATION_REQUESTED,
                delegation_id="delegation-new",
                offset_ms=780,
            )
        )
        await bridge.wait_idle()

        self.assertEqual(conversation.submitted, ["Book Friday.", "Actually, Thursday."])
        self.assertNotIn(("delegation-old", "Answer for: Book Friday."), session.commentary)
        self.assertIn(("delegation-new", "Answer for: Actually, Thursday."), session.commentary)
        event_types = [event.event_type for event in conversation.event_bus.history]
        self.assertIn("voice.frontend.delegation.superseded", event_types)
        await bridge.close()


if __name__ == "__main__":
    unittest.main()
