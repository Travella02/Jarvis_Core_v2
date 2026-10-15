"""Silent no-GUI/no-network tests for default-browser repair."""
from __future__ import annotations
import unittest
from unittest.mock import patch
from apps.desktop_managed_browser import ManagedDesktopBrowserSession
from core.tools.managed_browser import trusted_intent, open_in_system_default

class SpyBrowser:
    def __init__(self):
        self.calls = []
        self.result = True
    async def navigate(self, url):
        self.calls.append(('managed_navigate',url))
        return self.result
    async def close(self): pass
    async def media(self, operation, value=None):
        self.calls.append(('media', operation, value))
        return False
    async def select_tab(self,host): return False
    async def close_named_tab(self,host): return False
    async def close_tab(self): return False
    async def next_tab(self): return False

class RepairTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.browser=SpyBrowser()
        self.opened=[]
        def os_open(uri):
            self.opened.append(uri)
            return True
        self.session=ManagedDesktopBrowserSession(browser=self.browser, advanced=True, launch_default=os_open)

    async def perform(self, speech, intent='open',site='youtube.com',**extra):
        turn=self.session.active_turn+1
        self.session.on_turn_started(turn)
        return await self.session.handle(turn=turn, selected_tool='browser_action', source='voice',
                                         binding=f'item_{turn}', transcript=speech,
                                         arguments={'site':site,'intent':intent, **extra})

    async def test_public_sites_open_in_default_not_jarvis_browser(self):
        for text,host in [('Open YouTube','youtube.com'),('Could you open Google for me?','google.com'),
                          ('Now go to Wikipedia','wikipedia.org'),('Navigate to github.com','github.com')]:
            result=await self.perform(text,site=host)
            self.assertEqual(result.status,'completed',text)
        self.assertEqual(self.opened, ['https://youtube.com/','https://google.com/',
                                       'https://wikipedia.org/','https://github.com/'])
        self.assertEqual(self.browser.calls,[])

    async def test_search_uses_default_browser(self):
        got=await self.perform('Search YouTube for black holes',intent='search',site='youtube.com',query='black holes')
        self.assertEqual(got.status,'completed')
        self.assertEqual(self.opened,['https://www.youtube.com/results?search_query=black+holes'])

    async def test_default_handoff_survives_broken_managed_browser(self):
        async def should_never_run(url):raise RuntimeError('browser_failure')
        self.browser.navigate=should_never_run
        got=await self.perform('Please open YouTube',site='youtube.com')
        self.assertEqual(got.status,'completed')
        self.assertEqual(len(self.opened),1)

    async def test_os_rejection_returns_spoken_failure(self):
        self.session.gateway._launch_default=lambda uri:False
        got=await self.perform('Open YouTube')
        self.assertEqual(got.status,'failed')
        self.assertIn('default browser',got.text.lower())

    async def test_open_managed_only_when_explicit(self):
        got=await self.perform('Open YouTube in your managed browser',intent='open_managed')
        self.assertEqual(got.status,'completed',got.text)
        self.assertEqual(self.opened,[])
        self.assertEqual(self.browser.calls,[('managed_navigate','https://www.youtube.com/')])
        for text in ['Open YouTube','Open YouTube using the default browser',
                     'Do not open YouTube in your managed browser']:
            got=await self.perform(text,intent='open_managed')
            self.assertEqual(got.status,'failed',text)
        self.assertEqual(len(self.browser.calls),1)
        self.assertEqual((await self.perform('Open YouTube in your managed browser',intent='open')).status,'failed')
        self.assertEqual(self.opened,[])

    async def test_managed_media_does_not_claim_control_of_default(self):
        await self.perform('Open YouTube')
        result=await self.perform('Pause the video',intent='pause',site='current')
        self.assertEqual(result.status,'failed')
        self.assertIn('jarvis managed browser',result.text.lower())

    async def test_untrusted_requests_do_not_open_os_browser(self):
        cases=[('Do not open YouTube','youtube.com'),('Open YouTube tomorrow','youtube.com'),
               ('Open YouTube and send an email','youtube.com'),
               ('Open youtube.com.evil.net','youtube.com'),('Open Wikipedia','youtube.com')]
        for text,site in cases:
            self.assertEqual((await self.perform(text,site=site)).status,'failed',text)
        self.assertEqual(self.opened,[])

    async def test_same_turn_only_once(self):
        self.session.on_turn_started(1)
        arguments={'site':'youtube.com','intent':'open'}
        a=await self.session.handle(turn=1,selected_tool='browser_action',source='voice',binding='item_1',
                                    transcript='Open YouTube',arguments=arguments)
        b=await self.session.handle(turn=1,selected_tool='browser_action',source='voice',binding='item_1',
                                    transcript='Open YouTube',arguments=arguments)
        self.assertEqual(a.status,'completed')
        self.assertIsNone(b)
        self.assertEqual(len(self.opened),1)

class DefaultBrowserContract(unittest.TestCase):
    def test_windows_os_shell_is_used(self):
        with patch('core.tools.managed_browser.os.name','nt'),patch('core.tools.managed_browser.os.startfile',create=True) as start:
            self.assertTrue(open_in_system_default('https://www.youtube.com/'))
            start.assert_called_once_with('https://www.youtube.com/')

if __name__=='__main__':unittest.main()
