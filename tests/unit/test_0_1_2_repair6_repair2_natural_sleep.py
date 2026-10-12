"""Repair6-Repair2: natural sign-offs belong to lifecycle, not normal replies."""
from __future__ import annotations

import json
import unittest

from providers.voice_frontend.openai_realtime.webrtc import (
    ROUTE_TURN_TOOL,
    ROUTE_TURN_TOOL_NAME,
    TURN_ROUTER_INSTRUCTIONS,
)
from tests.integration import test_0_1_2_repair3_routing_bridge as bridge_fixtures


class Repair6Repair2NaturalSleepPromptTests(unittest.TestCase):
    def test_router_covers_natural_conversation_closures(self) -> None:
        prompt = TURN_ROUTER_INSTRUCTIONS.lower()
        self.assertIn('thanks jarvis, that\'s all', prompt)
        self.assertIn('that\'s everything, thank you', prompt)
        self.assertIn('i\'m done for now', prompt)
        self.assertIn('with no audible reply', prompt)

    def test_router_does_not_treat_gratitude_alone_as_sleep(self) -> None:
        prompt = TURN_ROUTER_INSTRUCTIONS.lower()
        self.assertIn('simple "thanks" (without closure)', prompt)
        self.assertIn('new/follow-up request', prompt)
        self.assertIn('when the user is still asking for help', prompt)

    def test_sleep_intent_is_semantic_not_local_keyword_fast_path(self) -> None:
        self.assertEqual(ROUTE_TURN_TOOL_NAME, 'route_jarvis_turn')
        self.assertIn('sleep', ROUTE_TURN_TOOL['parameters']['properties']['route']['enum'])
        self.assertIn('closing phrase paired with thanks', ROUTE_TURN_TOOL['parameters']['properties']['route']['description'])
        self.assertIn('for direct or sleep, omit request', TURN_ROUTER_INSTRUCTIONS.lower())


class Repair6Repair2NaturalSleepBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_semantically_selected_sleep_stays_silent(self) -> None:
        fixture = bridge_fixtures.Repair3RoutingBridgeTests()
        bridge, conversation, relay = fixture.make_bridge()
        handled = await bridge.handle_event({
            'type': 'response.function_call_arguments.done',
            'name': ROUTE_TURN_TOOL_NAME,
            'call_id': 'polite_sleep',
            'arguments': json.dumps({'route': 'sleep', 'sleep_evidence': "that's all"}),
        })
        self.assertTrue(handled)
        self.assertEqual(conversation.calls, [])
        self.assertEqual(relay.outputs, [])
        self.assertEqual(relay.sleep_reasons, ['explicit_sleep'])

    async def test_non_sleep_still_uses_direct_path(self) -> None:
        fixture = bridge_fixtures.Repair3RoutingBridgeTests()
        bridge, conversation, relay = fixture.make_bridge()
        handled = await bridge.handle_event({
            'type': 'response.function_call_arguments.done',
            'name': ROUTE_TURN_TOOL_NAME,
            'call_id': 'thanks_without_closure',
            'arguments': json.dumps({'route': 'direct'}),
        })
        self.assertTrue(handled)
        self.assertEqual(conversation.calls, [])
        self.assertEqual(len(relay.outputs), 1)
        self.assertEqual(relay.outputs[0][1]['status'], 'direct')


if __name__ == '__main__':
    unittest.main()
