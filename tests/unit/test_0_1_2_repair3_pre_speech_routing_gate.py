import unittest
from pathlib import Path

from providers.voice_frontend.openai_realtime.webrtc import (
    DIRECT_ROUTED_RESPONSE_INSTRUCTIONS,
    ROUTE_TURN_TOOL,
    ROUTE_TURN_TOOL_NAME,
    TURN_ROUTER_INSTRUCTIONS,
)

ROOT = Path(__file__).resolve().parents[2]
DESKTOP_HOST = (ROOT / "apps" / "desktop_alpha.py").read_text(encoding="utf-8")
APP = (ROOT / "apps" / "desktop" / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
BRIDGE = (ROOT / "providers" / "voice_frontend" / "openai_realtime" / "bridge.py").read_text(encoding="utf-8")


class Repair3PreSpeechRoutingGateTests(unittest.TestCase):
    def test_desktop_first_response_is_forced_named_router_and_text_only(self) -> None:
        self.assertEqual(ROUTE_TURN_TOOL_NAME, "route_jarvis_turn")
        self.assertEqual(ROUTE_TURN_TOOL["name"], ROUTE_TURN_TOOL_NAME)
        self.assertIn('"output_modalities": ["text"]', DESKTOP_HOST)
        self.assertIn('"tools": [ROUTE_TURN_TOOL]', DESKTOP_HOST)
        self.assertIn('"tool_choice": {"type": "function", "name": ROUTE_TURN_TOOL_NAME}', DESKTOP_HOST)

    def test_router_contract_requires_route_and_keeps_core_request_field(self) -> None:
        route_schema = ROUTE_TURN_TOOL["parameters"]["properties"]["route"]
        self.assertEqual(
            route_schema["enum"],
            ["direct", "reasoning", "memory", "action", "current_data", "long_task", "sleep"],
        )
        self.assertEqual(ROUTE_TURN_TOOL["parameters"]["required"], ["route"])
        self.assertIn("Internal routing only", TURN_ROUTER_INSTRUCTIONS)
        self.assertIn("emit no user-facing prose", TURN_ROUTER_INSTRUCTIONS)
        self.assertIn("explicitly requests Core", TURN_ROUTER_INSTRUCTIONS)
        self.assertIn("For direct or sleep, omit request", TURN_ROUTER_INSTRUCTIONS)

    def test_user_facing_followup_disables_all_tools(self) -> None:
        helper_start = BRIDGE.index("def _spoken_response_overrides")
        helper_end = BRIDGE.index("async def _start_core_call", helper_start)
        helper = BRIDGE[helper_start:helper_end]
        self.assertIn('"output_modalities": ["audio"]', helper)
        self.assertIn('"tools": []', helper)
        self.assertIn('"tool_choice": "none"', helper)
        self.assertIn("Start with the useful answer itself", DIRECT_ROUTED_RESPONSE_INSTRUCTIONS)
        self.assertIn("Do not say 'let me think'", DIRECT_ROUTED_RESPONSE_INSTRUCTIONS)

    def test_renderer_suppresses_and_deletes_any_illegal_router_message(self) -> None:
        self.assertIn("const suppressTurnRouterOutput", APP)
        self.assertIn("route_jarvis_turn", APP)
        response_done = APP[APP.index("const routingCall"):APP.index("} else if (event.response?.status === 'completed')")]
        self.assertIn("suppressTurnRouterOutput(event)", response_done)
        self.assertIn("deleteSuppressedResponseMessages(event)", response_done)

    def test_router_route_updates_working_state_only_for_backend_work(self) -> None:
        branch_start = APP.index("event.name === 'route_jarvis_turn'")
        branch_end = APP.index("} else if (event.name === 'delegate_to_jarvis_core')", branch_start)
        branch = APP[branch_start:branch_end]
        self.assertIn("JSON.parse", branch)
        self.assertIn("['direct', 'sleep']", branch)
        self.assertIn("setStateSafely('working', 'Working')", branch)


if __name__ == "__main__":
    unittest.main()
