from __future__ import annotations

import unittest

from core.voice.webrtc import normalize_sdp
from providers.voice_frontend.openai_realtime import (
    DELEGATE_TOOL_NAME,
    SLEEP_TOOL_NAME,
    OpenAIRealtimeConfig,
    build_realtime_session,
)


class Repair4RealtimeContractTests(unittest.TestCase):
    def test_config_defaults_to_realtime_2_1_mini_cedar_low_reasoning(self) -> None:
        cfg = OpenAIRealtimeConfig.from_env({"OPENAI_API_KEY": "test-key"})
        self.assertEqual(cfg.model, "gpt-realtime-2.1-mini")
        self.assertEqual(cfg.voice, "cedar")
        self.assertEqual(cfg.reasoning_effort, "low")
        self.assertEqual(cfg.api_key, "test-key")

    def test_session_keeps_only_narrow_core_delegation_tool(self) -> None:
        cfg = OpenAIRealtimeConfig(api_key="test")
        session = build_realtime_session(cfg)
        self.assertEqual(session["type"], "realtime")
        self.assertEqual(session["model"], "gpt-realtime-2.1-mini")
        self.assertEqual(session["audio"]["output"]["voice"], "cedar")
        self.assertEqual(session["reasoning"], {"effort": "low"})
        self.assertEqual(session["tool_choice"], "auto")
        tool_names = [tool["name"] for tool in session["tools"]]
        self.assertEqual(tool_names, [DELEGATE_TOOL_NAME, SLEEP_TOOL_NAME, "request_expanded_response"])
        # sleep_jarvis and request_expanded_response are local lifecycle/presentation
        # controls; delegate_to_jarvis_core remains the sole tool that can request
        # authoritative backend work.
        instructions = session["instructions"].lower()
        self.assertIn("answer ordinary conversation", instructions)
        self.assertIn("do not pretend to look something up", instructions)
        self.assertIn("sure, i'm on it", instructions)
        self.assertIn("core remains authoritative", instructions)

    def test_realtime_provider_does_not_pin_pcm_format_for_browser_webrtc(self) -> None:
        session = build_realtime_session(OpenAIRealtimeConfig(api_key="test"))
        self.assertNotIn("format", session["audio"]["input"])
        self.assertNotIn("format", session["audio"]["output"])
        self.assertEqual(session["audio"]["input"]["turn_detection"]["type"], "semantic_vad")
        self.assertTrue(session["audio"]["input"]["turn_detection"]["interrupt_response"])

    def test_shared_sdp_normalizer_keeps_crlf_terminal_framing(self) -> None:
        self.assertEqual(normalize_sdp("v=0\nm=audio 9 RTP/AVP 0\n", label="offer"), "v=0\r\nm=audio 9 RTP/AVP 0\r\n")

    def test_bad_reasoning_effort_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OpenAIRealtimeConfig.from_env(
                {"OPENAI_API_KEY": "test", "JARVIS_REALTIME_REASONING_EFFORT": "warp-speed"}
            )


if __name__ == "__main__":
    unittest.main()
