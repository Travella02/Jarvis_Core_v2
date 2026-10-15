"""0.1.5.4 managed-browser regression suite. Never launches a real browser/audio."""
from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from core.common.ids import CorrelationContext
from core.tools import ToolRequest, ToolResultStatus
from core.tools.gateway import ConfirmedUserAction
from core.tools.managed_browser import normalize_host, trusted_intent, ManagedBrowserGateway
from apps.desktop_managed_browser import ManagedDesktopBrowserSession

ROOT=Path(__file__).resolve().parents[2]

class FakeBrowser:
    def __init__(self):self.ops=[];self.result=True;self.closed=False
    async def navigate(self,u):self.ops.append(('navigate',u));return self.result
    async def go_back(self):self.ops.append(('back',));return self.result
    async def go_forward(self):self.ops.append(('forward',));return self.result
    async def reload(self):self.ops.append(('reload',));return self.result
    async def close_tab(self):self.ops.append(('close_tab',));return self.result
    async def next_tab(self):self.ops.append(('next_tab',));return self.result
    async def close(self):self.closed=True

class BrowserGatewayTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.browser=FakeBrowser()
        self.session=ManagedDesktopBrowserSession(browser=self.browser)

    async def call(self,phrase,site='youtube.com',intent='open',query=None,turn=None,source='voice',binding=None):
        if turn is None:
            self.session.on_turn_started(self.session.active_turn+1);turn=self.session.active_turn
        if binding is None: binding=f'item_{turn}' if source=='voice' else f'typed:{turn}'
        proposal={'site':site,'intent':intent}
        if query is not None:proposal['query']=query
        return await self.session.handle(turn=turn,selected_tool='browser_action',source=source,
                                         binding=binding,transcript=phrase,arguments=proposal)

    async def test_generic_sites_with_different_natural_utterances(self):
        samples=[('Jarvis could you please open Google for me?','google.com'),
                 ('Thank you so much. Now take me to Wikipedia.','wikipedia.org'),
                 ('Go ahead and visit GitHub please.','github.com'),
                 ('Please open example.com','example.com'),
                 ('Navigate to https://www.nasa.gov','nasa.gov'),
                 ('I would appreciate it if you could open YouTube','youtube.com')]
        for text,host in samples:
            got=await self.call(text,site=host)
            self.assertEqual(got.status,'completed',text)
        self.assertEqual(self.browser.ops,[('navigate',f'https://www.{host}/') for _,host in samples])

    async def test_navigation_and_tab_actions_are_bound_to_current_turn(self):
        for phrase,intent in [('Go back to the previous page','back'),
                              ('Go forward now','forward'),('Refresh this page','reload'),
                              ('Close the current tab','close_tab'),('Switch to the next tab','next_tab')]:
            got=await self.call(phrase,site='current',intent=intent)
            self.assertEqual(got.status,'completed',phrase)
        self.assertEqual([op[0] for op in self.browser.ops],
                         ['back','forward','reload','close_tab','next_tab'])

    async def test_search_engine_query_and_encoded_query(self):
        got=await self.call('Please search YouTube for black holes',intent='search',site='youtube.com',query='black holes & stars')
        self.assertEqual(got.status,'completed')
        self.assertEqual(self.browser.ops[0][1],'https://www.youtube.com/results?search_query=black+holes+%26+stars')
        got=await self.call('Can you search the web for astrophysics?',intent='search',site='google.com',query='astrophysics')
        self.assertEqual(got.status,'completed')
        self.assertEqual(self.browser.ops[1][1],'https://www.google.com/search?q=astrophysics')

    async def test_negations_conditionals_and_compounds_fail_closed(self):
        samples=['Do not open YouTube', 'If you have time please open YouTube',
                 'Pretend to open YouTube','Explain how to open YouTube',
                 'Open YouTube and send an email', 'Open Google and YouTube',
                 'Someone said open YouTube', 'Open YouTube tomorrow']
        for text in samples:
            self.assertEqual((await self.call(text)).status,'failed',text)
        self.assertFalse(self.browser.ops)

    async def test_domain_binding_spoofing_and_unsafe_hostnames(self):
        for site in ('youtube.evil.com','youtube.com.evil.net','127.0.0.1','localhost',
                     'google.local','wikipedia.org:8443','file:///etc/passwd',
                     'google.com/path','evil.com?x=1','xn--googl-fsa.com'):
            self.assertEqual((await self.call('Can you open Google?',site=site)).status,'failed',site)
        # Even a valid but different site must be independently mentioned.
        self.assertEqual((await self.call('Open Wikipedia',site='google.com')).status,'failed')
        self.assertFalse(self.browser.ops)

    async def test_repeated_and_late_calls_never_reexecute(self):
        self.session.on_turn_started(1)
        a=await self.call('Open Google',site='google.com',turn=1)
        b=await self.call('Open Google',site='google.com',turn=1)
        self.assertEqual(a.status,'completed');self.assertIsNone(b)
        self.session.on_turn_started(2)
        self.assertIsNone(await self.call('Open Google',site='google.com',turn=1))
        self.assertEqual(len(self.browser.ops),1)

    async def test_missing_binding_and_unavailable_action_speaks_failure(self):
        got=await self.call('Open Google',site='google.com',binding='')
        self.assertEqual(got.code,'missing_independent_user_evidence')
        self.browser.result=False
        got=await self.call('Close this tab',site='current',intent='close_tab')
        self.assertEqual(got.status,'failed');self.assertNotEqual(got.text,'')

    async def test_gateway_rejects_unconfirmed_model_proposals(self):
        gw=ManagedBrowserGateway(self.browser)
        trace=CorrelationContext.create()
        req=ToolRequest(trace,'desktop_browser','open',{'site':'google.com'})
        self.assertEqual((await gw.execute(req,evidence=None)).status,ToolResultStatus.DENIED)
        self.assertEqual((await gw.execute(req,evidence=ConfirmedUserAction('not-this-turn','Open Google',True,True))).status,ToolResultStatus.DENIED)
        self.assertFalse(self.browser.ops)
        await gw.close();self.assertTrue(self.browser.closed)

class ContractTests(unittest.TestCase):
    def test_mode_is_separate_from_accepted_semantic_mode(self):
        s=(ROOT/'scripts/realtime_ab.py').read_text(encoding='utf-8')
        self.assertIn('mini-overlap-luna-trim-guided-managed-browser',s)
        self.assertIn('JARVIS_MANAGED_BROWSER_PROBE',s)
        app=(ROOT/'apps/desktop_alpha.py').read_text(encoding='utf-8')
        self.assertIn('ManagedDesktopBrowserSession',app)
        self.assertIn('managed_browser_probe',app)
        self.assertIn('await self._managed_browser_engine.close()',app)
    def test_no_added_routing_round_trip_or_altered_vad(self):
        s=(ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        self.assertIn('managedBrowserRef.current',s)
        self.assertIn('max_output_tokens:1024,tools:[],tool_choice:\'none\'',s)
        self.assertIn('settlePendingOverlapDirect()',s)
    def test_optional_playwright_lazily_imported(self):
        s=(ROOT/'core/tools/managed_browser.py').read_text(encoding='utf-8')
        self.assertIn('from playwright.async_api import async_playwright',s)
        self.assertNotIn('eval(',s)

if __name__=='__main__':unittest.main()
