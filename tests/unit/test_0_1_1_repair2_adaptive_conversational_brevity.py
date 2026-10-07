from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REALTIME = (ROOT / "providers" / "voice_frontend" / "openai_realtime" / "webrtc.py").read_text(encoding="utf-8")
PERSONA = (ROOT / "core" / "conversation" / "persona.py").read_text(encoding="utf-8")


class AdaptiveConversationalBrevityTests(unittest.TestCase):
    def test_default_answers_have_structural_output_budget(self) -> None:
        self.assertIn("DEFAULT_REALTIME_MAX_OUTPUT_TOKENS = 1024", REALTIME)
        self.assertIn('"max_output_tokens": DEFAULT_REALTIME_MAX_OUTPUT_TOKENS', REALTIME)
        self.assertIn("Response-specific instructions may impose a concise conversational shape", REALTIME)

    def test_short_followups_are_still_continuations_not_new_lectures(self) -> None:
        self.assertIn("Brief continuation questions", REALTIME)
        self.assertIn("Do not restart the earlier explanation", REALTIME)
        self.assertIn("Why does that happen?", PERSONA)

    def test_personality_is_provider_neutral_and_preserved(self) -> None:
        self.assertIn("Provider-neutral Jarvis conversational identity", PERSONA)
        self.assertIn("dry, understated wit", PERSONA)
        self.assertIn("Light sarcasm is welcome occasionally", PERSONA)
        self.assertIn("Accuracy and usefulness outrank wit", PERSONA)

    def test_explicit_detail_requests_use_expansion_tool(self) -> None:
        self.assertIn("EXPAND_RESPONSE_TOOL_NAME", REALTIME)
        self.assertIn("EXPANDED_REALTIME_MAX_OUTPUT_TOKENS = 2048", REALTIME)
        self.assertIn("request_expanded_response", REALTIME)
        self.assertIn("explicit depth request", PERSONA)


if __name__ == "__main__":
    unittest.main()
