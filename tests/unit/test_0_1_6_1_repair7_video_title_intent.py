"""Repair7: typed and voice natural title requests survive Mini's tool-choice drift.

Only repairs a preexisting browser_action proposal, and never permits guesses,
model-invented titles, visual descriptors, other tabs, or hypothetical commands.
"""
import unittest
from core.tools.managed_browser import confirmed_video_title_request
from tests.unit.test_0_1_6_1_repair6_page_perception import PageBridge
from core.tools.default_browser_bridge import DefaultBrowserBridgeAdapter
from apps.desktop_managed_browser import ManagedDesktopBrowserSession

class NaturalTitleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bridge=PageBridge()
        self.adapter=DefaultBrowserBridgeAdapter(self.bridge,open_default=lambda _:self.fail('OS must not open a URL'))
        self.session=ManagedDesktopBrowserSession(browser=self.adapter,advanced=True,bridge_mode=True)
        self.n=0
    async def act(self, utterance, intent='select_match', site='current', query=None, source='voice'):
        self.n+=1
        self.session.on_turn_started(self.n)
        args={'site':site,'intent':intent}
        if query is not None: args['query']=query
        res=await self.session.handle(turn=self.n, selected_tool='browser_action', source=source,
            binding=('typed:'+str(self.n)) if source=='typed' else 'item_valid',
            transcript=utterance,arguments=args)
        return res
    def navigations(self):
        return [op for op,_ in self.bridge.ops if op=='navigate']
    async def test_exact_natural_typed_command_with_model_extra_search_topic(self):
        r=await self.act('play the how far you can get video',query='sidemen how far can you get',source='typed')
        self.assertEqual(r.status,'completed',r)
        self.assertEqual(self.bridge.tabs[0]['url'],'https://www.youtube.com/watch?v=abcdefghijk')
        self.assertEqual(self.navigations(),['navigate'])
    async def test_natural_voice_request_with_model_selected_play(self):
        r=await self.act('Play the how far you can get video',intent='play')
        self.assertEqual(r.status,'completed',r)
        self.assertEqual(self.navigations(),['navigate'])
    async def test_model_selected_open_site_current(self):
        r=await self.act('Play the how far you can get video',intent='open')
        self.assertEqual(r.status,'completed',r)
        self.assertEqual(self.navigations(),['navigate'])
    async def test_model_selected_open_pseudo_site(self):
        r=await self.act('Play the how far you can get video',intent='open',site='how far can you get')
        self.assertEqual(r.status,'completed',r)
        self.assertEqual(self.navigations(),['navigate'])
    async def test_original_titled_request_kept_working(self):
        r=await self.act('Jarvis play the video titled How Far Can You Get',query='How Far Can You Get')
        self.assertEqual(r.status,'completed',r)
    async def test_unrelated_invented_title_denied(self):
        r=await self.act('Play the red video',query='how far can you get')
        self.assertEqual(r.status,'failed',r)
        self.assertEqual(self.navigations(),[])
    async def test_wrong_real_domain_cannot_turn_into_video(self):
        r=await self.act('Play the how far you can get video',intent='open',site='google.com')
        self.assertEqual(r.status,'failed',r)
        self.assertEqual(self.navigations(),[])
    async def test_hypothetical_not_navigated(self):
        r=await self.act('What if we played the how far you can get video?',intent='play')
        self.assertEqual(r.status,'failed',r)
        self.assertEqual(self.navigations(),[])
    async def test_negation_not_navigated(self):
        r=await self.act("Don't play the how far you can get video",intent='play')
        self.assertEqual(r.status,'failed',r)
        self.assertEqual(self.navigations(),[])
    async def test_compound_not_navigated(self):
        r=await self.act('Play the how far you can get video and open a new tab',intent='play')
        self.assertEqual(r.status,'failed',r)
        self.assertEqual(self.navigations(),[])
    async def test_unsupported_visual_reference_not_navigated(self):
        r=await self.act('Play the one with the guy in the red coat',intent='play')
        self.assertEqual(r.status,'failed',r)
        self.assertEqual(self.navigations(),[])
    async def test_ambiguous_titles_not_navigated(self):
        self.bridge.elements[2]['label']='SIDEMEN How Far Can You Get Abroad'
        r=await self.act('play the how far you can get video',intent='play')
        self.assertEqual(r.status,'failed',r)
        self.assertEqual(self.navigations(),[])
    async def test_not_on_results_page_fails_closed(self):
        self.bridge.tabs[0]['url']='https://www.youtube.com/watch?v=abcdefghijk'
        r=await self.act('Play the how far you can get video',intent='play')
        self.assertEqual(r.status,'failed',r)
        self.assertEqual(self.navigations(),[])
    async def test_no_action_selected_no_execution(self):
        # The helper isn't called unless Mini already chose browser_action.
        # The actual handler requires that selection to establish a tool boundary.
        self.n+=1
        self.session.on_turn_started(self.n)
        r=await self.session.handle(turn=self.n,selected_tool='none',source='voice',
            binding='item_valid',transcript='Play the how far you can get video',
            arguments={'site':'current','intent':'play'})
        self.assertEqual(r.status,'failed',r)
        self.assertEqual(self.navigations(),[])
    def test_extractor_is_not_global_phrase_map(self):
        self.assertEqual(confirmed_video_title_request('play the how far you can get video'),'how far you can get')
        self.assertEqual(confirmed_video_title_request('play the video titled How Far Can You Get'),'How Far Can You Get')
        for utterance in ('keep going','play video','play the first video',
                          'play the one with the guy in a red coat',
                          'what if we played the how far you can get video',
                          "don't play the how far you can get video"):
            self.assertIsNone(confirmed_video_title_request(utterance),utterance)

if __name__ == '__main__': unittest.main()
