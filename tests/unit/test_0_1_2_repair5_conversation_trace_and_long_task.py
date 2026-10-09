from __future__ import annotations

from pathlib import Path
import unittest

from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig
from providers.voice_frontend.openai_realtime.webrtc import (
    ROUTE_TURN_TOOL,
    TURN_ROUTER_INSTRUCTIONS,
    build_realtime_session,
)


ROOT = Path(__file__).resolve().parents[2]
APP_TSX = ROOT / "apps" / "desktop" / "ui" / "src" / "App.tsx"
DESKTOP_ALPHA = ROOT / "apps" / "desktop_alpha.py"


class Repair5ConversationTraceAndLongTaskTests(unittest.TestCase):
    def test_desktop_trace_transcription_is_explicit_and_async_only(self) -> None:
        config = OpenAIRealtimeConfig(api_key="test")
        session = build_realtime_session(
            config,
            auto_create_response=False,
            include_expand_response_tool=False,
            include_input_transcription=True,
        )
        transcription = session["audio"]["input"]["transcription"]
        self.assertEqual(transcription["model"], "gpt-realtime-whisper")
        self.assertEqual(transcription["delay"], "minimal")
        self.assertFalse(session["audio"]["input"]["turn_detection"]["create_response"])

    def test_trace_transcription_can_be_disabled_without_changing_voice_session(self) -> None:
        config = OpenAIRealtimeConfig(api_key="test")
        session = build_realtime_session(config, include_input_transcription=False)
        self.assertNotIn("transcription", session["audio"]["input"])

    def test_trace_config_can_be_disabled_from_env(self) -> None:
        config = OpenAIRealtimeConfig.from_env(
            {
                "OPENAI_API_KEY": "test",
                "JARVIS_DESKTOP_CONVERSATION_TRACE": "0",
                "JARVIS_REALTIME_INPUT_TRANSCRIPTION_MODEL": "gpt-realtime-whisper",
            }
        )
        self.assertFalse(config.desktop_conversation_trace)
        self.assertEqual(config.input_transcription_model, "gpt-realtime-whisper")

    def test_terminal_conversation_labels_are_unambiguous(self) -> None:
        source = DESKTOP_ALPHA.read_text(encoding="utf-8")
        self.assertIn("[USER SPEECH]", source)
        self.assertIn("[JARVIS REPLY]", source)
        self.assertIn('kind == "desktop_user"', source)
        self.assertIn('kind == "desktop_reply"', source)

    def test_renderer_forwards_voice_transcript_and_final_reply(self) -> None:
        source = APP_TSX.read_text(encoding="utf-8")
        self.assertIn("conversation.item.input_audio_transcription.completed", source)
        self.assertIn("kind: 'desktop_user'", source)
        self.assertIn("kind: 'desktop_reply'", source)
        self.assertIn("responseTranscript(event.response)", source)

    def test_background_execution_has_precedence_over_generic_action(self) -> None:
        self.assertIn("If a request is both an action and background/durable work, choose long_task", TURN_ROUTER_INSTRUCTIONS)
        self.assertIn("while they are away", TURN_ROUTER_INSTRUCTIONS)
        route = ROUTE_TURN_TOOL["parameters"]["properties"]["route"]
        self.assertIn("long_task", route["enum"])
        self.assertIn("Use long_task rather than action", route["description"])


if __name__ == "__main__":
    unittest.main()
