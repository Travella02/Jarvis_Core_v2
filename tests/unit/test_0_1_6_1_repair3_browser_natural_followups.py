"""0.1.6.1 Repair3: grounded natural browser follow-ups, fail-closed tests."""
import unittest
from apps.desktop_managed_browser import ManagedDesktopBrowserSession
from core.tools.default_browser_bridge import DefaultBrowserBridgeAdapter
from core.tools.managed_browser import trusted_intent, confirmed_youtube_pause_request
from tests.unit.test_0_1_6_1_repair2_browser_scrolling import ScrollingExtension
from tests.unit.test_0_1_5_9_browser_result_selection import FakeBrowserBridge


class BrowserNaturalFollowupTests(unittest.IsolatedAsyncioTestCase):
    def setup_scroll(self):
        self.bridge = ScrollingExtension()
        self.adapter = DefaultBrowserBridgeAdapter(self.bridge, open_default=lambda _:self.fail('unexpected OS browser'))
        self.session = ManagedDesktopBrowserSession(browser=self.adapter,advanced=True,bridge_mode=True)
        self.turn = 0
    def setup_media(self):
        self.bridge = FakeBrowserBridge()
        self.bridge.tabs[0]['url'] = 'https://www.youtube.com/watch?v=abcdefghijk'
        self.adapter = DefaultBrowserBridgeAdapter(self.bridge, open_default=lambda _:self.fail('unexpected OS browser'))
        self.session = ManagedDesktopBrowserSession(browser=self.adapter,advanced=True,bridge_mode=True)
        self.turn = 0
    async def ask(self,text,intent='scroll',site='current',direction=None,**extra):
        self.turn += 1
        self.session.on_turn_started(self.turn)
        args = {'intent':intent,'site':site,**extra}
        if direction is not None:args['direction']=direction
        return await self.session.handle(turn=self.turn,selected_tool='browser_action',source='voice',
            binding=f'item_{self.turn}',transcript=text,arguments=args)

    async def test_jump_to_bottom_corrects_model_down(self):
        self.setup_scroll()
        result=await self.ask('Jump to the bottom',direction='down')
        self.assertEqual(result.status,'completed',result)
        self.assertEqual(self.bridge.scroll_y,3200)
        self.assertIn(('scroll',{'direction':'bottom','tab_id':7,'expected_url':self.bridge.tabs[0]['url']}),self.bridge.operations)

    async def test_scroll_down_to_bottom_no_duplicate_direction(self):
        self.setup_scroll()
        result=await self.ask('Scroll down to the bottom',direction='down')
        self.assertEqual(result.status,'completed',result)
        self.assertEqual(self.bridge.scroll_y,3200)

    async def test_bottom_from_wrong_open_proposal_scoped_to_active_page(self):
        self.setup_scroll()
        result=await self.ask('Jump to bottom',intent='open',site='current')
        self.assertEqual(result.status,'completed',result)
        self.assertEqual(self.bridge.scroll_y,3200)

    async def test_keep_going_only_after_recent_verified_scroll(self):
        self.setup_scroll()
        first=await self.ask('Scroll down a bit',direction='down')
        self.assertEqual(first.status,'completed',first)
        second=await self.ask('Keep going',direction='up')
        self.assertEqual(second.status,'completed',second)
        self.assertEqual(self.bridge.scroll_y,1152)

    async def test_keep_going_not_authorized_without_recent_scroll(self):
        self.setup_scroll()
        result=await self.ask('Keep going',direction='down')
        self.assertEqual(result.code,'unverified_user_intent')
        self.assertEqual(self.bridge.scroll_y,0)

    async def test_keep_going_reject_changed_active_tab(self):
        self.setup_scroll()
        self.assertEqual((await self.ask('Scroll down',direction='down')).status,'completed')
        self.bridge.active_id=8
        result=await self.ask('Keep going',direction='down')
        self.assertEqual(result.code,'unverified_user_intent')
        self.assertEqual(self.bridge.scroll_y,576)

    async def test_keep_going_after_intervening_action_denied(self):
        self.setup_scroll()
        self.assertEqual((await self.ask('Scroll down',direction='down')).status,'completed')
        self.assertEqual((await self.ask('Scroll up',direction='up')).status,'completed')
        self.assertEqual((await self.ask('Pause YouTube',intent='open',site='youtube.com')).status,'failed')
        result=await self.ask('Keep going',direction='up')
        self.assertEqual(result.code,'unverified_user_intent')

    async def test_pause_youtube_mistaken_open_is_scoped_media_action(self):
        self.setup_media()
        result=await self.ask('Pause YouTube',intent='open',site='youtube.com')
        self.assertEqual(result.status,'completed',result)
        media=[args for op,args in self.bridge.ops if op=='media_control']
        self.assertEqual(media,[{'action':'pause','preferred_tab_id':11}])
        self.assertFalse(any(op=='navigate' for op,_ in self.bridge.ops))

    async def test_pause_youtube_video_mistaken_pause_site_is_corrected(self):
        self.setup_media()
        result=await self.ask('Pause the YouTube video',intent='pause',site='youtube.com')
        self.assertEqual(result.status,'completed',result)
        self.assertIn(('media_control',{'action':'pause','preferred_tab_id':11}),self.bridge.ops)

    async def test_pause_youtube_not_from_search_page(self):
        self.setup_media()
        self.bridge.tabs[0]['url']='https://www.youtube.com/results?search_query=Sidemen'
        result=await self.ask('Pause YouTube',intent='open',site='youtube.com')
        self.assertEqual(result.code,'unverified_user_intent')
        self.assertFalse(any(op=='media_control' for op,_ in self.bridge.ops))

    async def test_pause_youtube_not_from_unrelated_active_tab(self):
        self.setup_media()
        self.bridge.focus_swap=True
        result=await self.ask('Pause YouTube',intent='open',site='youtube.com')
        self.assertEqual(result.code,'unverified_user_intent')
        self.assertFalse(any(op=='media_control' for op,_ in self.bridge.ops))

    async def test_negation_hypothetical_and_compound_do_not_execute(self):
        for t in ["Don't pause YouTube", 'What if we paused YouTube?',
                  'Pause YouTube and open a new tab','I was thinking about pausing YouTube']:
            with self.subTest(t=t):
                self.setup_media()
                result=await self.ask(t,intent='open',site='youtube.com')
                self.assertEqual(result.status,'failed')
                self.assertFalse(any(op=='media_control' for op,_ in self.bridge.ops))

    async def test_wrong_scroll_or_hypothetical_never_reconciled(self):
        self.setup_scroll()
        for t in ['What if you jumped to bottom?',"Don't jump to the bottom",'Scroll down then jump to bottom']:
            with self.subTest(t=t):
                result=await self.ask(t,intent='open',site='current')
                self.assertEqual(result.status,'failed',result)
        self.assertFalse(any(op=='scroll' for op,_ in self.bridge.operations))

    def test_independent_authorization(self):
        self.assertTrue(trusted_intent('Jump to the bottom','scroll','current',direction='bottom'))
        self.assertTrue(trusted_intent('Scroll down to bottom','scroll','current',direction='bottom'))
        self.assertFalse(trusted_intent('Scroll down to bottom','scroll','current',direction='down'))
        self.assertFalse(trusted_intent('Keep going','scroll','current',direction='down'))
        self.assertTrue(trusted_intent('Keep going','scroll','current',direction='down',scroll_continuation_verified=True))
        self.assertTrue(confirmed_youtube_pause_request('Pause YouTube'))
        self.assertFalse(confirmed_youtube_pause_request('What if you paused YouTube?'))
        self.assertFalse(confirmed_youtube_pause_request('Pause YouTube and open a new tab'))
        self.assertFalse(trusted_intent('Pause YouTube','pause','current'))
        self.assertTrue(trusted_intent('Pause YouTube','pause','current',active_media_verified=True))

if __name__=='__main__': unittest.main()
