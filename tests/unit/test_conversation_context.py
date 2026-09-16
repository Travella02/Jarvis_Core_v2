import unittest

from core.common.ids import CorrelationContext
from core.conversation import (
    ConversationContext,
    InputChannel,
    Referent,
    ReferentKind,
    TranscriptEntry,
    TranscriptRole,
)


class ConversationContextTests(unittest.TestCase):
    def test_recent_referents_are_deduplicated_and_bounded(self) -> None:
        context = ConversationContext("conv", "user", max_recent_referents=2)
        one = Referent("1", ReferentKind.ENTITY, "one")
        two = Referent("2", ReferentKind.ENTITY, "two")
        context.record_referent(one)
        context.record_referent(two)
        context.record_referent(one)
        self.assertEqual([item.entity_id for item in context.recent_referents], ["1", "2"])

    def test_active_slot_type_is_enforced(self) -> None:
        context = ConversationContext("conv", "user")
        with self.assertRaises(ValueError):
            context.set_active_task(Referent("media", ReferentKind.MEDIA, "video"))

    def test_snapshot_round_trip_preserves_focus_and_transcript(self) -> None:
        context = ConversationContext("conv", "user", speaker_id="speaker", device_id="device")
        task = Referent(
            "task-1",
            ReferentKind.TASK,
            "morning task",
            supported_actions=frozenset({"resume"}),
        )
        context.set_active_task(task, focus=True)
        context.append_transcript(
            TranscriptEntry.create(
                role=TranscriptRole.USER,
                content="remember bluejay",
                channel=InputChannel.TYPED,
                turn_id="turn-1",
            )
        )
        restored = ConversationContext.from_dict(context.to_dict())
        self.assertEqual(restored.current_focus_entity.entity_id, "task-1")
        self.assertEqual(restored.recent_transcript[0].content, "remember bluejay")
        self.assertEqual(restored.device_id, "device")

    def test_provider_snapshot_contains_shared_conversation_history(self) -> None:
        context = ConversationContext("conv", "user")
        context.working_memory_summary = "User prefers concise answers."
        context.append_transcript(
            TranscriptEntry.create(
                role=TranscriptRole.USER,
                content="The test word is bluejay.",
                channel=InputChannel.TYPED,
                turn_id="turn-1",
            )
        )
        snapshot = context.to_intelligence_context(CorrelationContext.create())
        self.assertEqual(snapshot.messages[0]["role"], "system")
        self.assertIn("concise", snapshot.messages[0]["content"])
        self.assertEqual(snapshot.messages[1]["content"], "The test word is bluejay.")
        self.assertEqual(snapshot.metadata["conversation_id"], "conv")


if __name__ == "__main__":
    unittest.main()
