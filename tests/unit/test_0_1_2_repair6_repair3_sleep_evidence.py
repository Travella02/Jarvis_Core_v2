"""0.1.2 Repair6-Repair3: explicit closure evidence, not mere gratitude, authorizes sleep."""
import json
import unittest

from providers.voice_frontend.openai_realtime.webrtc import ROUTE_TURN_TOOL, TURN_ROUTER_INSTRUCTIONS
from tests.integration.test_0_1_2_repair3_routing_bridge import Repair3RoutingBridgeTests


class RouterContractTests(unittest.TestCase):
    def test_direct_gratitude_examples_and_closure_contrasts(self):
        prompt = TURN_ROUTER_INSTRUCTIONS.lower()
        self.assertIn('"thanks, jarvis." -> direct', prompt)
        self.assertIn('"thanks, jarvis, that\'s all." -> sleep', prompt)
        self.assertIn('"thank you, that helps." -> direct', prompt)
        self.assertIn('"thanks, jarvis, can i ask another question?" -> direct', prompt)
        self.assertIn('never invent closure words', prompt)

    def test_tool_has_independent_sleep_evidence_field(self):
        props = ROUTE_TURN_TOOL['parameters']['properties']
        self.assertIn('sleep_evidence', props)
        self.assertEqual(props['sleep_evidence']['type'], 'string')
        self.assertIn('excluding mere thanks', props['sleep_evidence']['description'])
        self.assertEqual(ROUTE_TURN_TOOL['parameters']['required'], ['route'])


class SleepEvidenceBridgeTests(unittest.IsolatedAsyncioTestCase):
    def create(self):
        return Repair3RoutingBridgeTests().make_bridge()

    async def route(self, bridge, route, *, evidence=None):
        args = {'route': route}
        if evidence is not None:
            args['sleep_evidence'] = evidence
        bridge.note_route_telemetry(call_id='route-evidence', turn=42)
        return await bridge.handle_event({
            'type': 'response.function_call_arguments.done',
            'name': 'route_jarvis_turn',
            'call_id': 'route-evidence',
            'arguments': json.dumps(args),
        })

    async def test_explicit_closure_evidence_allows_silent_sleep(self):
        bridge, conversation, relay = self.create()
        self.assertTrue(await self.route(bridge, 'sleep', evidence="that's all"))
        self.assertEqual(relay.sleep_reasons, ['explicit_sleep'])
        self.assertEqual(relay.outputs, [])
        self.assertEqual(conversation.calls, [])

    async def test_missing_evidence_prevents_unverified_sleep(self):
        bridge, conversation, relay = self.create()
        self.assertTrue(await self.route(bridge, 'sleep'))
        self.assertEqual(relay.sleep_reasons, [])
        self.assertEqual(relay.outputs[0][1]['status'], 'direct')
        self.assertEqual(conversation.calls, [])
        self.assertEqual(relay.outputs[0][3]['tools'], [])

    async def test_blank_evidence_prevents_unverified_sleep(self):
        bridge, conversation, relay = self.create()
        self.assertTrue(await self.route(bridge, 'sleep', evidence='   '))
        self.assertEqual(relay.sleep_reasons, [])
        self.assertEqual(relay.outputs[0][1]['status'], 'direct')

    async def test_direct_route_does_not_require_evidence(self):
        bridge, conversation, relay = self.create()
        self.assertTrue(await self.route(bridge, 'direct'))
        self.assertEqual(relay.sleep_reasons, [])
        self.assertEqual(relay.outputs[0][1]['status'], 'direct')


if __name__ == '__main__':
    unittest.main()
