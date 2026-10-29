"""0.1.6.1 Repair1: reconcile Mini browser proposals safely from confirmed speech."""
import unittest

from apps.desktop_managed_browser import ManagedDesktopBrowserSession
from core.tools.default_browser_bridge import DefaultBrowserBridgeAdapter
from core.tools.managed_browser import confirmed_result_selection_index
from tests.unit.test_0_1_5_9_browser_result_selection import FakeBrowserBridge


class NaturalFollowUpTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bridge = FakeBrowserBridge()
        self.opened = []
        self.adapter = DefaultBrowserBridgeAdapter(
            self.bridge, open_default=lambda uri: self.opened.append(uri) or True)
        self.session = ManagedDesktopBrowserSession(
            browser=self.adapter, advanced=True, bridge_mode=True)
        self.turn = 0

    async def ask(self, transcript, intent='open', site='current', **extra):
        self.turn += 1
        self.session.on_turn_started(self.turn)
        return await self.session.handle(
            turn=self.turn, selected_tool='browser_action',
            source='voice', binding=f'item_{self.turn}', transcript=transcript,
            arguments={'intent': intent, 'site': site, **extra})

    async def test_open_current_reconciles_first_one_to_verified_selection(self):
        outcome = await self.ask("Let's watch the first one")
        self.assertEqual(outcome.status, 'completed', outcome)
        self.assertEqual(sum(op == 'navigate' for op, _ in self.bridge.ops), 1)
        self.assertIn('abcdefghijk', self.bridge.tabs[0]['url'])
        self.assertEqual(self.opened, [])

    async def test_play_current_reconciles_second_one(self):
        outcome = await self.ask('Can we watch the second one?', intent='play')
        self.assertEqual(outcome.status, 'completed', outcome)
        self.assertIn('ZYXWVUTSRQP', self.bridge.tabs[0]['url'])

    async def test_site_youtube_open_proposal_can_reconcile_only_when_spoken(self):
        outcome = await self.ask('Please select the first video', site='youtube.com')
        self.assertEqual(outcome.status, 'completed', outcome)

    async def test_arbitrary_site_and_invented_ordinal_do_not_reconcile(self):
        for transcript, site in [
            ('Please watch the first one', 'google.com'),
            ('Open YouTube', 'current'),
            ('Play a video', 'current'),
            ('Watch the first and second ones', 'current'),
            ("Don't watch the first one", 'current'),
            ('What if we watched the first one?', 'current'),
            ('I was considering watching the first one', 'current'),
        ]:
            with self.subTest(transcript=transcript):
                outcome = await self.ask(transcript, site=site)
                self.assertEqual(outcome.status, 'failed', outcome)
        self.assertFalse(any(op == 'navigate' for op, _ in self.bridge.ops))

    async def test_no_selection_from_unrelated_site_or_missing_extension(self):
        self.bridge.tabs[0]['url'] = 'https://www.wikipedia.org/'
        outcome = await self.ask('Watch the first one')
        self.assertEqual(outcome.status, 'failed')
        self.assertFalse(any(op == 'navigate' for op, _ in self.bridge.ops))
        self.bridge.tabs[0]['url'] = 'https://www.youtube.com/results?search_query=rocket+league'
        self.bridge.connected = False
        outcome = await self.ask('Watch the first one')
        self.assertEqual(outcome.status, 'failed')
        self.assertFalse(any(op == 'navigate' for op, _ in self.bridge.ops))

    async def test_compound_media_does_not_execute_only_one_half(self):
        outcome = await self.ask('Pause that, then resume it', intent='pause')
        self.assertEqual(outcome.status, 'failed')
        self.assertFalse(any(op == 'media_control' for op, _ in self.bridge.ops))

    def test_ordinal_evidence_is_transcript_only(self):
        self.assertEqual(confirmed_result_selection_index("Let's watch the first one"), 1)
        self.assertEqual(confirmed_result_selection_index('Pick the second one'), 2)
        for utterance in ['Open YouTube', 'Play a video', "Don't watch the first one",
                          'What if we watched the first one?', 'Watch the first and second ones',
                          'Pause the video then resume it']:
            self.assertIsNone(confirmed_result_selection_index(utterance))


if __name__ == '__main__':
    unittest.main()
