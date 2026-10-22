"""0.1.5.8 Repair 3: silent, offline, deterministic browser tab safety tests."""
from __future__ import annotations

import unittest
from pathlib import Path
from apps.desktop_managed_browser import ManagedDesktopBrowserSession
from core.tools.default_browser_bridge import DefaultBrowserBridgeAdapter


class SimulatedBridge:
    def __init__(self, tabs=None, connected=True):
        self.tabs = [dict(t) for t in (tabs if tabs is not None else [
            {'id':11,'url':'https://www.youtube.com/','window_id':1,'active':True},
            {'id':12,'url':'https://google.com/','window_id':1,'active':False}])]
        self.connected=connected
        self.instance='browser_A'
        self.focused=next((t['id'] for t in self.tabs if t.get('active')),0)
        self.operations=[]
        self.focus_race=False
        self.fail_navigate=False

    def status(self):return {'connected':self.connected,'instance_id':self.instance, 'capabilities':['navigate_target_guarded']}

    def state(self):
        return {'ok':True, 'tabs':[dict(t) for t in self.tabs],
                'active_tab':dict(next((t for t in self.tabs if t['id']==self.focused),{}))}

    async def execute(self, name, args=None, **kwargs):
        args=dict(args or {})
        self.operations.append((name,args))
        if name=='tabs_list':return self.state()
        if name=='navigate':
            if self.fail_navigate:raise RuntimeError('navigation_already_may_have_happened')
            # A user focuses Google after Core selected YouTube.
            if self.focus_race:self.focused=12
            target=next(t for t in self.tabs if t['id']==args['tab_id'])
            from urllib.parse import urlsplit
            norm=lambda url:(urlsplit(url).hostname or '').removeprefix('www.')
            if norm(target['url'])!=args['expected_host']:
                raise RuntimeError('navigate_target_changed')
            target['url']=args['url']
            return {'ok':True}
        if name=='tab_close':
            self.tabs=[t for t in self.tabs if t['id']!=args['tab_id']]
            return self.state()
        if name=='tab_switch':
            self.focused=args['tab_id']
            return self.state()
        return {'ok':True}


class ReuseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bridge=SimulatedBridge()
        self.os=[]
        self.adapter=DefaultBrowserBridgeAdapter(self.bridge,open_default=lambda url:self.os.append(url) or True)

    async def test_search_reuses_existing_youtube_tab_without_new_tab(self):
        self.assertTrue(await self.adapter.navigate('https://www.youtube.com/results?search_query=Sidemen'))
        self.assertEqual(self.bridge.tabs[0]['id'],11)
        self.assertEqual(len(self.bridge.tabs),2)
        self.assertEqual(self.os,[])
        self.assertTrue(self.adapter.last_navigation_verified)
        self.assertEqual(self.adapter.last_navigation_route,'reused_connected_tab')
        params=[a for operation,a in self.bridge.operations if operation=='navigate']
        self.assertEqual(params[0]['tab_id'],11)
        self.assertEqual(params[0]['expected_host'],'youtube.com')
        self.assertFalse(any(op=='tab_switch' for op,_ in self.bridge.operations))

    async def test_focus_race_never_navigates_google(self):
        self.bridge.focus_race=True
        self.assertTrue(await self.adapter.navigate('https://www.youtube.com/results?search_query=Sidemen'))
        self.assertEqual(self.bridge.tabs[1]['url'],'https://google.com/')
        self.assertEqual(self.os,[])

    async def test_existing_other_site_uses_default_browser_instead_of_hijack(self):
        self.assertTrue(await self.adapter.navigate('https://wikipedia.org/'))
        self.assertEqual(self.bridge.tabs[0]['url'],'https://www.youtube.com/')
        self.assertEqual(self.os,['https://wikipedia.org/'])
        self.assertEqual(self.adapter.last_navigation_route,'default_new_site')
        self.assertFalse(self.adapter.last_navigation_verified)

    async def test_two_youtube_tabs_without_selection_stay_untouched(self):
        self.bridge.tabs.append({'id':13,'url':'https://www.youtube.com/watch?v=1','window_id':1,'active':False})
        self.bridge.focused=12
        self.assertTrue(await self.adapter.navigate('https://www.youtube.com/results?search_query=Sidemen'))
        self.assertEqual(self.adapter.last_navigation_route,'default_ambiguous_tabs')
        self.assertEqual(len(self.bridge.tabs),3)
        self.assertEqual(len(self.os),1)

    async def test_verified_affinity_picks_previous_tab_if_duplicates_exist(self):
        self.assertTrue(await self.adapter.navigate('https://www.youtube.com/results?search_query=Sidemen'))
        self.bridge.tabs.append({'id':13,'url':'https://www.youtube.com/watch?v=2','window_id':1,'active':False})
        self.bridge.focused=12
        self.assertTrue(await self.adapter.navigate('https://www.youtube.com/results?search_query=NASA'))
        self.assertEqual(self.bridge.tabs[0]['url'],'https://www.youtube.com/results?search_query=NASA')
        self.assertEqual(self.os,[])

    async def test_user_focused_matching_tab_overrides_affinity(self):
        self.assertTrue(await self.adapter.navigate('https://www.youtube.com/results?search_query=Sidemen'))
        self.bridge.tabs.append({'id':13,'url':'https://www.youtube.com/watch?v=2','window_id':1,'active':True})
        self.bridge.focused=13
        self.assertTrue(await self.adapter.navigate('https://www.youtube.com/results?search_query=NASA'))
        self.assertEqual(self.bridge.tabs[-1]['url'],'https://www.youtube.com/results?search_query=NASA')
        self.assertIn('Sidemen',self.bridge.tabs[0]['url'])

    async def test_bridge_instance_change_invalidates_affinity(self):
        self.assertTrue(await self.adapter.navigate('https://www.youtube.com/results?search_query=Sidemen'))
        self.bridge.instance='browser_B'
        self.bridge.tabs.append({'id':13,'url':'https://www.youtube.com/watch?v=2','window_id':1,'active':False})
        self.bridge.focused=12
        self.assertTrue(await self.adapter.navigate('https://www.youtube.com/results?search_query=NASA'))
        self.assertEqual(len(self.os),1)
        self.assertEqual(self.adapter.last_navigation_route,'default_ambiguous_tabs')

    async def test_disconnected_fallback_cannot_claim_tab_reuse(self):
        self.bridge.connected=False
        self.assertTrue(await self.adapter.navigate('https://www.youtube.com/results?search_query=Sidemen'))
        self.assertEqual(self.adapter.last_navigation_route,'default_bridge_disconnected')
        self.assertFalse(self.adapter.last_navigation_verified)
        self.assertTrue(self.adapter.last_system_handoff)
        self.assertEqual(len(self.os),1)

    async def test_old_worker_cannot_receive_unguarded_tab_navigation(self):
        self.bridge.status=lambda: {'connected':True,'instance_id':'browser_A', 'capabilities':['navigate']}
        self.assertTrue(await self.adapter.navigate('https://www.youtube.com/results?search_query=Sidemen'))
        self.assertEqual(self.adapter.last_navigation_route,'default_extension_outdated')
        self.assertFalse(any(op=='navigate' for op,_ in self.bridge.operations))
        self.assertEqual(len(self.os),1)

    async def test_command_failure_cannot_trigger_duplicate_navigation(self):
        self.bridge.fail_navigate=True
        self.assertFalse(await self.adapter.navigate('https://www.youtube.com/results?search_query=Sidemen'))
        self.assertEqual(self.adapter.last_navigation_route,'bridge_command_failed')
        self.assertEqual(self.os,[])

    async def test_core_authorization_and_route_are_unchanged(self):
        s=ManagedDesktopBrowserSession(browser=self.adapter,advanced=True,bridge_mode=True)
        s.on_turn_started(1)
        denied=await s.handle(turn=1,selected_tool='browser_action',source='voice',binding='item_1',
             transcript="Don't search YouTube for Sidemen",
             arguments={'site':'youtube.com','intent':'search','query':'Sidemen'})
        self.assertEqual(denied.status,'failed')
        self.assertEqual(self.os,[])
        s.on_turn_started(2)
        good=await s.handle(turn=2,selected_tool='browser_action',source='voice',binding='item_2',
             transcript='Search YouTube for Sidemen',
             arguments={'site':'youtube.com','intent':'search','query':'Sidemen'})
        self.assertEqual(good.status,'completed')
        self.assertEqual(self.os,[])

    def test_browser_worker_requires_direct_tab_and_original_host(self):
        script=(Path(__file__).resolve().parents[2]/'extensions/jarvis_browser_bridge/service_worker.js').read_text('utf-8')
        self.assertIn('args.tab_id',script)
        self.assertIn('args.expected_host',script)
        self.assertIn('navigate_target_changed',script)
        self.assertIn('chrome.tabs.update(tabId, {url})',script)
        self.assertNotIn('await chrome.tabs.update(tab.id, {url});',script[script.index('if (operation === "navigate")'):script.index('if (operation === "search")')])


if __name__=='__main__':unittest.main()
