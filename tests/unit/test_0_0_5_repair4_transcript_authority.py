import unittest
from pathlib import Path

from core.voice.lexical import TranscriptEvidenceTracker


ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "core" / "voice" / "engine.py"
WHISPER = ROOT / "providers" / "stt" / "whisper_cpp" / "provider.py"
VOICE_LAB = ROOT / "apps" / "voice_lab.py"


class Repair4TranscriptAuthorityTests(unittest.TestCase):
    def test_rolling_partials_provide_generic_stability_evidence(self):
        tracker = TranscriptEvidenceTracker()
        self.assertTrue(tracker.observe_partial("tell me"))
        self.assertGreater(tracker.stability_score("tell me about mars"), 0.5)

    def test_one_word_partial_earns_stability_only_from_repeat_evidence(self):
        tracker = TranscriptEvidenceTracker()
        self.assertEqual(tracker.stability_score("yes"), 0.0)
        tracker.observe_partial("yes")
        self.assertGreater(tracker.stability_score("yes"), 0.9)

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

    def test_whisper_requests_model_native_non_speech_suppression_and_verbose_confidence(self):
        text = WHISPER.read_text(encoding="utf-8")
        self.assertIn('field("suppress_nst"', text)
        self.assertIn('field("no_speech_thold"', text)
        self.assertIn('field("response_format", "verbose_json")', text)

    def test_continuous_session_uses_internal_partials_even_with_final_only_user_flag(self):
        text = VOICE_LAB.read_text(encoding="utf-8")
        self.assertIn("continuous_control", text)
        self.assertIn("emit_partials=True", text)
        self.assertIn("WhisperCppSileroVadDetector", text)


if __name__ == "__main__":
    unittest.main()
