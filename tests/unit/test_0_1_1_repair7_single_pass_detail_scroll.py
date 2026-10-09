from __future__ import annotations

import re
import unittest
from pathlib import Path

from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig
from providers.voice_frontend.openai_realtime.webrtc import (
    DESKTOP_REALTIME_MAX_OUTPUT_TOKENS,
    ROUTER_REALTIME_MAX_OUTPUT_TOKENS,
    NORMAL_RESPONSE_INSTRUCTIONS,
    build_realtime_session,
)

ROOT = Path(__file__).resolve().parents[2]
DESKTOP_HOST = (ROOT / "apps" / "desktop_alpha.py").read_text(encoding="utf-8")
APP = (ROOT / "apps" / "desktop" / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
STYLES = (ROOT / "apps" / "desktop" / "ui" / "src" / "styles.css").read_text(encoding="utf-8")


class Repair7SinglePassDetailScrollTests(unittest.TestCase):
    def test_desktop_session_can_remove_expansion_tool_without_changing_default_labs(self) -> None:
        config = OpenAIRealtimeConfig(api_key="test")
        default_session = build_realtime_session(config)
        desktop_session = build_realtime_session(config, auto_create_response=False, include_expand_response_tool=False)
        self.assertIn("request_expanded_response", [tool["name"] for tool in default_session["tools"]])
        self.assertEqual(
            [tool["name"] for tool in desktop_session["tools"]],
            ["delegate_to_jarvis_core", "sleep_jarvis"],
        )

    def test_desktop_router_budget_is_separate_from_answer_headroom(self) -> None:
        self.assertEqual(DESKTOP_REALTIME_MAX_OUTPUT_TOKENS, 2048)
        self.assertLess(ROUTER_REALTIME_MAX_OUTPUT_TOKENS, DESKTOP_REALTIME_MAX_OUTPUT_TOKENS)
        self.assertIn("include_expand_response_tool=False", DESKTOP_HOST)
        self.assertIn('"max_output_tokens": ROUTER_REALTIME_MAX_OUTPUT_TOKENS', DESKTOP_HOST)
        self.assertIn("answer that detailed request directly in this same response", NORMAL_RESPONSE_INSTRUCTIONS)
        self.assertIn("At most one brief natural lead-in is allowed", NORMAL_RESPONSE_INSTRUCTIONS)
        self.assertIn("Never say you need a moment", NORMAL_RESPONSE_INSTRUCTIONS)

    def test_normal_compact_policy_is_still_preserved(self) -> None:
        self.assertIn("at most two complete spoken sentences", NORMAL_RESPONSE_INSTRUCTIONS)
        self.assertIn("no more than about 35 words", NORMAL_RESPONSE_INSTRUCTIONS)
        self.assertIn("Always finish the sentence you start", NORMAL_RESPONSE_INSTRUCTIONS)

    def test_inline_caption_is_scrollable_without_resizing_presence(self) -> None:
        viewport = re.search(r"\.caption__viewport\s*\{([^}]*)\}", STYLES, re.S)
        frame = re.search(r"\.caption-frame\s*\{([^}]*)\}", STYLES, re.S)
        self.assertIsNotNone(viewport)
        self.assertIsNotNone(frame)
        self.assertIn("overflow-y: auto", viewport.group(1))
        self.assertIn("height: 15vmin", frame.group(1))
        self.assertIn("max-height: 15vmin", frame.group(1))

    def test_user_scroll_owns_viewport_until_returning_to_latest(self) -> None:
        self.assertIn("captionStickToLatestRef", APP)
        self.assertIn("const handleCaptionScroll", APP)
        self.assertIn("distanceFromBottom <= 24", APP)
        self.assertIn("if (captionStickToLatestRef.current)", APP)
        self.assertIn("onScroll={handleCaptionScroll}", APP)
        self.assertIn("caption-frame--browsing", APP)
        self.assertIn(".caption-frame--browsing .caption__viewport", STYLES)

    def test_fullscreen_reader_remains_available(self) -> None:
        self.assertIn('aria-label="Expand full response text"', APP)
        self.assertIn('aria-label="Full Jarvis response"', APP)
        self.assertIn("overflow-y: auto", STYLES)


if __name__ == "__main__":
    unittest.main()
