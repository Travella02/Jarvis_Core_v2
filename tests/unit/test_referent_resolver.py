import unittest

from core.conversation import ConversationContext, Referent, ReferentKind, ReferentResolver, ResolutionStatus


class ReferentResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ConversationContext("conv", "user")
        self.media = Referent(
            "media",
            ReferentKind.MEDIA,
            "YouTube video",
            supported_actions=frozenset({"pause", "resume"}),
        )
        self.task = Referent(
            "task",
            ReferentKind.TASK,
            "calendar task",
            supported_actions=frozenset({"pause", "resume"}),
        )
        self.resolver = ReferentResolver()

    def test_resume_it_prefers_current_conversational_focus_over_media_slot(self) -> None:
        self.context.set_active_media(self.media)
        self.context.set_active_task(self.task, focus=True)
        result = self.resolver.resolve(self.context, "it", action="resume")
        self.assertEqual(result.status, ResolutionStatus.RESOLVED)
        self.assertEqual(result.referent, self.task)

    def test_explicit_wording_outranks_current_focus(self) -> None:
        self.context.set_active_media(self.media)
        self.context.set_active_task(self.task, focus=True)
        result = self.resolver.resolve(self.context, "the YouTube video", action="resume")
        self.assertEqual(result.referent, self.media)
        self.assertEqual(result.reason, "explicit wording")

    def test_material_ambiguity_does_not_guess(self) -> None:
        self.context.active_media = self.media
        self.context.active_task = self.task
        result = self.resolver.resolve(self.context, "it", action="resume")
        self.assertEqual(result.status, ResolutionStatus.AMBIGUOUS)
        self.assertTrue(result.needs_clarification)
        self.assertEqual({item.entity_id for item in result.candidates}, {"media", "task"})

    def test_action_incompatible_focus_is_skipped(self) -> None:
        entity = Referent("doc", ReferentKind.ENTITY, "document", supported_actions=frozenset({"open"}))
        self.context.current_focus_entity = entity
        self.context.active_media = self.media
        result = self.resolver.resolve(self.context, "it", action="resume")
        self.assertEqual(result.referent, self.media)


if __name__ == "__main__":
    unittest.main()
