"""Core-authorized browser scrolling: verified current tab, no speculative effects."""
import unittest
from copy import deepcopy
from apps.desktop_managed_browser import ManagedDesktopBrowserSession
from core.tools.default_browser_bridge import DefaultBrowserBridgeAdapter
from core.tools.managed_browser import trusted_intent


class ScrollingExtension:
    def __init__(self):
        self.connected=True
        self.capabilities=['snapshot','scroll','navigate_target_guarded']
        self.active_id=7
        self.tabs=[{'id':7,'url':'https://www.youtube.com/results?search_query=Sidemen','active':True,'window_id':1},
                   {'id':8,'url':'https://www.example.org/blog','active':False,'window_id':1}]
        self.scroll_y=0; self.height=4000; self.viewport=800
        self.operations=[]
        self.ack_without_movement=False
        self.swap_before_command=False
        self.nonmatching_snapshot=False
    def status(self):return {'connected':self.connected,'instance_id':'extension-test','capabilities':self.capabilities}
    def active(self):return next(t for t in self.tabs if t['id']==self.active_id)
    async def execute(self, op, args=None, **kwargs):
        args=dict(args or {}); self.operations.append((op,args))
        if op=='snapshot':
            active=deepcopy(self.active())
            return {'ok':True,'active_tab':active,'tabs':deepcopy(self.tabs),
                    'page':{'supported':True,'url':'https://www.other.net/' if self.nonmatching_snapshot else active['url'],
                            'scroll_y':self.scroll_y,'scroll_height':self.height,
                            'viewport_height':self.viewport}}
        if op=='scroll':
            if self.swap_before_command:self.active_id=8
            active=self.active()
            if active['id']!=args['tab_id'] or active['url']!=args['expected_url']:
                raise RuntimeError('scroll_active_tab_changed')
            if not self.ack_without_movement:
                delta=max(320,round(self.viewport*0.72))
                self.scroll_y=max(0,min(self.height-self.viewport,
                      {'up':self.scroll_y-delta,'down':self.scroll_y+delta,
                       'top':0,'bottom':self.height-self.viewport}[args['direction']]))
            return {'ok':True,'summary':'Scrolled.'}
        raise AssertionError(op)

class ScrollCoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.extension=ScrollingExtension()
        self.adapter=DefaultBrowserBridgeAdapter(self.extension,open_default=lambda _:self.fail('no OS launch'))
        self.session=ManagedDesktopBrowserSession(browser=self.adapter,advanced=True,bridge_mode=True)
        self.turn=0
    async def say(self, text, direction='down', site='current', args=None):
        self.turn+=1
        self.session.on_turn_started(self.turn)
        return await self.session.handle(turn=self.turn,selected_tool='browser_action',source='voice',
            binding=f'item_{self.turn}',transcript=text,
            arguments={'site':site,'intent':'scroll','direction':direction} if args is None else args)
    async def test_scroll_down_up_top_bottom_and_continue(self):
        for text,direction,expected in [('Scroll down a bit','down',576),('Keep going down','down',1152),
            ('Go back up','up',576),('Take me to the bottom','bottom',3200),
            ('Go back to the top','top',0)]:
            with self.subTest(text=text):
                result=await self.say(text,direction)
                self.assertEqual(result.status,'completed',result)
                self.assertEqual(self.extension.scroll_y,expected)
                self.assertIn(self.adapter.last_scroll_route,('verified_scroll','already_at_edge'))
        self.assertEqual(sum(op=='scroll' for op,_ in self.extension.operations),5)
    async def test_natural_more_videos_only_on_active_search_results(self):
        outcome=await self.say('Show me more videos')
        self.assertEqual(outcome.status,'completed',outcome)
        self.assertEqual(self.extension.scroll_y,576)
        self.extension.active_id=8
        outcome=await self.say('Show me more videos')
        self.assertEqual(outcome.code,'unverified_user_intent')
        self.extension.active_id=7
        self.extension.tabs[0]['url']='https://www.youtube.com/watch?v=abcdefghijk'
        outcome=await self.say('Show me more videos')
        self.assertEqual(outcome.code,'unverified_user_intent')
        self.assertEqual(sum(op=='scroll' for op,_ in self.extension.operations),1)
    async def test_no_move_no_false_positive(self):
        self.extension.ack_without_movement=True
        result=await self.say('Scroll down')
        self.assertEqual(result.status,'failed')
        self.assertEqual(self.adapter.last_scroll_route,'movement_unverified')
    async def test_edge_is_reported(self):
        result=await self.say('Go to the top','top')
        self.assertEqual(result.status,'completed')
        self.assertIn('already at',result.text)
        self.assertEqual(sum(op=='scroll' for op,_ in self.extension.operations),0)
    async def test_wrong_active_tab_and_url_fail_closed(self):
        self.extension.swap_before_command=True
        result=await self.say('Scroll down')
        self.assertEqual(result.status,'failed')
        self.assertEqual(self.extension.scroll_y,0)
        self.assertEqual(self.adapter.last_scroll_route,'bridge_scroll_failed')
        self.extension.swap_before_command=False
        self.extension.active_id=7
        self.extension.nonmatching_snapshot=True
        result=await self.say('Scroll down')
        self.assertEqual(result.status,'failed')
        self.assertEqual(self.adapter.last_scroll_route,'unsupported_page')
    async def test_disabled_bridge_and_missing_capability(self):
        self.extension.connected=False
        result=await self.say('Scroll down')
        self.assertEqual(result.status,'failed')
        self.extension.connected=True
        self.extension.capabilities=['snapshot']
        result=await self.say('Scroll down')
        self.assertEqual(result.status,'failed')
        self.assertFalse(any(op=='scroll' for op,_ in self.extension.operations))
    async def test_hypothetical_negated_multistep_and_ambiguous_do_not_scroll(self):
        for text in ["Don't scroll down",'What if you scrolled down?',
                     'I was thinking about scrolling down','Scroll down and open Google',
                     'Scroll down then up', 'Scroll up and down',
                     'Please scroll down tomorrow','Scroll the page somewhere']:
            with self.subTest(text=text):
                result=await self.say(text)
                self.assertEqual(result.code,'unverified_user_intent',result)
        self.assertFalse(any(op=='scroll' for op,_ in self.extension.operations))
    async def test_spoofed_site_extra_arguments_and_wrong_direction(self):
        for args in [{'site':'google.com','intent':'scroll','direction':'down'},
                     {'site':'current','intent':'scroll','direction':'left'},
                     {'site':'current','intent':'scroll','direction':'down','url':'https://evil.example'},
                     {'site':'current','intent':'scroll','direction':'down','query':'x'}]:
            outcome=await self.say('scroll down',args=args)
            self.assertEqual(outcome.status,'failed')
        outcome=await self.say('scroll down',direction='up')
        self.assertEqual(outcome.status,'failed')
        self.assertFalse(any(op=='scroll' for op,_ in self.extension.operations))
    def test_speech_evidence_is_independent(self):
        self.assertTrue(trusted_intent('Scroll down a little','scroll','current',direction='down'))
        self.assertTrue(trusted_intent('Go back up','scroll','current',direction='up'))
        self.assertFalse(trusted_intent('Show me more videos','scroll','current',direction='down'))
        self.assertTrue(trusted_intent('Show me more videos','scroll','current',direction='down',active_site_verified=True))
        self.assertFalse(trusted_intent('Show me more videos','scroll','current',direction='up',active_site_verified=True))
        self.assertFalse(trusted_intent('Scroll down','scroll','current',direction='top'))

if __name__=='__main__':unittest.main()
