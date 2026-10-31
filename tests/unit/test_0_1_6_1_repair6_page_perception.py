"""Repair6: live-page read-only inspection, verified approximate title selection.

Fake connected extension; no network or Windows desktop required.
"""
from pathlib import Path
import unittest

from apps.desktop_managed_browser import ManagedDesktopBrowserSession
from core.tools.default_browser_bridge import DefaultBrowserBridgeAdapter
from core.tools.managed_browser import trusted_intent
from tests.unit.test_0_1_5_9_browser_result_selection import FakeBrowserBridge

ROOT = Path(__file__).resolve().parents[2]

class PageBridge(FakeBrowserBridge):
    def __init__(self):
        super().__init__()
        self.tabs[0]['url']='https://www.youtube.com/results?search_query=Sidemen'
        self.elements=[
            {'href':'https://www.youtube.com/watch?v=abcdefghijk','label':'', 'risk':'normal','disabled':False},
            {'href':'https://www.youtube.com/watch?v=abcdefghijk','label':'SIDEMEN How Far Can You Get In 24 Hours','risk':'normal','disabled':False},
            {'href':'https://www.youtube.com/watch?v=ZYXWVUTSRQP','label':'SIDEMEN Survive On A Desert Island','risk':'normal','disabled':False},
            {'href':'https://www.youtube.com/watch?v=QWERTYUIOPA','label':'False Sensitive Match','risk':'external_commit','disabled':False},
        ]
        self.snapshot_text='SIDEMEN How Far Can You Get In 24 Hours SIDEMEN Survive On A Desert Island'
        self.scroll_y=0
        self.scroll_height=1800
        self.viewport_height=700
    async def execute(self,op,args=None,**kwargs):
        result=await super().execute(op,args,**kwargs)
        if op=='snapshot':
            result['page'].update(title='Sidemen - YouTube',text=self.snapshot_text,
                                  scroll_y=self.scroll_y,scroll_height=self.scroll_height,
                                  viewport_height=self.viewport_height)
        return result

class PerceptionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bridge=PageBridge()
        self.adapter=DefaultBrowserBridgeAdapter(self.bridge,open_default=lambda _:self.fail('no OS browser navigation'))
        self.session=ManagedDesktopBrowserSession(browser=self.adapter,advanced=True,bridge_mode=True)
        self.turn=0
    async def act(self, utterance, intent, query=None, site='current'):
        self.turn+=1
        self.session.on_turn_started(self.turn)
        args={'site':site,'intent':intent}
        if query is not None:args['query']=query
        return await self.session.handle(turn=self.turn,selected_tool='browser_action',
            source='voice',binding='item_valid',transcript=utterance,arguments=args)
    async def test_partial_title_finds_only_grounded_video(self):
        response=await self.act('Jarvis play the how far you can get video','select_match','how far you can get')
        self.assertEqual(response.status,'completed',response)
        self.assertEqual(self.bridge.tabs[0]['url'],'https://www.youtube.com/watch?v=abcdefghijk')
        self.assertEqual([op for op,args in self.bridge.ops if op=='navigate'],['navigate'])
    async def test_thumbnails_are_not_used_for_guessing(self):
        response=await self.act('Play the one with the guy in a red coat','select_match','guy in a red coat')
        self.assertEqual(response.status,'failed')
        self.assertEqual([op for op,args in self.bridge.ops if op=='navigate'],[])
    async def test_ambiguous_and_unknown_title_fail_closed(self):
        self.bridge.elements[2]['label']='SIDEMEN How Far Can You Get Abroad'
        response=await self.act('Play the how far can you get video','select_match','how far can you get')
        self.assertEqual(response.status,'failed')
        self.assertNotIn('navigate',[op for op,args in self.bridge.ops])
    async def test_model_invented_query_denied(self):
        response=await self.act('Play the red video','select_match','how far you can get')
        self.assertEqual(response.status,'failed')
        self.assertNotIn('navigate',[op for op,args in self.bridge.ops])
    async def test_hypothetical_title_request_denied(self):
        response=await self.act('What if you played the how far you can get video?','select_match','how far you can get')
        self.assertEqual(response.status,'failed')
        self.assertNotIn('navigate',[op for op,args in self.bridge.ops])
    async def test_page_inspection_is_read_only_and_spoken(self):
        response=await self.act('Jarvis what would happen if we scrolled down?','inspect_page')
        self.assertEqual(response.status,'completed',response)
        self.assertTrue(response.spoken_result)
        self.assertIn('Sidemen', response.text)
        self.assertIn('more videos', response.text)
        self.assertNotIn('navigate',[op for op,args in self.bridge.ops])
        self.assertNotIn('scroll',[op for op,args in self.bridge.ops])
    async def test_generic_page_answer_is_not_invented(self):
        self.bridge.tabs[0]['url']='https://www.wikipedia.org/wiki/Forest'
        response=await self.act('What would we see if we scrolled down?','inspect_page')
        self.assertEqual(response.status,'completed',response)
        self.assertIn('exact content below is not visible',response.text)
        self.assertNotIn('navigate',[op for op,args in self.bridge.ops])
    async def test_page_at_bottom_answer_is_grounded(self):
        self.bridge.scroll_y=1100
        response=await self.act('What if we scroll down?','inspect_page')
        self.assertEqual(response.status,'completed',response)
        self.assertIn('already at the bottom',response.text)
    async def test_page_focus_change_denies_read(self):
        self.bridge.focus_swap=True
        response=await self.act('What if we scrolled down?','inspect_page')
        self.assertEqual(response.status,'failed')
    async def test_disconnect_denies_read(self):
        self.bridge.connected=False
        response=await self.act('What would happen if we scrolled down?','inspect_page')
        self.assertEqual(response.status,'failed')
    def test_core_text_authorization(self):
        self.assertTrue(trusted_intent('Play the how far you can get video','select_match','current',query='how far you can get'))
        self.assertFalse(trusted_intent("Don't play the how far you can get video",'select_match','current',query='how far you can get'))
        self.assertTrue(trusted_intent('What would happen if we scrolled down?','inspect_page','current'))
        self.assertFalse(trusted_intent("Don't inspect the page",'inspect_page','current'))
        self.assertFalse(trusted_intent('What if we watched the second video?','inspect_page','current'))
    def test_static_spoken_handling_and_model_schema(self):
        desktop=(ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        app=(ROOT/'apps/desktop_alpha.py').read_text(encoding='utf-8')
        self.assertIn("payload.spoken_result === true",desktop)
        self.assertIn("origin:'observation'",desktop)
        self.assertIn("'select_match','inspect_page'",app)
        self.assertIn("'spoken_result':result.spoken_result",app)

if __name__=='__main__':unittest.main()
