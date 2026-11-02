"""0.1.7.3: isolated browser worker persistence, DOM fast path and denial safety."""
import asyncio
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from core.tools.terra_navigation import TerraNavigator,confirmed_isolated_link_selection
from core.tools.background_browser import IsolatedBrowserDriver

ENV={
    'JARVIS_TERRA_NAV_ENABLED':'1',
    'JARVIS_TERRA_NAV_MODE':'isolated_browser',
    'JARVIS_TERRA_NAV_EXECUTE':'0',
    'JARVIS_TERRA_BACKGROUND_URL':'https://example.org/',
    'JARVIS_TERRA_BACKGROUND_HOSTS':'example.org',
}

class Links:
    def __init__(self, page, name):self.page=page;self.name=name;self.first=self
    def count(self):return sum(bool(self.name.search(label)) for label,href in self.page.links)
    def get_attribute(self,attribute):
        assert attribute=='href'
        return next(href for label,href in self.page.links if self.name.search(label))

class Page:
    def __init__(self, url):
        self.url=url;self.links=[('About','/about'),('Outside','https://bad.invalid'),
                                 ('Danger','/delete/account'),('Query','/about?act=1'),
                                 ('Duplicated','/a'),('Duplicated','/b')]
        self.thread=threading.get_ident();self.calls=[]
    def on(self,*a):pass
    def goto(self,url,**kw):
        assert threading.get_ident()==self.thread
        self.calls.append(('goto',url));self.url=url
    def screenshot(self,**kw):return b'\x89PNG'+b'a'*20
    def title(self):return 'Example Domain'
    def locator(self,selector):
        assert selector=='body'
        return SimpleNamespace(inner_text=lambda **kw:'Example Domain. A documentation-only example page.')
    def get_by_role(self,role,name):
        assert role=='link'
        return Links(self,name)

class Context:
    def __init__(self):self.pages=[];self.closed=False
    def new_page(self):
        p=Page('https://example.org/')
        self.pages=[p];return p
    def close(self):self.closed=True

class Browser:
    def __init__(self):self.context=Context();self.closed=False
    def new_context(self,**kw):return self.context
    def close(self):self.closed=True

class Factory:
    def __init__(self):self.launched=[]
    def launch(self,**kw):
        b=Browser();self.launched.append(b);return b

