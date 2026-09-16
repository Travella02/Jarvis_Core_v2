import unittest

from core.common.ids import CorrelationContext
from core.conversation import ConversationContext, EventBus


class EventBusTests(unittest.TestCase):
    def test_event_contains_trace_identity_and_structured_payload(self) -> None:
        bus = EventBus()
        trace = CorrelationContext.create()
        event = bus.emit(
            "turn.endpointed",
            origin="test",
            trace=trace,
            conversation_id="conv",
            user_id="user",
            device_id="device",
            payload={"channel": "typed"},
        )
        self.assertEqual(event.trace, trace)
        self.assertEqual(event.payload["channel"], "typed")
        with self.assertRaises(TypeError):
            event.payload["channel"] = "voice"

    def test_specific_and_wildcard_subscribers_receive_event(self) -> None:
        bus = EventBus()
        seen = []
        bus.subscribe("x", lambda event: seen.append(("specific", event.event_type)))
        bus.subscribe("*", lambda event: seen.append(("all", event.event_type)))
        bus.emit("x", origin="test")
        self.assertEqual(seen, [("specific", "x"), ("all", "x")])

    def test_history_is_bounded(self) -> None:
        bus = EventBus(history_limit=2)
        for number in range(3):
            bus.emit(f"event.{number}", origin="test")
        self.assertEqual([item.event_type for item in bus.history], ["event.1", "event.2"])


if __name__ == "__main__":
    unittest.main()
