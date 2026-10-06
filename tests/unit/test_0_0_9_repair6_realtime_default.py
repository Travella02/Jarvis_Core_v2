from __future__ import annotations

import argparse
import unittest
from pathlib import Path

from apps.gpt_realtime_webrtc_lab import _response_contains_function_call, parser
from core.diagnostics import collect_diagnostics
from providers.voice_frontend.openai_realtime.config import DEFAULT_REALTIME_MODEL, OpenAIRealtimeConfig
from providers.voice_frontend.openai_realtime.webrtc import REALTIME_CONVERSATION_INSTRUCTIONS, build_realtime_session


ROOT = Path(__file__).resolve().parents[2]


class Repair6RealtimeDefaultTests(unittest.TestCase):
    def test_realtime_mini_is_default_but_model_remains_configurable(self) -> None:
        self.assertEqual(DEFAULT_REALTIME_MODEL, "gpt-realtime-2.1-mini")
        config = OpenAIRealtimeConfig.from_env({"OPENAI_API_KEY": "test-key"})
        self.assertEqual(config.model, "gpt-realtime-2.1-mini")
        full = OpenAIRealtimeConfig.from_env({"OPENAI_API_KEY": "test-key", "JARVIS_REALTIME_MODEL": "gpt-realtime-2.1"})
        self.assertEqual(full.model, "gpt-realtime-2.1")

    def test_default_session_preserves_core_delegation_and_natural_personality(self) -> None:
        config = OpenAIRealtimeConfig.from_env({"OPENAI_API_KEY": "test-key"})
        session = build_realtime_session(config)
        self.assertEqual(session["model"], "gpt-realtime-2.1-mini")
        self.assertEqual([tool["name"] for tool in session["tools"]], ["delegate_to_jarvis_core"])
        self.assertIn("Natural personality is welcome", REALTIME_CONVERSATION_INSTRUCTIONS)
        self.assertIn("Do not use personality as filler", REALTIME_CONVERSATION_INSTRUCTIONS)
        self.assertIn("Core remains authoritative", REALTIME_CONVERSATION_INSTRUCTIONS)

    def test_lab_does_not_prewarm_core_by_default_and_has_final_playout_grace(self) -> None:
        args = parser().parse_args([])
        self.assertFalse(args.prewarm_core)
        self.assertEqual(args.tail_seconds, 5.0)

    def test_function_call_only_response_is_not_a_final_spoken_response(self) -> None:
        self.assertTrue(_response_contains_function_call({"response": {"output": [{"type": "function_call"}]}}))
        self.assertFalse(_response_contains_function_call({"response": {"output": [{"type": "message"}]}}))

    def test_diagnostics_declares_realtime_mini_default_and_keeps_alternatives(self) -> None:
        providers = collect_diagnostics()["providers"]
        self.assertEqual(providers["voice_frontend_default"], "openai-gpt-realtime-2.1-mini/webrtc")
        self.assertIn("openai-gpt-live", providers["voice_frontend_alternatives"])
        self.assertIn("local-chain", providers["voice_frontend_alternatives"])

    def test_env_example_documents_swappable_realtime_defaults(self) -> None:
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("JARVIS_REALTIME_MODEL=gpt-realtime-2.1-mini", text)
        self.assertIn("JARVIS_REALTIME_VOICE=cedar", text)
        self.assertIn("JARVIS_REALTIME_REASONING_EFFORT=low", text)


if __name__ == "__main__":
    unittest.main()