class TestPersistentBrowser(unittest.TestCase):
    def test_reuses_owning_worker_without_terra_or_physical_input(self):
        f=Factory();clock=[10.0]
        n=TerraNavigator(ENV, clock=lambda:clock[0])
        # The driver loads the in-memory fake page; no external network or API.
        original=IsolatedBrowserDriver.__enter__
        def enter(driver):
            driver.factory=f
            return original(driver)
        async def twice():
            first=await n.run_async('Inspect the isolated background browser at example.org.')
            second=await n.run_async('Inspect the isolated background browser at example.org.')
            return first,second
        try:
            with patch.object(IsolatedBrowserDriver,'__enter__',enter):
                first,second=asyncio.run(twice())
            self.assertEqual(first.code,'observed_only')
            self.assertIn('Example Domain',first.message)
            self.assertEqual(second.code,'observed_only')
            self.assertEqual(len(f.launched),1)
            self.assertEqual(n._background_uses,2)
            self.assertEqual(n._background_driver.page.thread,n._background_thread)
            self.assertGreaterEqual(first.timings['setup_ms'],0)
            self.assertEqual(first.timings['model_ms'],0.0)
            self.assertEqual(len(f.launched[0].context.pages[0].calls),1)
        finally:n.close()
        self.assertTrue(f.launched[0].closed)
        self.assertTrue(f.launched[0].context.closed)

    def test_ttl_rotates_session_and_isolated_content_is_not_shared(self):
        f=Factory();clock=[10.0];n=TerraNavigator(ENV,clock=lambda:clock[0])
        old=IsolatedBrowserDriver.__enter__
        def enter(driver):driver.factory=f;return old(driver)
        async def calls():
            await n.run_async('Inspect the background browser at example.org.')
            clock[0]=200.0
            await n.run_async('Inspect the background browser at example.org.')
        try:
            with patch.object(IsolatedBrowserDriver,'__enter__',enter):asyncio.run(calls())
            self.assertEqual(len(f.launched),2)
            self.assertTrue(f.launched[0].closed)
        finally:n.close()

    def test_mismatched_thread_fails_closed(self):
        n=TerraNavigator(ENV)
        n._background_driver=object()
        n._background_thread=-999
        with self.assertRaisesRegex(RuntimeError,'background_thread_mismatch'):
            with n._background_context():pass
        n._background_driver=None

    def test_native_inspect_can_be_disabled_and_terra_remains_available(self):
        f=Factory();fake=SimpleNamespace(responses=SimpleNamespace(create=lambda **kw:
            SimpleNamespace(output=[],output_text='Terra saw the screenshot')))
        n=TerraNavigator({**ENV,'JARVIS_TERRA_BACKGROUND_NATIVE_INSPECT':'0'},client=fake)
        old=IsolatedBrowserDriver.__enter__
        def enter(driver):driver.factory=f;return old(driver)
        try:
            with patch.object(IsolatedBrowserDriver,'__enter__',enter):
                output=asyncio.run(n.run_async('Inspect the background browser at example.org.'))
            self.assertEqual(output.code,'observed_only')
            self.assertIn('Terra saw',output.message)
            self.assertGreaterEqual(output.timings['model_ms'],0)
        finally:n.close()

    def test_native_link_selection_requires_separate_execution_opt_in(self):
        f=Factory();old=IsolatedBrowserDriver.__enter__
        def enter(driver):driver.factory=f;return old(driver)
        text='Click the "About" link in the background browser at example.org.'
        opts={**ENV,'JARVIS_TERRA_BACKGROUND_DIRECT_LINKS':'1'}
        n=TerraNavigator(opts)
        try:
            with patch.object(IsolatedBrowserDriver,'__enter__',enter):
                preview=asyncio.run(n.run_async(text))
                self.assertEqual(preview.code,'preview_only')
                self.assertFalse(f.launched[0].context.pages[0].url.endswith('about'))
                n.env['JARVIS_TERRA_NAV_EXECUTE']='1'
                success=asyncio.run(n.run_async(text))
            self.assertEqual(success.code,'background_link_navigated')
            self.assertEqual(f.launched[0].context.pages[0].url,'https://example.org/about')
            self.assertEqual(success.actions,1)
        finally:n.close()

    def test_link_navigation_fail_closed_for_unsafe_and_ambiguous_targets(self):
        f=Factory();old=IsolatedBrowserDriver.__enter__
        def enter(driver):driver.factory=f;return old(driver)
        n=TerraNavigator({**ENV,'JARVIS_TERRA_BACKGROUND_DIRECT_LINKS':'1','JARVIS_TERRA_NAV_EXECUTE':'1'})
        try:
            with patch.object(IsolatedBrowserDriver,'__enter__',enter):
                for label in ('Outside','Danger','Query','Duplicated','Unknown'):
                    result=asyncio.run(n.run_async(f'Click the "{label}" link in the background browser at example.org.'))
                    self.assertEqual(result.code,'background_link_unverified',label)
            self.assertEqual(f.launched[0].context.pages[0].url,'https://example.org/')
        finally:n.close()

    def test_denied_task_explains_foreground_restriction(self):
        n=TerraNavigator(ENV)
        result=n.run('Click the File menu in Notepad.')
        self.assertEqual(result.code,'background_target_unverified')
        self.assertIn('foreground app',result.message)
        self.assertNotIn('Please explicitly refer',result.message)

    def test_no_unquoted_or_compound_native_click(self):
        for phrase in (
            'Click the About link in background browser at example.org.',
            'Click the "About" link in the background browser at other.org.',
            'What if I clicked the "About" link in background browser?',
            'Click the "About" link in background browser and type password.',
        ):
            self.assertIsNone(confirmed_isolated_link_selection(phrase,'example.org'),phrase)

if __name__=='__main__':unittest.main()
