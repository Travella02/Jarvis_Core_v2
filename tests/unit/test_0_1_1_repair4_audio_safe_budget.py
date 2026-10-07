from __future__ import annotations

import unittest

from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig
from providers.voice_frontend.openai_realtime.webrtc import (
    DEFAULT_REALTIME_MAX_OUTPUT_TOKENS,
    EXPANDED_REALTIME_MAX_OUTPUT_TOKENS,
    REALTIME_CONVERSATION_INSTRUCTIONS,
    build_realtime_session,
)


class AudioSafeResponseBudgetTests(unittest.TestCase):
    def test_normal_budget_is_audio_safe_guardrail(self) -> None:
        session = build_realtime_session(OpenAIRealtimeConfig(api_key="test"))
        self.assertEqual(DEFAULT_REALTIME_MAX_OUTPUT_TOKENS, 1024)
        self.assertEqual(session["max_output_tokens"], 1024)
        self.assertEqual(session["output_modalities"], ["audio"])

    def test_expanded_budget_has_real_headroom(self) -> None:
        self.assertEqual(EXPANDED_REALTIME_MAX_OUTPUT_TOKENS, 2048)
        self.assertGreater(EXPANDED_REALTIME_MAX_OUTPUT_TOKENS, DEFAULT_REALTIME_MAX_OUTPUT_TOKENS)

    def test_prompt_targets_words_separately_from_token_guardrail(self) -> None:
        self.assertIn("Response-specific instructions", REALTIME_CONVERSATION_INSTRUCTIONS)
        self.assertIn("shortest natural answer", REALTIME_CONVERSATION_INSTRUCTIONS)


if __name__ == "__main__":
    unittest.main()
