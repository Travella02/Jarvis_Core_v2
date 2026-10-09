from __future__ import annotations

import unittest
from pathlib import Path

from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig
from providers.voice_frontend.openai_realtime.webrtc import (
    DEFAULT_REALTIME_MAX_OUTPUT_TOKENS,
    EXPANDED_REALTIME_MAX_OUTPUT_TOKENS,
    NORMAL_RESPONSE_INSTRUCTIONS,
    TURN_ROUTER_INSTRUCTIONS,
    build_realtime_session,
)

ROOT = Path(__file__).resolve().parents[2]
DESKTOP_HOST = (ROOT / "apps" / "desktop_alpha.py").read_text(encoding="utf-8")
APP = (ROOT / "apps" / "desktop" / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
BRIDGE = (ROOT / "providers" / "voice_frontend" / "openai_realtime" / "bridge.py").read_text(encoding="utf-8")


class ManualResponsePolicyTests(unittest.TestCase):
    def test_desktop_can_keep_semantic_vad_but_disable_auto_response_creation(self) -> None:
        config = OpenAIRealtimeConfig(api_key="test")
        automatic = build_realtime_session(config)
        manual = build_realtime_session(config, auto_create_response=False)
        self.assertTrue(automatic["audio"]["input"]["turn_detection"]["create_response"])
        self.assertFalse(manual["audio"]["input"]["turn_detection"]["create_response"])
        self.assertTrue(manual["audio"]["input"]["turn_detection"]["interrupt_response"])

    def test_response_guardrails_leave_enough_room_to_finish_naturally(self) -> None:
        self.assertEqual(DEFAULT_REALTIME_MAX_OUTPUT_TOKENS, 1024)
        self.assertEqual(EXPANDED_REALTIME_MAX_OUTPUT_TOKENS, 2048)
        self.assertGreater(EXPANDED_REALTIME_MAX_OUTPUT_TOKENS, DEFAULT_REALTIME_MAX_OUTPUT_TOKENS)

    def test_compact_policy_is_response_specific_and_requires_complete_sentences(self) -> None:
        self.assertIn("at most two complete spoken sentences", NORMAL_RESPONSE_INSTRUCTIONS)
        self.assertIn("no more than about 35 words", NORMAL_RESPONSE_INSTRUCTIONS)
        self.assertIn("Always finish the sentence you start", NORMAL_RESPONSE_INSTRUCTIONS)
        self.assertIn("request_expanded_response", NORMAL_RESPONSE_INSTRUCTIONS)

    def test_desktop_host_owns_policy_and_disables_provider_auto_creation(self) -> None:
        self.assertIn('"kind": "response_policy"', DESKTOP_HOST)
        self.assertIn('"instructions": TURN_ROUTER_INSTRUCTIONS', DESKTOP_HOST)
        self.assertIn("auto_create_response=False", DESKTOP_HOST)
        self.assertIn("DIRECT_ROUTED_RESPONSE_INSTRUCTIONS", BRIDGE)

    def test_renderer_manually_creates_voice_and_typed_responses(self) -> None:
        self.assertIn("const requestNormalRealtimeResponse", APP)
        speech_stop = APP.index("type === 'input_audio_buffer.speech_stopped'")
        manual = APP.index("requestNormalRealtimeResponse();", speech_stop)
        self.assertGreater(manual, speech_stop)
        self.assertIn("requestNormalRealtimeResponse(dc);", APP)
        self.assertIn("payload.kind === 'response_policy'", APP)

    def test_core_results_get_same_compact_spoken_surface_policy(self) -> None:
        self.assertIn("CORE_RESULT_RESPONSE_INSTRUCTIONS", BRIDGE)
        self.assertIn('"max_output_tokens": DEFAULT_REALTIME_MAX_OUTPUT_TOKENS', BRIDGE)


if __name__ == "__main__":
    unittest.main()
