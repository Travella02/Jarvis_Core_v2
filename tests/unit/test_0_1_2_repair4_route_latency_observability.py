from __future__ import annotations

import unittest
from pathlib import Path

from providers.voice_frontend.openai_realtime.webrtc import (
    ROUTER_REALTIME_MAX_OUTPUT_TOKENS,
    ROUTER_REALTIME_REASONING_EFFORT,
    ROUTE_TURN_TOOL,
    TURN_ROUTER_INSTRUCTIONS,
)

ROOT = Path(__file__).resolve().parents[2]
DESKTOP_HOST = (ROOT / "apps" / "desktop_alpha.py").read_text(encoding="utf-8")
APP = (ROOT / "apps" / "desktop" / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
BRIDGE = (ROOT / "providers" / "voice_frontend" / "openai_realtime" / "bridge.py").read_text(encoding="utf-8")


class Repair4RouteLatencyObservabilityTests(unittest.TestCase):
    def test_router_uses_small_minimal_reasoning_response_policy(self) -> None:
        self.assertEqual(ROUTER_REALTIME_MAX_OUTPUT_TOKENS, 512)
        self.assertEqual(ROUTER_REALTIME_REASONING_EFFORT, "minimal")
        self.assertIn('"max_output_tokens": ROUTER_REALTIME_MAX_OUTPUT_TOKENS', DESKTOP_HOST)
        self.assertIn('"instructions": TURN_ROUTER_INSTRUCTIONS', DESKTOP_HOST)
        self.assertNotIn('NORMAL_RESPONSE_INSTRUCTIONS + "\n\n" + TURN_ROUTER_INSTRUCTIONS', DESKTOP_HOST)
        self.assertIn('"reasoning": {"effort": ROUTER_REALTIME_REASONING_EFFORT}', DESKTOP_HOST)
        self.assertIn('"metadata": {"jarvis_stage": "route"}', DESKTOP_HOST)

    def test_direct_route_does_not_need_to_repeat_user_request(self) -> None:
        self.assertEqual(ROUTE_TURN_TOOL["parameters"]["required"], ["route"])
        request = ROUTE_TURN_TOOL["parameters"]["properties"]["request"]
        self.assertIn("Core routes only", request["description"])
        self.assertIn("For direct or sleep, omit request", TURN_ROUTER_INSTRUCTIONS)
        direct_start = BRIDGE.index('if route == "direct"')
        direct_end = BRIDGE.index('if route not in {mode.value for mode in DelegationMode}', direct_start)
        direct_branch = BRIDGE[direct_start:direct_end]
        self.assertIn('{"status": "direct"}', direct_branch)
        self.assertNotIn('{"status": "direct", "request": request}', direct_branch)

    def test_renderer_reports_route_before_forwarding_route_event(self) -> None:
        handler_start = APP.index("const handleRealtimeEvent")
        forward_index = APP.index("forwardToCore(event)", handler_start)
        route_telemetry_index = APP.index("kind: 'desktop_route'", handler_start)
        self.assertLess(route_telemetry_index, forward_index)
        self.assertIn("speech_end_to_route_ms", APP)
        self.assertIn("route_to_first_audio_ms", APP)
        self.assertIn("jarvis_turn", APP)

    def test_console_contract_distinguishes_direct_and_core_ownership(self) -> None:
        self.assertIn("[Jarvis Route]", DESKTOP_HOST)
        self.assertIn("[Jarvis Direct]", DESKTOP_HOST)
        self.assertIn("owner={owner}", DESKTOP_HOST)
        self.assertIn("[Jarvis Core Call]", BRIDGE)
        self.assertIn("status=started", BRIDGE)
        self.assertIn("status=completed", BRIDGE)


if __name__ == "__main__":
    unittest.main()
