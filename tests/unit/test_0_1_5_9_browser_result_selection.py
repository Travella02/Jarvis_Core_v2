"""Silent, no-network 0.1.5.9 YouTube search-result selection contracts."""
import unittest
from urllib.parse import urlsplit

from apps.desktop_managed_browser import ManagedDesktopBrowserSession
from core.tools.default_browser_bridge import DefaultBrowserBridgeAdapter
from core.tools.managed_browser import trusted_intent


class FakeBrowserBridge:
    def __init__(self):
        self.tabs = [
            {'id': 11, 'url':'https://www.youtube.com/results?search_query=rocket+league', 'active':True, 'window_id':1},
            {'id': 12, 'url':'https://www.wikipedia.org/', 'active':False, 'window_id':1},
        ]
        self.elements = [
            {'href':'https://www.youtube.com/watch?v=abcdefghijk', 'risk':'normal', 'disabled':False, 'label':'Guide One'},
            {'href':'https://www.youtube.com/watch?v=abcdefghijk&t=12', 'risk':'normal', 'disabled':False, 'label':'Duplicate Guide One'},
            {'href':'https://www.youtube.com/watch?v=ZYXWVUTSRQP&feature=share', 'risk':'normal', 'disabled':False, 'label':'Guide Two'},
            {'href':'https://evil.example/watch?v=AAAAAAAAAAA', 'risk':'normal', 'disabled':False, 'label':'Fake'},
            {'href':'https://www.youtube.com/watch?v=QWERTYUIOPA', 'risk':'external_commit', 'disabled':False, 'label':'Sensitive Link'},
        ]
        self.ops=[]; self.connected=True; self.focus_swap=False; self.snapshot_url=None
    def status(self):
        return {'connected':self.connected,'instance_id':'test_browser','capabilities':['navigate_target_guarded','snapshot']}
    def state(self):
        active=self.tabs[0]
        return {'tabs':[dict(t) for t in self.tabs],'active_tab':dict(active)}
    async def execute(self, op, args=None, **kwargs):
        args=dict(args or {});self.ops.append((op,args))
        if op=='tabs_list':return self.state()
        if op=='snapshot':
            st=self.state()
            st['page']={'supported':True,'url':self.snapshot_url or self.tabs[0]['url'], 'elements':self.elements}
            if self.focus_swap:st['active_tab']=dict(self.tabs[1])
            return st
        if op=='navigate':
            assert args['tab_id']==11
            assert (urlsplit(self.tabs[0]['url']).hostname or '').removeprefix('www.')==args['expected_host']
            self.tabs[0]['url']=args['url'];return {'ok':True}
        if op in ('media_fullscreen', 'media_control'):
            return {'verified':True}
        raise AssertionError(op)


class SelectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bridge=FakeBrowserBridge()
        self.adapter=DefaultBrowserBridgeAdapter(self.bridge,open_default=lambda url:self.fail('should not open OS browser'))
        self.session=ManagedDesktopBrowserSession(browser=self.adapter, advanced=True, bridge_mode=True)
        self.turn=0
    async def act(self,text,intent='select_result',value=1,site='current'):
        self.turn+=1;self.session.on_turn_started(self.turn)
        args={'site':site,'intent':intent}
        if intent in ('select_result','volume'):args['value']=value
        return await self.session.handle(turn=self.turn,selected_tool='browser_action',source='voice',binding='item_1',transcript=text,arguments=args)
    async def test_first_result_reuses_tab_with_verified_url(self):
        result=await self.act('Play the first video')
        self.assertEqual(result.status,'completed',result)
        self.assertEqual(self.bridge.tabs[0]['url'],'https://www.youtube.com/watch?v=abcdefghijk')
        self.assertEqual(self.bridge.tabs[1]['url'],'https://www.wikipedia.org/')
        self.assertEqual([x for x,a in self.bridge.ops if x=='navigate'],['navigate'])
        self.assertTrue(self.adapter.last_navigation_verified)
    async def test_second_result_dedupes_watch_links(self):
        result=await self.act('Open the second result',value=2)
        self.assertEqual(result.status,'completed',result)
        self.assertIn('ZYXWVUTSRQP',self.bridge.tabs[0]['url'])
    async def test_disallow_unspoken_ordinal(self):
        result=await self.act('Play the first video',value=2)
        self.assertEqual(result.status,'failed')
        self.assertFalse(any(x=='navigate' for x,a in self.bridge.ops))
    async def test_missing_result_is_not_randomly_substituted(self):
        result=await self.act('Play the third video',value=3)
        self.assertEqual(result.status,'failed')
        self.assertFalse(any(x=='navigate' for x,a in self.bridge.ops))
    async def test_focus_race_fails_closed(self):
        self.bridge.focus_swap=True
        result=await self.act('Play the first video')
        self.assertEqual(result.status,'failed')
        self.assertFalse(any(x=='navigate' for x,a in self.bridge.ops))
    async def test_snapshot_url_change_fails_closed(self):
        self.bridge.snapshot_url='https://www.youtube.com/watch?v=abcdefghijk'
        result=await self.act('Play the first video')
        self.assertEqual(result.status,'failed')
        self.assertFalse(any(x=='navigate' for x,a in self.bridge.ops))
    async def test_no_extension_no_fallback_open(self):
        self.bridge.connected=False
        result=await self.act('Play the first video')
        self.assertEqual(result.status,'failed')
        self.assertFalse(any(x=='navigate' for x,a in self.bridge.ops))
    async def test_unsupported_site_cannot_be_selected(self):
        self.bridge.tabs[0]['url']='https://www.wikipedia.org/wiki/Things'
        result=await self.act('Play the first video')
        self.assertEqual(result.status,'failed')
        self.assertFalse(any(x=='navigate' for x,a in self.bridge.ops))
    async def test_fullscreen_existing_media(self):
        result=await self.act('Make it fullscreen',intent='fullscreen')
        self.assertEqual(result.status,'completed',result)
        self.assertIn(('media_fullscreen',{'action':'enter'}),self.bridge.ops)
        result=await self.act('Exit fullscreen',intent='exit_fullscreen')
        self.assertEqual(result.status,'completed',result)
        self.assertIn(('media_fullscreen',{'action':'exit'}),self.bridge.ops)
    async def test_video_url_with_website_added_tracking_query_is_still_verified(self):
        original_execute=self.bridge.execute
        async def augmented(op,args=None,**kwargs):
            value=await original_execute(op,args,**kwargs)
            if op=='navigate':self.bridge.tabs[0]['url']+='&pp=observed'
            return value
        self.bridge.execute=augmented
        result=await self.act('Play the first video')
        self.assertEqual(result.status,'completed',result)
    async def test_hypothetical_and_negative_denied(self):
        for text in ("Don't play the first video",'What if you played the first video?','Suppose you played the first video'):
            result=await self.act(text)
            self.assertEqual(result.status,'failed',text)
        self.assertFalse(any(x=='navigate' for x,a in self.bridge.ops))
    def test_direct_validation(self):
        self.assertTrue(trusted_intent('Play the first video','select_result','current',value=1))
        self.assertTrue(trusted_intent('Open the second result','select_result','current',value=2))
        self.assertFalse(trusted_intent('Play the first video','select_result','current',value=3))
        self.assertFalse(trusted_intent('Play the first and second video','select_result','current',value=1))
        self.assertFalse(trusted_intent('Play the first video and send an email','select_result','current',value=1))

if __name__=='__main__':unittest.main()
