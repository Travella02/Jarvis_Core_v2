import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Repair33PreservesHumanResponsePolicyTests(unittest.TestCase):
    def test_repair33_does_not_modify_conversation_personality_policy(self):
        # Repair33 must remain a TTS scheduling experiment only.
        # ConversationCore's voice instruction stays the committed Repair31 text.
        text = (ROOT / "core/conversation/engine.py").read_text(encoding="utf-8")
        self.assertIn("Respond naturally and concisely", text)
        self.assertIn("Then elaborate naturally if useful", text)
        self.assertNotIn("one or two sentences maximum", text.lower())
        self.assertNotIn("exactly two sentences", text.lower())

    def test_voice_lab_defaults_to_repair31_and_exposes_whole_ab(self):
        text = (ROOT / "apps/voice_lab.py").read_text(encoding="utf-8")
        self.assertIn('"--tts-response-mode"', text)
        self.assertIn('choices=["streaming", "whole"]', text)
        self.assertIn('default="streaming"', text)
        self.assertIn("Whole-response TTS unit:", text)

    def test_engine_whole_mode_uses_final_response_text_once(self):
        text = (ROOT / "core/voice/engine.py").read_text(encoding="utf-8")
        self.assertIn("await queue_spoken_chunk(result.trace, result.text)", text)
        self.assertIn('if self.tts_response_mode == "whole":', text)


if __name__ == "__main__":
    unittest.main()
