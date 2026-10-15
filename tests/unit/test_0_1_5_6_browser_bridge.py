"""Silent, no-browser, no-network tests for v1-derived v2 browser bridge."""
from __future__ import annotations
import unittest
from unittest.mock import patch
from apps.desktop_managed_browser import ManagedDesktopBrowserSession
from core.tools.default_browser_bridge import DefaultBrowserBridgeAdapter
from core.tools.browser_bridge import BrowserBridge

class FakeExtension:
    def __init__(self, tabs=None, connected=True):
        self.connected=connected
        self.tabs=tabs if tabs is not None else [
            {'id':3,'title':'YouTube','url':'https://www.youtube.com/','window_id':1,'active':True},
            {'id':4,'title':'Google','url':'https://google.com/','window_id':1,'active':False}]
        self.active=next((t['id'] for t in self.tabs if t['active']),self.tabs[0]['id'] if self.tabs else 0)
        self.operations=[]
        self.media_verified=True
    def status(self):return {'connected':self.connected}
    def snapshot(self):
        return {'ok':True,'tabs':[dict(t) for t in self.tabs],
                'active_tab':dict(next((t for t in self.tabs if t['id']==self.active),{}))}
    async def execute(self, name, args=None, **kw):
        if not self.connected:raise RuntimeError('disconnected')
        args=args or {};self.operations.append((name,dict(args)))
        if name=='tabs_list':return self.snapshot()
        if name=='tab_switch':
            self.active=args['tab_id'];return self.snapshot()
        if name=='navigate':
            next(t for t in self.tabs if t['id']==self.active)['url']=args['url']
            return self.snapshot()
        if name=='tab_close':
            self.tabs=[t for t in self.tabs if t['id']!=args['tab_id']]
            self.active=self.tabs[0]['id'] if self.tabs else 0
            return self.snapshot()
        if name in ('media_control','media_volume','media_mute'):
            return {'ok':True,'verified':self.media_verified}
        return {'ok':True}

class BridgeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.extension=FakeExtension()
        self.os_open=[]
        def launcher(url):self.os_open.append(url);return True
        self.adapter=DefaultBrowserBridgeAdapter(self.extension,open_default=launcher)

    async def test_search_reuses_exact_site_tab(self):
        self.assertTrue(await self.adapter.navigate('https://www.youtube.com/results?search_query=Sidemen'))
        self.assertTrue(self.adapter.last_navigation_verified)
        self.assertFalse(self.adapter.last_system_handoff)
        self.assertEqual(self.os_open,[])
        self.assertEqual(self.extension.active,3)
        self.assertEqual(self.extension.tabs[0]['url'],'https://www.youtube.com/results?search_query=Sidemen')

    async def test_unmatched_site_uses_os_default(self):
        self.assertTrue(await self.adapter.navigate('https://wikipedia.org/'))
        self.assertEqual(self.os_open,['https://wikipedia.org/'])
        self.assertFalse(self.adapter.last_navigation_verified)

    async def test_disconnect_still_opens_default(self):
        self.extension.connected=False
        self.assertTrue(await self.adapter.navigate('https://youtube.com/'))
        self.assertEqual(self.os_open,['https://youtube.com/'])

    async def test_ambiguous_duplicate_tabs_do_not_guess(self):
        self.extension.tabs[0]['active']=False
        self.extension.tabs.append({'id':5,'url':'https://youtube.com/watch?v=other','window_id':1,'active':False})
        self.extension.active=4
        self.assertTrue(await self.adapter.navigate('https://www.youtube.com/results?search_query=Sidemen'))
        self.assertEqual(self.os_open,['https://www.youtube.com/results?search_query=Sidemen'])

    async def test_named_switch_and_close_are_verified(self):
        self.assertTrue(await self.adapter.select_tab('google.com'))
        self.assertEqual(self.extension.active,4)
        self.assertTrue(await self.adapter.close_named_tab('google.com'))
        self.assertEqual([t['id'] for t in self.extension.tabs],[3])

    async def test_verified_media_not_mere_request_acceptance(self):
        self.extension.media_verified=False
        self.assertFalse(await self.adapter.media('pause'))
        self.extension.media_verified=True
        self.assertTrue(await self.adapter.media('pause'))
        self.assertTrue(await self.adapter.media('volume',40))
        self.assertFalse(await self.adapter.media('volume',101))

    async def test_reject_unsafe_urls(self):
        self.assertFalse(await self.adapter.navigate('file:///etc/passwd'))
        self.assertEqual(self.os_open,[])

    async def test_core_speech_authorization_and_one_execution(self):
        session=ManagedDesktopBrowserSession(browser=self.adapter,advanced=True,bridge_mode=True)
        session.on_turn_started(7)
        args={'site':'youtube.com','intent':'search','query':'Sidemen'}
        ok=await session.handle(turn=7,selected_tool='browser_action',source='voice',binding='item_7',
                 transcript='Search YouTube for Sidemen',arguments=args)
        self.assertEqual(ok.status,'completed',ok)
        self.assertIsNone(await session.handle(turn=7,selected_tool='browser_action',source='voice',binding='item_7',
                 transcript='Search YouTube for Sidemen',arguments=args))
        self.assertEqual(len([n for n,_ in self.extension.operations if n=='navigate']),1)

    async def test_core_denies_untrusted_and_managed_redirect(self):
        session=ManagedDesktopBrowserSession(browser=self.adapter,advanced=True,bridge_mode=True)
        session.on_turn_started(1)
        result=await session.handle(turn=1,selected_tool='browser_action',source='voice',binding='item_1',
                 transcript='Do not open YouTube',arguments={'site':'youtube.com','intent':'open'})
        self.assertEqual(result.status,'failed')
        session.on_turn_started(2)
        result=await session.handle(turn=2,selected_tool='browser_action',source='voice',binding='item_2',
                 transcript='Open YouTube in your managed browser',arguments={'site':'youtube.com','intent':'open_managed'})
        self.assertEqual(result.status,'failed')
        self.assertEqual(self.os_open,[])

    async def test_user_gets_spoken_failure_when_extension_missing(self):
        self.extension.connected=False
        session=ManagedDesktopBrowserSession(browser=self.adapter,advanced=True,bridge_mode=True)
        session.on_turn_started(1)
        result=await session.handle(turn=1,selected_tool='browser_action',source='voice',binding='item_1',
             transcript='Pause the video',arguments={'site':'current','intent':'pause'})
        self.assertEqual(result.status,'failed')
        self.assertIn('extension',result.text.lower())

class SecurityContracts(unittest.IsolatedAsyncioTestCase):
    async def test_bridge_does_not_expose_generic_script_or_typing(self):
        bridge=BrowserBridge()
        for op in ('click','type','select','scroll','tab_new','execute_script','eval','download','snapshot'):
            with self.assertRaises(ValueError):
                await bridge.execute(op,{})

if __name__=='__main__':unittest.main()
