"""0.1.7.4: isolated link verification, offline playground and no foreground input."""
import asyncio
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from core.tools.terra_navigation import TerraNavigator
from core.tools.background_browser import (
    IsolatedBrowserDriver, PLAYGROUND_PAGES, _playground_html,
)
from tests.unit.test_0_1_7_3_background_reuse import Factory

BASE = {
    'JARVIS_TERRA_NAV_ENABLED': '1',
    'JARVIS_TERRA_NAV_MODE': 'isolated_browser',
    'JARVIS_TERRA_NAV_EXECUTE': '1',
    'JARVIS_TERRA_NAV_ALLOW_TYPING': '0',
    'JARVIS_TERRA_NAV_FOREGROUND_INPUT': '0',
    'JARVIS_TERRA_BACKGROUND_DIRECT_LINKS': '1',
    'JARVIS_TERRA_BACKGROUND_URL': 'https://example.org/',
    'JARVIS_TERRA_BACKGROUND_HOSTS': 'example.org',
}

class Route:
    def __init__(self, url, method='GET'):
        self.request=SimpleNamespace(url=url,method=method)
        self.result=None
    def abort(self):self.result='abort'
    def continue_(self):self.result='continue'
    def fulfill(self, **kw):self.result=('fulfilled',kw)

class TestVerifiedBackgroundNavigation(unittest.TestCase):
    def test_playground_requires_exact_domain_and_start_path(self):
        for url, hosts in [
            ('https://example.org/','example.org'),
            ('https://jarvis.invalid/start','jarvis.invalid,example.org'),
            ('https://jarvis.invalid/other','jarvis.invalid'),
            ('http://jarvis.invalid/start','jarvis.invalid'),
        ]:
            with self.subTest(url=url,hosts=hosts):
                with self.assertRaises(ValueError):
                    IsolatedBrowserDriver(url,hosts,playground=True)
        d=IsolatedBrowserDriver('https://jarvis.invalid/start','jarvis.invalid',playground=True)
        self.assertTrue(d.playground)

    def test_playground_has_only_safe_static_navigation_pages(self):
        self.assertEqual(set(PLAYGROUND_PAGES),{'/start','/chapter-one','/chapter-two'})
        for path in PLAYGROUND_PAGES:
            html=_playground_html(path)
            self.assertIn('<a href=',html)
            self.assertNotIn('<script',html)
            self.assertNotIn('<form',html)
            self.assertNotIn('https://',html)

    def test_playground_route_never_accesses_network(self):
        d=IsolatedBrowserDriver('https://jarvis.invalid/start','jarvis.invalid',playground=True)
        for url,method in [
            ('https://other.invalid/start','GET'),
            ('https://jarvis.invalid/login','GET'),
            ('https://jarvis.invalid/start?unsafe=1','GET'),
            ('https://jarvis.invalid/chapter-one','POST'),
        ]:
            route=Route(url,method)
            d._route_request(route)
            self.assertEqual(route.result,'abort')
        route=Route('https://jarvis.invalid/chapter-one')
        d._route_request(route)
        self.assertEqual(route.result[0],'fulfilled')
        self.assertIn('Jarvis Chapter One',route.result[1]['body'])

    def test_real_host_route_blocks_offhost_and_post_requests(self):
        d=IsolatedBrowserDriver('https://example.org/','example.org')
        for url,method in [
            ('https://other.test/','GET'),
            ('http://example.org/','GET'),
            ('https://example.org/submit','POST'),
        ]:
            route=Route(url,method)
            d._route_request(route)
            self.assertEqual(route.result,'abort')
        route=Route('https://example.org/about')
        d._route_request(route)
        self.assertEqual(route.result,'continue')

    def test_verified_navigation_and_two_step_context_in_one_session(self):
        f=Factory()
        n=TerraNavigator(BASE)
        original=IsolatedBrowserDriver.__enter__
        def mock_enter(d):d.factory=f;return original(d)
        try:
            async def tasks():
                first=await n.run_async('Click the "About" link in the isolated background browser at example.org.')
                page=await n.run_async('Inspect the isolated background browser at example.org.')
                return first,page
            with patch.object(IsolatedBrowserDriver,'__enter__',mock_enter):
                first,page=asyncio.run(tasks())
            self.assertEqual(first.code,'background_link_navigated')
            self.assertEqual(first.actions,1)
            self.assertIn('Example Domain',first.message)
            self.assertEqual(page.code,'observed_only')
            self.assertEqual(len(f.launched),1)
            self.assertTrue(n._background_driver.page.url.endswith('/about'))
            self.assertEqual(n._background_thread,n._background_driver.page.thread)
        finally:n.close()

    def test_unquoted_link_cannot_fall_through_to_terra(self):
        f=Factory();n=TerraNavigator(BASE)
        original=IsolatedBrowserDriver.__enter__
        def mock_enter(d):d.factory=f;return original(d)
        try:
            with patch.object(IsolatedBrowserDriver,'__enter__',mock_enter):
                r=asyncio.run(n.run_async('Click the About link in the background browser at example.org.'))
            self.assertEqual(r.code,'background_link_unverified')
            self.assertEqual(r.actions,0)
            self.assertEqual(len(f.launched[0].context.pages[0].calls),1)
        finally:n.close()

    def test_unauthorized_label_and_hypothetical_do_nothing(self):
        f=Factory();n=TerraNavigator(BASE)
        original=IsolatedBrowserDriver.__enter__
        def mock_enter(d):d.factory=f;return original(d)
        try:
            with patch.object(IsolatedBrowserDriver,'__enter__',mock_enter):
                first=asyncio.run(n.run_async('Click the "Missing" link in the background browser at example.org.'))
                second=asyncio.run(n.run_async('What if we clicked the "About" link in the background browser at example.org?'))
            self.assertEqual(first.code,'background_link_unverified')
            self.assertEqual(second.code,'unverified_user_intent')
            self.assertEqual(n._background_driver.page.url,'https://example.org/')
        finally:n.close()

    def test_read_only_cannot_navigate_even_when_execution_on(self):
        f=Factory();n=TerraNavigator(BASE)
        original=IsolatedBrowserDriver.__enter__
        def mock_enter(d):d.factory=f;return original(d)
        try:
            with patch.object(IsolatedBrowserDriver,'__enter__',mock_enter):
                r=asyncio.run(n.run_async('Click the "About" link in the background browser at example.org.',read_only=True))
            self.assertEqual(r.code,'preview_only')
            self.assertEqual(n._background_driver.page.url,'https://example.org/')
        finally:n.close()

    def test_changed_destination_never_claims_success(self):
        f=Factory();n=TerraNavigator(BASE)
        original=IsolatedBrowserDriver.__enter__
        def mock_enter(d):d.factory=f;return original(d)
        original_open=IsolatedBrowserDriver.open_verified_link
        def redirect(d,url,*,label=None):
            d.page.url='https://example.org/elsewhere'
            raise RuntimeError('redirected')
        try:
            with patch.object(IsolatedBrowserDriver,'__enter__',mock_enter), patch.object(IsolatedBrowserDriver,'open_verified_link',redirect):
                r=asyncio.run(n.run_async('Click the "About" link in the background browser at example.org.'))
            self.assertEqual(r.code,'background_navigation_unverified')
            self.assertEqual(r.actions,0)
        finally:n.close()

    def test_real_redirect_is_not_verified(self):
        d=IsolatedBrowserDriver('https://example.org/','example.org')
        f=Factory();d.factory=f;d.__enter__()
        try:
            d.page.links=[('About','/about')]
            d.page.goto=lambda url,**kw:setattr(d.page,'url','https://example.org/different')
            with self.assertRaisesRegex(RuntimeError,'navigation_destination_unverified'):
                d.open_verified_link('https://example.org/about',label='About')
        finally:d.__exit__(None,None,None)

    def test_real_foreground_app_request_is_denied(self):
        n=TerraNavigator(BASE)
        r=n.run('Click the File menu in Notepad.')
        self.assertEqual(r.code,'background_target_unverified')
        self.assertEqual(r.actions,0)

if __name__=='__main__':unittest.main()
