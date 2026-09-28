import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Repair34PreservesWholeResponseVoiceTests(unittest.TestCase):
    def test_whole_response_tts_architecture_is_untouched(self):
        text = (ROOT / "core/voice/engine.py").read_text(encoding="utf-8")
        self.assertIn('if self.tts_response_mode == "whole":', text)
        self.assertIn("await queue_spoken_chunk(result.trace, result.text)", text)

    def test_voice_lab_exposes_final_only_ab_without_changing_default(self):
        text = (ROOT / "apps/voice_lab.py").read_text(encoding="utf-8")
        self.assertIn('"--stt-endpoint-final-only"', text)
        self.assertIn("_whisper_config_from_args(args)", text)
        self.assertIn('"--stt-endpoint-final-only"', text)
        self.assertIn('default="streaming"', text)  # Repair33 A/B default remains intact.

    def test_no_personality_or_response_length_policy_change(self):
        text = (ROOT / "core/conversation/engine.py").read_text(encoding="utf-8")
        self.assertIn("Then elaborate naturally if useful", text)
        self.assertNotIn("one sentence maximum", text.lower())


if __name__ == "__main__":
    unittest.main()
