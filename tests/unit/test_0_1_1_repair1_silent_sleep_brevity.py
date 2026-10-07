from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / "apps" / "desktop" / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
REALTIME = (ROOT / "providers" / "voice_frontend" / "openai_realtime" / "webrtc.py").read_text(encoding="utf-8")
PERSONA = (ROOT / "core" / "conversation" / "persona.py").read_text(encoding="utf-8")


class SilentSleepBrevityTests(unittest.TestCase):
    def test_sleep_intent_is_tool_only_and_never_spoken_acknowledgement(self) -> None:
        self.assertIn("call sleep_jarvis immediately as the only response", REALTIME)
        self.assertIn("produce no spoken acknowledgement, filler, or normal answer", REALTIME)

    def test_sleep_transition_cancels_and_clears_provider_audio_before_teardown(self) -> None:
        self.assertIn("const silenceRealtimeOutput = () =>", APP)
        self.assertIn("type: 'response.cancel'", APP)
        self.assertIn("type: 'output_audio_buffer.clear'", APP)
        self.assertIn("type: 'input_audio_buffer.clear'", APP)
        sleep_index = APP.index("const enterSleep = async")
        silence_index = APP.index("silenceRealtimeOutput();", sleep_index)
        stop_index = APP.index("await stopRealtimeSession", sleep_index)
        self.assertLess(silence_index, stop_index)

    def test_sleep_hard_stops_local_playout_and_clears_visible_caption(self) -> None:
        self.assertIn("audioRef.current.pause()", APP)
        self.assertIn("audioRef.current.muted = true", APP)
        self.assertIn("clearCaptionPacing(true)", APP)
        self.assertIn("audioRef.current.muted = false", APP)

    def test_direct_realtime_answers_use_enforced_budget_without_flattening_personality(self) -> None:
        self.assertIn("DEFAULT_REALTIME_MAX_OUTPUT_TOKENS = 1024", REALTIME)
        self.assertIn("request_expanded_response", REALTIME)
        self.assertIn("dry, understated wit", PERSONA)
        self.assertIn("Personality must never change facts", PERSONA)


if __name__ == "__main__":
    unittest.main()
