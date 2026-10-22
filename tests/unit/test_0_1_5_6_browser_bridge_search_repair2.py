"""Silent tests for conservative phonetic STT recovery in browser search approval."""
from __future__ import annotations
import unittest
from apps.desktop_managed_browser import ManagedDesktopBrowserSession
from core.tools.default_browser_bridge import DefaultBrowserBridgeAdapter
from core.tools.managed_browser import trusted_intent


class FakeConnectedExtension:
    def __init__(self):
        self.tabs=[{'id':7,'title':'YouTube','url':'https://www.youtube.com/',
                    'window_id':2,'active':True}]
        self.operations=[]
    def status(self):return {'connected':True,'capabilities':['navigate_target_guarded']}
    async def execute(self, name, args=None, **kwargs):
        args=args or {};self.operations.append((name,dict(args)))
        if name=='tabs_list':
            return {'ok':True,'active_tab':dict(self.tabs[0]),'tabs':[dict(x) for x in self.tabs]}
        if name=='tab_switch':
            return {'ok':True,'active_tab':dict(self.tabs[0])}
        if name=='navigate':
            self.tabs[0]['url']=args['url']
            return {'ok':True}
        return {'ok':False}


class SearchRepairTests(unittest.IsolatedAsyncioTestCase):
    async def test_transcription_sirch_is_independently_authorized_and_reuses_tab(self):
        extension=FakeConnectedExtension()
        handoff=[]
        adapter=DefaultBrowserBridgeAdapter(extension,open_default=lambda url:handoff.append(url) or True)
        session=ManagedDesktopBrowserSession(browser=adapter,advanced=True,bridge_mode=True)
        session.on_turn_started(1)
        result=await session.handle(turn=1,selected_tool='browser_action',source='voice',
            binding='item_01',transcript='Sirch YouTube for Sidemen.',
            arguments={'intent':'search','site':'youtube.com','query':'Sidemen'})
        self.assertEqual(result.status,'completed',result)
        self.assertEqual(handoff,[])
        self.assertEqual(extension.tabs[0]['url'],
            'https://www.youtube.com/results?search_query=Sidemen')
        self.assertEqual(sum(1 for x,_ in extension.operations if x=='navigate'),1)
        # Same turn cannot silently execute a second time.
        self.assertIsNone(await session.handle(turn=1,selected_tool='browser_action',source='voice',
            binding='item_01',transcript='Sirch YouTube for Sidemen.',
            arguments={'intent':'search','site':'youtube.com','query':'Sidemen'}))

    async def test_fail_closed_on_unmentioned_query_even_when_verb_is_phonetic(self):
        ext=FakeConnectedExtension()
        adapter=DefaultBrowserBridgeAdapter(ext,open_default=lambda url:True)
        session=ManagedDesktopBrowserSession(browser=adapter,advanced=True,bridge_mode=True)
        session.on_turn_started(4)
        result=await session.handle(turn=4,selected_tool='browser_action',source='voice',
            binding='item_04',transcript='Sirch YouTube for Sidemen.',
            arguments={'intent':'search','site':'youtube.com','query':'Finance'})
        self.assertEqual(result.code,'unverified_user_intent')
        self.assertFalse(any(op=='navigate' for op,_ in ext.operations))

    def test_not_a_general_action_bypass(self):
        self.assertFalse(trusted_intent('Sirch YouTube for Sidemen','open','youtube.com'))
        self.assertFalse(trusted_intent('Sirch Google for Sidemen','search','youtube.com',query='Sidemen'))
        self.assertFalse(trusted_intent('Sirch YouTube','search','youtube.com',query='Sidemen'))
        self.assertFalse(trusted_intent('Sirch YouTube for Sidemen tomorrow','search','youtube.com',query='Sidemen'))
        self.assertFalse(trusted_intent("Don't sirch YouTube for Sidemen",'search','youtube.com',query='Sidemen'))
        self.assertFalse(trusted_intent('Sirch YouTube for Sidemen and send an email','search','youtube.com',query='Sidemen'))
        self.assertFalse(trusted_intent('Explain how to sirch YouTube for Sidemen','search','youtube.com',query='Sidemen'))
        self.assertFalse(trusted_intent('Church YouTube for Sidemen','search','youtube.com',query='Sidemen'))
        self.assertFalse(trusted_intent('Sirch YouTube for Sidemen','search','google.com',query='Sidemen'))
        # Ordinary requests work exactly as before.
        self.assertTrue(trusted_intent('Search YouTube for Sidemen','search','youtube.com',query='Sidemen'))
        self.assertTrue(trusted_intent('Open YouTube','open','youtube.com'))

if __name__ == '__main__':unittest.main()
