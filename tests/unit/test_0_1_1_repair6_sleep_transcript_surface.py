from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / "apps" / "desktop" / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
STYLES = (ROOT / "apps" / "desktop" / "ui" / "src" / "styles.css").read_text(encoding="utf-8")
REALTIME = (ROOT / "providers" / "voice_frontend" / "openai_realtime" / "webrtc.py").read_text(encoding="utf-8")


class Repair6SleepTranscriptSurfaceTests(unittest.TestCase):
    def test_per_turn_policy_preserves_silent_sleep_tool_priority(self) -> None:
        self.assertIn("Lifecycle/tool control has higher priority than spoken formatting", REALTIME)
        self.assertIn("call sleep_jarvis immediately as the initial and only output", REALTIME)
        self.assertIn("Never acknowledge an explicit sleep request", REALTIME)
        self.assertIn("delegate_to_jarvis_core", REALTIME)
        self.assertIn("request_expanded_response", REALTIME)

    def test_sleep_transition_also_closes_expanded_transcript(self) -> None:
        sleep = APP.index("const enterSleep = async")
        expanded = APP.index("setTranscriptExpanded(false);", sleep)
        teardown = APP.index("await stopRealtimeSession", sleep)
        self.assertLess(expanded, teardown)

    def test_caption_surface_has_fixed_height_so_long_text_cannot_move_orb(self) -> None:
        frame = re.search(r"\.caption-frame\s*\{([^}]*)\}", STYLES, re.S)
        self.assertIsNotNone(frame)
        block = frame.group(1)
        self.assertIn("height: 15vmin", block)
        self.assertIn("min-height: 15vmin", block)
        self.assertIn("max-height: 15vmin", block)
        self.assertIn("flex: 0 0 15vmin", block)

    def test_long_caption_auto_scrolls_to_keep_latest_text_visible(self) -> None:
        self.assertIn("captionViewportRef", APP)
        self.assertIn("viewport.scrollTop = viewport.scrollHeight", APP)
        self.assertIn("viewport.scrollHeight > viewport.clientHeight + 4", APP)
        viewport = re.search(r"\.caption__viewport\s*\{([^}]*)\}", STYLES, re.S)
        self.assertIsNotNone(viewport)
        self.assertIn("overflow-y: auto", viewport.group(1))

    def test_overflow_fades_old_text_at_top_only(self) -> None:
        self.assertIn(".caption-frame--overflow .caption__viewport", STYLES)
        self.assertIn("mask-image: linear-gradient(to bottom, transparent", STYLES)

    def test_overflow_exposes_full_response_overlay(self) -> None:
        self.assertIn("captionOverflow && caption", APP)
        self.assertIn('aria-label="Expand full response text"', APP)
        self.assertIn('className="transcript-overlay"', APP)
        self.assertIn('aria-label="Full Jarvis response"', APP)
        self.assertIn("if (event.key === 'Escape') setTranscriptExpanded(false)", APP)
        self.assertIn("position: fixed", STYLES)

    def test_repair_does_not_change_response_budgets_or_realtime_model(self) -> None:
        self.assertIn("DEFAULT_REALTIME_MAX_OUTPUT_TOKENS = 1024", REALTIME)
        self.assertIn("EXPANDED_REALTIME_MAX_OUTPUT_TOKENS = 2048", REALTIME)
        config = (ROOT / "providers" / "voice_frontend" / "openai_realtime" / "config.py").read_text(encoding="utf-8")
        self.assertIn("gpt-realtime-2.1-mini", config)


if __name__ == "__main__":
    unittest.main()
