import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Repair1DelegationCaptionTruthfulnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.realtime = (ROOT / "providers" / "voice_frontend" / "openai_realtime" / "webrtc.py").read_text(encoding="utf-8")
        cls.desktop = (ROOT / "apps" / "desktop" / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")

    def test_delegation_tool_call_precedes_spoken_preamble(self) -> None:
        self.assertIn("that tool call must be the initial output for the response", self.realtime)
        self.assertIn("Do not speak an acknowledgement, plan, or filler before the tool call", self.realtime)
        self.assertIn("The desktop WORKING state is the acknowledgement", self.realtime)

    def test_delegated_actions_cannot_be_announced_before_core_confirms_them(self) -> None:
        self.assertIn("Never say or imply that an action, background task, search, lookup", self.realtime)
        self.assertIn("until Jarvis Core returns an authoritative result confirming that state", self.realtime)

    def test_unavailable_core_results_are_presented_without_fake_progress(self) -> None:
        self.assertIn("Read the function result status first", self.realtime)
        self.assertIn("Never describe an unavailable, failed, cancelled, or superseded capability as started", self.realtime)
        self.assertIn("If the status is unavailable, state the limitation plainly and stop", self.realtime)

    def test_function_call_boundary_discards_internal_preamble_after_repair2(self) -> None:
        branch_start = self.desktop.index("type === 'response.function_call_arguments.done'")
        branch_end = self.desktop.index("} else if (type === 'response.done')", branch_start)
        branch = self.desktop[branch_start:branch_end]
        self.assertIn("suppressDelegationPreamble(event)", branch)
        self.assertNotIn("finalizeCaptionPacing()", branch)

    def test_function_call_response_done_keeps_internal_preamble_suppressed(self) -> None:
        branch_start = self.desktop.index("const delegationCall")
        branch_end = self.desktop.index("} else if (event.response?.status === 'completed')", branch_start)
        branch = self.desktop[branch_start:branch_end]
        self.assertIn("suppressDelegationPreamble(event)", branch)
        self.assertNotIn("finalizeCaptionPacing()", branch)

    def test_caption_finalizer_still_exists_for_non_delegation_completion_paths(self) -> None:
        helper_start = self.desktop.index("const finalizeCaptionPacing")
        helper_end = self.desktop.index("const enqueueCaptionDelta", helper_start)
        helper = self.desktop[helper_start:helper_end]
        self.assertIn("captionIndexRef.current = captionSourceRef.current.length", helper)
        self.assertIn("setCaption(normalizeCaptionForDisplay(captionSourceRef.current))", helper)


if __name__ == "__main__":
    unittest.main()
