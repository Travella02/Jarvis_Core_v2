"""0.1.5.8 Repair 4 — natural return and search, offline and silent."""
from __future__ import annotations

import unittest

from apps.desktop_managed_browser import ManagedDesktopBrowserSession
from core.tools.managed_browser import confirmed_site_search_query
from tests.unit.test_0_1_5_8_repair3_tab_reuse import SimulatedBridge
from core.tools.default_browser_bridge import DefaultBrowserBridgeAdapter


class ReturnAndSearchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bridge=SimulatedBridge(tabs=[
            {'id':11,'url':'https://www.youtube.com/results?search_query=Sidemen','window_id':1,'active':False},
            {'id':12,'url':'https://www.wikipedia.org/','window_id':1,'active':True},
        ])
        self.os=[]
        self.adapter=DefaultBrowserBridgeAdapter(self.bridge,open_default=lambda url:self.os.append(url) or True)
        self.session=ManagedDesktopBrowserSession(browser=self.adapter,advanced=True,bridge_mode=True)
        self.turn=0

    async def request(self, text, args):
        self.turn+=1
        self.session.on_turn_started(self.turn)
        return await self.session.handle(turn=self.turn, selected_tool='browser_action',
            source='voice', binding='item_'+str(self.turn), transcript=text, arguments=args)

    async def test_return_and_search_single_action_reuses_background_tab(self):
        outcome=await self.request('Hey, can we go back to YouTube and search for soccer videos?',
           {'site':'youtube.com','intent':'search','query':'soccer videos'})
        self.assertEqual(outcome.status,'completed',outcome)
        self.assertEqual(self.adapter.last_navigation_route,'reused_connected_tab')
        self.assertEqual(len(self.bridge.tabs),2)
        self.assertEqual(self.os,[])
        self.assertIn('soccer+videos', self.bridge.tabs[0]['url'])
        self.assertIn('wikipedia.org', self.bridge.tabs[1]['url'])
        self.assertEqual(len([x for x in self.bridge.operations if x[0]=='navigate']),1)

    async def test_select_tab_plus_grounded_search_query_coerces_to_search(self):
        outcome=await self.request('Switch back to the YouTube tab and search for soccer',
            {'site':'youtube.com','intent':'select_tab','query':'soccer'})
        self.assertEqual(outcome.status,'completed',outcome)
        self.assertIn('soccer',self.bridge.tabs[0]['url'])
        self.assertEqual(self.os,[])
        self.assertFalse(any(op=='tab_switch' for op,_ in self.bridge.operations))

    async def test_open_plus_grounded_search_query_coerces_to_search(self):
        outcome=await self.request('Return to YouTube and find soccer videos',
            {'site':'youtube.com','intent':'open','query':'soccer videos'})
        self.assertEqual(outcome.status,'completed',outcome)
        self.assertIn('soccer+videos',self.bridge.tabs[0]['url'])

    async def test_unverified_query_must_not_execute(self):
        outcome=await self.request('Switch back to the YouTube tab and search for soccer',
            {'site':'youtube.com','intent':'select_tab','query':'bank account'})
        self.assertEqual(outcome.status,'failed')
        self.assertEqual(self.os,[])
        self.assertFalse(any(op=='navigate' for op,_ in self.bridge.operations))

    async def test_missing_query_is_not_invented(self):
        outcome=await self.request('Switch back to the YouTube tab and search for soccer',
            {'site':'youtube.com','intent':'select_tab'})
        self.assertEqual(outcome.status,'failed')
        self.assertEqual(self.os,[])
        self.assertFalse(any(op in ('navigate','tab_switch') for op,_ in self.bridge.operations))

    async def test_negated_and_hypothetical_requests_denied(self):
        for text in ["Don't switch to YouTube and search for soccer",
                     'What if you went back to YouTube and searched for soccer?']:
            outcome=await self.request(text,{'site':'youtube.com','intent':'search','query':'soccer'})
            self.assertEqual(outcome.status,'failed',text)
        self.assertEqual(self.os,[])
        self.assertFalse(any(op=='navigate' for op,_ in self.bridge.operations))

    async def test_model_cannot_retarget_unrelated_site(self):
        result=await self.request('Go back to YouTube and search for soccer',
            {'site':'google.com','intent':'select_tab','query':'soccer'})
        self.assertEqual(result.status,'failed')
        self.assertFalse(any(op=='navigate' for op,_ in self.bridge.operations))

    async def test_no_extension_falls_back_to_os_default_without_reuse_claim(self):
        self.bridge.connected=False
        outcome=await self.request('Go back to YouTube and search for soccer',
            {'site':'youtube.com','intent':'search','query':'soccer'})
        self.assertEqual(outcome.status,'completed')
        self.assertEqual(self.adapter.last_navigation_route,'default_bridge_disconnected')
        self.assertEqual(len(self.os),1)
        self.assertFalse(self.adapter.last_navigation_verified)

    def test_non_model_subject_must_not_be_inferred(self):
        self.assertFalse(confirmed_site_search_query('Switch to YouTube and search for soccer',
                                                     'youtube.com','investment tips'))

if __name__=='__main__':unittest.main()
