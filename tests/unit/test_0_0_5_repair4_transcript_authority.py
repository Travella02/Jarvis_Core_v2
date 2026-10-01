import unittest
from pathlib import Path

from core.voice.lexical import TranscriptEvidenceTracker


ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "core" / "voice" / "engine.py"
WHISPER = ROOT / "providers" / "stt" / "whisper_cpp" / "provider.py"
VOICE_LAB = ROOT / "apps" / "voice_lab.py"


class Repair4TranscriptAuthorityTests(unittest.TestCase):
    def test_arbitrary_partial_needs_same_stream_stability_before_early_barge_in(self):
        tracker = TranscriptEvidenceTracker()
        self.assertTrue(tracker.observe_partial("tell me"))
        self.assertFalse(tracker.confirms_early_partial("tell me"))
        self.assertTrue(tracker.observe_partial("tell me about mars"))
        self.assertTrue(tracker.confirms_early_partial("tell me about mars"))

    def test_deliberate_control_word_can_interrupt_on_first_partial(self):
        tracker = TranscriptEvidenceTracker()
        self.assertTrue(tracker.observe_partial("wait"))
        self.assertTrue(tracker.confirms_early_partial("wait"))

    def test_compatible_partial_confirms_quiet_final_without_amplitude_gate(self):
        tracker = TranscriptEvidenceTracker()
        tracker.observe_partial("why is")
        self.assertTrue(tracker.confirms_final("Why is that?", require_partial=True))

    def test_engine_uses_one_live_stt_turn_after_independent_speech_presence(self):
        text = ENGINE.read_text(encoding="utf-8")
        self.assertIn('name="jarvis-live-stt-turn"', text)
        self.assertIn("reset_false_candidate", text)
        self.assertIn("await reset_false_candidate()", text)
        self.assertIn("onset.accept(vad_speech)", text)
        self.assertNotIn("_probe_lexical_text", text)
        self.assertNotIn("SpeechEvidenceGate(", text)
        self.assertNotIn("SpeechActivityFusion()", text)

    def test_whisper_requests_model_native_non_speech_suppression(self):
        text = WHISPER.read_text(encoding="utf-8")
        self.assertIn('field("suppress_nst"', text)
        self.assertIn('field("no_speech_thold"', text)

    def test_continuous_session_uses_internal_partials_even_with_final_only_user_flag(self):
        text = VOICE_LAB.read_text(encoding="utf-8")
        self.assertIn("continuous_control", text)
        self.assertIn("emit_partials=True", text)
        self.assertIn("require_partial_confirmation=False", text)
        self.assertIn("WhisperCppSileroVadDetector", text)


if __name__ == "__main__":
    unittest.main()
