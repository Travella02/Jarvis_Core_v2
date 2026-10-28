"""Repair3: grounded YouTube follow-up context and delayed watch URL verification.

No browser launch, live service, or account data. Verify safety properties with
an in-memory extension and true turn-bound Core gateway authorization.
"""
import unittest

from apps.desktop_managed_browser import ManagedDesktopBrowserSession
from core.tools.default_browser_bridge import DefaultBrowserBridgeAdapter
from core.tools.managed_browser import trusted_intent
from tests.unit.test_0_1_5_9_browser_result_selection import FakeBrowserBridge
from tests.unit.test_0_1_5_6_browser_bridge import FakeExtension


class ContextualSearchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.extension = FakeExtension()
        self.os = []
        self.adapter = DefaultBrowserBridgeAdapter(
            self.extension, open_default=lambda url: self.os.append(url) or True)
        self.session = ManagedDesktopBrowserSession(browser=self.adapter, advanced=True, bridge_mode=True)
        self.turn = 0

    async def ask(self, text, *, site='youtube.com', query='Sidemen'):
        self.turn += 1
        self.session.on_turn_started(self.turn)
        return await self.session.handle(
            turn=self.turn, selected_tool='browser_action', source='voice',
            binding=f'item_{self.turn}', transcript=text,
            arguments={'site':site,'intent':'search','query':query})

    async def test_current_youtube_allows_natural_video_search_followup(self):
        outcome = await self.ask('Jarvis find me some videos from the Sidemen.')
        self.assertEqual(outcome.status, 'completed', outcome)
        self.assertIn('search_query=Sidemen', self.extension.tabs[0]['url'])
        self.assertEqual(self.os, [])
        self.assertEqual(sum(op=='navigate' for op,_ in self.extension.operations), 1)

    async def test_explicit_youtube_search_still_works_without_bridge(self):
        self.extension.connected = False
        outcome = await self.ask('Search YouTube for Sidemen')
        self.assertEqual(outcome.status, 'completed', outcome)
        self.assertEqual(len(self.os), 1)

    async def test_does_not_infer_youtube_from_an_unrelated_active_tab(self):
        self.extension.active = 4   # Google is active; YouTube only in background
        outcome = await self.ask('Find some videos from the Sidemen')
        self.assertEqual(outcome.code, 'unverified_user_intent')
        self.assertEqual(self.os, [])
        self.assertFalse(any(op=='navigate' for op,_ in self.extension.operations))

    async def test_does_not_infer_when_extension_disconnected(self):
        self.extension.connected = False
        outcome = await self.ask('Find some videos from the Sidemen')
        self.assertEqual(outcome.code, 'unverified_user_intent')
        self.assertEqual(self.os, [])

    async def test_does_not_authorize_invented_query_or_other_site(self):
        for text,site,query in [
            ('Find some videos from the Sidemen','youtube.com','bank account'),
            ('Find some videos from the Sidemen','google.com','Sidemen'),
            ('Find videos from Sidemen on Google','youtube.com','Sidemen'),
            ('Find Sidemen','youtube.com','Sidemen'),
            ("Don't find me some videos from the Sidemen",'youtube.com','Sidemen'),
            ('What if you found videos from Sidemen?','youtube.com','Sidemen'),
            ('Find videos from Sidemen and send a message','youtube.com','Sidemen'),
            ('Find videos from Sidemen tomorrow','youtube.com','Sidemen'),
        ]:
            with self.subTest(text=text,site=site,query=query):
                outcome = await self.ask(text,site=site,query=query)
                self.assertEqual(outcome.code,'unverified_user_intent',outcome)
        self.assertEqual(self.os, [])
        self.assertFalse(any(op=='navigate' for op,_ in self.extension.operations))

    async def test_snapshot_must_agree_with_active_tab_identity_and_https(self):
        self.extension.tabs[0]['url'] = 'http://www.youtube.com/'
        self.assertFalse(await self.adapter.verify_active_site('youtube.com'))
        self.extension.tabs[0]['url'] = 'https://www.youtube.com/'
        self.assertFalse(await self.adapter.verify_active_site('google.com'))
        self.extension.tabs[0]['url'] = 'https://www.youtube.com/'
        self.assertTrue(await self.adapter.verify_active_site('youtube.com'))

    def test_transcript_only_does_not_authorize_implicit_site(self):
        self.assertFalse(trusted_intent('Find some videos from the Sidemen','search','youtube.com',query='Sidemen'))
        self.assertTrue(trusted_intent('Find some videos from the Sidemen','search','youtube.com',query='Sidemen',active_site_verified=True))
        self.assertFalse(trusted_intent('Find some videos from the Sidemen','search','youtube.com',query='Finance',active_site_verified=True))


class DelayedNavigationBridge(FakeBrowserBridge):
    def __init__(self):
        super().__init__()
        self.initial_url = self.tabs[0]['url']
        self.stale_reads = 0
        self.force_wrong_video = False

    async def execute(self, op, args=None, **kwargs):
        result = await super().execute(op, args, **kwargs)
        if op == 'tabs_list' and self.stale_reads > 0:
            self.stale_reads -= 1
            for tab in result.get('tabs', []):
                if tab.get('id') == 11:
                    tab['url'] = self.initial_url
            if result.get('active_tab', {}).get('id') == 11:
                result['active_tab']['url'] = self.initial_url
        if op == 'navigate':
            self.stale_reads = 3
            if self.force_wrong_video:
                self.tabs[0]['url'] = 'https://www.youtube.com/watch?v=XXXXXXXXXXX'
        return result


class ResultVerificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_eventually_visible_url_counts_as_verified(self):
        bridge = DelayedNavigationBridge()
        adapter = DefaultBrowserBridgeAdapter(bridge)
        ok = await adapter.select_result(1)
        self.assertTrue(ok)
        self.assertTrue(adapter.last_navigation_verified)
        self.assertEqual(adapter.last_navigation_route,'selected_video_same_tab')
        self.assertEqual(sum(op=='navigate' for op,_ in bridge.ops),1)

    async def test_never_claim_success_from_navigation_ack_alone(self):
        bridge = DelayedNavigationBridge()
        bridge.force_wrong_video = True
        adapter = DefaultBrowserBridgeAdapter(bridge)
        ok = await adapter.select_result(1)
        self.assertFalse(ok)
        self.assertFalse(adapter.last_navigation_verified)
        self.assertEqual(adapter.last_navigation_route,'result_navigation_unverified')
        self.assertEqual(sum(op=='navigate' for op,_ in bridge.ops),1)

    async def test_unchanged_extension_safety_guards(self):
        bridge = DelayedNavigationBridge()
        bridge.focus_swap = True
        adapter = DefaultBrowserBridgeAdapter(bridge)
        self.assertFalse(await adapter.select_result(1))
        self.assertFalse(any(op=='navigate' for op,_ in bridge.ops))

if __name__ == '__main__': unittest.main()
