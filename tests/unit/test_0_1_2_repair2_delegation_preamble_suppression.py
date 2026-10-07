import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Repair2DelegationPreambleSuppressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.realtime = (ROOT / "providers" / "voice_frontend" / "openai_realtime" / "webrtc.py").read_text(encoding="utf-8")
        cls.bridge = (ROOT / "providers" / "voice_frontend" / "openai_realtime" / "bridge.py").read_text(encoding="utf-8")
        cls.desktop = (ROOT / "apps" / "desktop" / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")

    def test_internal_routing_must_not_be_narrated(self) -> None:
        self.assertIn("Internal implementation privacy:", self.realtime)
        self.assertIn("Never narrate or name them in a user-facing response", self.realtime)
        self.assertIn("use your Core", self.realtime)
        self.assertIn("Do not echo it, announce it, or say that you are pulling in Core", self.realtime)

    def test_earliest_function_call_item_suppresses_preamble(self) -> None:
        branch_start = self.desktop.index("type === 'response.output_item.added'")
        branch_end = self.desktop.index("} else if (type === 'response.output_audio_transcript.delta')", branch_start)
        branch = self.desktop[branch_start:branch_end]
        self.assertIn("delegate_to_jarvis_core", branch)
        self.assertIn("suppressDelegationPreamble(event)", branch)

    def test_suppression_mutes_and_clears_provider_audio(self) -> None:
        helper_start = self.desktop.index("const suppressDelegationPreamble")
        helper_end = self.desktop.index("const sendLatencySummary", helper_start)
        helper = self.desktop[helper_start:helper_end]
        self.assertIn("audioRef.current.muted = true", helper)
        self.assertIn("output_audio_buffer.clear", helper)
        self.assertIn("clearCaptionPacing(true)", helper)
        self.assertIn("setStateSafely('working', 'Working')", helper)

    def test_suppressed_internal_message_is_removed_from_realtime_history(self) -> None:
        helper_start = self.desktop.index("const deleteSuppressedResponseMessages")
        helper_end = self.desktop.index("const sendLatencySummary", helper_start)
        helper = self.desktop[helper_start:helper_end]
        self.assertIn("conversation.item.delete", helper)
        self.assertIn("responseMessageItemIdsRef", helper)
        response_done = self.desktop[self.desktop.index("const delegationCall"):self.desktop.index("} else if (event.response?.status === 'completed')")]
        self.assertIn("deleteSuppressedResponseMessages(event)", response_done)

    def test_suppressed_response_cannot_resume_audio_or_caption(self) -> None:
        transcript_start = self.desktop.index("type === 'response.output_audio_transcript.delta'")
        transcript_end = self.desktop.index("} else if (type === 'output_audio_buffer.started')", transcript_start)
        self.assertIn("responseIsSuppressed(event)", self.desktop[transcript_start:transcript_end])
        audio_start = self.desktop.index("type === 'output_audio_buffer.started'")
        audio_end = self.desktop.index("} else if (type === 'output_audio_buffer.stopped')", audio_start)
        audio_branch = self.desktop[audio_start:audio_end]
        self.assertIn("responseIsSuppressed(event)", audio_branch)
        self.assertIn("output_audio_buffer.clear", audio_branch)

    def test_core_result_instruction_hides_internal_architecture(self) -> None:
        self.assertIn("Do not repeat the request or narrate Core, delegation, backend routing, tools, models, or providers", self.realtime)
        self.assertNotIn("Jarvis Core has returned authoritative backend work", self.realtime)
        self.assertNotIn("Jarvis Core failed to complete the delegated request", self.bridge)


if __name__ == "__main__":
    unittest.main()
