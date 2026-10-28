"""Repair4: observations stay conversational, Core remains the action authority."""
from pathlib import Path
import unittest

from apps.desktop_managed_browser import ManagedDesktopBrowserSession
from core.tools.default_browser_bridge import DefaultBrowserBridgeAdapter
from core.tools.managed_browser import trusted_intent
from tests.unit.test_0_1_5_6_browser_bridge import FakeExtension

ROOT = Path(__file__).resolve().parents[2]


class NonRequestCoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.extension = FakeExtension()
        self.opened = []
        self.adapter = DefaultBrowserBridgeAdapter(self.extension, open_default=lambda url: self.opened.append(url) or True)
        self.session = ManagedDesktopBrowserSession(browser=self.adapter, advanced=True, bridge_mode=True)
        self.turn = 0

    async def ask(self, text, *, query='MrBeast'):
        self.turn += 1
        self.session.on_turn_started(self.turn)
        return await self.session.handle(
            turn=self.turn, selected_tool='browser_action', source='voice',
            binding=f'item_{self.turn}', transcript=text,
            arguments={'site': 'youtube.com', 'intent': 'search', 'query': query})

    async def test_observations_do_not_authorize_youtube_search(self):
        for phrase in [
            'I was thinking about searching for MrBeast videos.',
            'I am considering searching for MrBeast videos.',
            'I have been debating whether to search YouTube for MrBeast videos.',
            'I was planning to search YouTube for MrBeast videos.',
            'I wonder what if you searched YouTube for MrBeast videos?',
            'What if you searched YouTube for MrBeast videos?',
            "Don't search YouTube for MrBeast videos.",
        ]:
            with self.subTest(phrase=phrase):
                result = await self.ask(phrase)
                self.assertEqual(result.code, 'unverified_user_intent', result)
        self.assertEqual(self.opened, [])
        self.assertFalse(any(op == 'navigate' for op, _ in self.extension.operations))

    async def test_genuine_natural_request_still_executes(self):
        result = await self.ask('Could you please search YouTube for MrBeast videos?')
        self.assertEqual(result.status, 'completed', result)
        self.assertTrue(any('search_query=MrBeast' in tab.get('url', '') for tab in self.extension.tabs))

    def test_transcript_intent_guard_not_command_phrase_dispatch(self):
        self.assertFalse(trusted_intent('I was thinking about asking you to search YouTube for MrBeast videos',
                                        'search', 'youtube.com', query='MrBeast', active_site_verified=True))
        self.assertFalse(trusted_intent('I am contemplating whether to search YouTube for MrBeast videos',
                                        'search', 'youtube.com', query='MrBeast', active_site_verified=True))
        self.assertTrue(trusted_intent('Please search YouTube for MrBeast videos',
                                       'search', 'youtube.com', query='MrBeast', active_site_verified=True))


class ConversationalRecoveryContractTests(unittest.TestCase):
    def test_backend_relays_verified_denial_code(self):
        server = (ROOT / 'apps/desktop_alpha.py').read_text(encoding='utf-8')
        self.assertIn("'status':result.status, 'code':result.code, 'text':result.text", server)

    def test_ui_uses_original_turn_not_model_proposed_arguments(self):
        app = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        self.assertIn("code !== 'unverified_user_intent'", app)
        self.assertIn("input.binding !== overlapInputBindingRef.current", app)
        self.assertIn("overlapSleepInputRef.current?.turn === turn", app)
        self.assertIn("originalUtterance", app)
        self.assertIn("origin:'intent_unverified'", app)
        self.assertIn("tools:[],tool_choice:'none'", app)
        self.assertIn("No browser action was taken.", app)

    def test_ordinary_failures_still_get_spoken_errors(self):
        app = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        self.assertIn("announceActionProblem(turn,status,message);", app)
        self.assertIn("code !== 'unverified_user_intent'", app)

    def test_model_proposes_actions_only_for_actual_requests(self):
        app = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        self.assertIn('Never turn a description of a possible future action into an immediate tool call.', app)
        self.assertIn('Never claim completion before Core reports it.', app)


if __name__ == '__main__':
    unittest.main()
