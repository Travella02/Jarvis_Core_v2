"""0.1.7.2: safe read-only recovery for misrouted isolated browser inspection."""
import asyncio
import unittest
from types import SimpleNamespace
from core.tools.terra_navigation import (
    confirmed_isolated_browser_inspection, TerraNavigator, WindowIdentity,
)
from apps.desktop_managed_browser import ManagedDesktopBrowserSession

ENV = {
    'JARVIS_TERRA_NAV_ENABLED': '1',
    'JARVIS_TERRA_NAV_MODE': 'isolated_browser',
    'JARVIS_TERRA_NAV_EXECUTE': '1',
    'JARVIS_TERRA_NAV_ALLOW_TYPING': '1',
    'JARVIS_TERRA_BACKGROUND_URL': 'https://example.org/',
    'JARVIS_TERRA_BACKGROUND_HOSTS': 'example.org',
}

class RecordingNavigator:
    def __init__(self, env=None):
        self.env=dict(ENV if env is None else env)
        self.calls=[]
    def run(self,text,*,cancelled,read_only=False):
        self.calls.append((text,read_only))
        return SimpleNamespace(status='completed',code='observed_only',
                               message='This is the isolated example.org page.',actions=0,spoken=True)

class SimulatedDriver:
    def __init__(self):
        self.actions=[]
        self.window=WindowIdentity(-1,'isolated-browser.exe','example.org',(0,0,800,600))
    def identity(self):return self.window
    def screenshot(self,_):return b'\xff\xd8\xffimage'
    def perform(self,a,w):self.actions.append(a)

class SimulatedClient:
    def __init__(self,call):self.responses=self;self.call=call
    def create(self,**kwargs):return SimpleNamespace(output=[{'type':'computer_call','call_id':'s1','actions':[self.call]}],output_text='')

class TestIsolatedReadOnlyRecovery(unittest.TestCase):
    def test_exact_failed_typed_request_recovers_without_any_model_arguments(self):
        nav=RecordingNavigator()
        session=ManagedDesktopBrowserSession(advanced=True,bridge_mode=True,terra_navigator=nav)
        session.on_turn_started(4)
        text='Inspect the isolated background browser at example.org.'
        async def run():
            return await session.handle(turn=4,selected_tool='browser_action',source='typed',
                binding='typed:4',transcript=text,arguments={'site':'evil.net','intent':'open'})
        result=asyncio.run(run())
        self.assertEqual(result.code,'observed_only')
        self.assertTrue(result.spoken_result)
        self.assertEqual(nav.calls,[(text,True)])
        self.assertIsNone(result.action_context)

    def test_unbound_or_wrong_model_tool_cannot_recover(self):
        for source,binding,tool in [('typed','typed:88','browser_action'),
                                     ('voice','wrong','browser_action'),
                                     ('typed','typed:3','launch_app')]:
            with self.subTest(source=source,tool=tool):
                nav=RecordingNavigator()
                session=ManagedDesktopBrowserSession(advanced=True,bridge_mode=True,terra_navigator=nav)
                session.on_turn_started(4)
                async def run():
                    return await session.handle(turn=4,selected_tool=tool,source=source,
                        binding=binding,transcript='Inspect the isolated background browser at example.org.',
                        arguments={'site':'example.org','intent':'open'})
                asyncio.run(run())
                self.assertEqual(nav.calls,[])

    def test_recovery_never_opens_other_scope_or_mutates(self):
        denied=[
            'What if we inspected the background browser?',
            "Don't inspect the background browser.",
            'Inspect the background browser at evil.org.',
            'Inspect the background browser and click the Settings button.',
            'Inspect the background browser; open the admin page.',
            'Search YouTube for cats.',
            'Open example.org in my browser.',
            'Inspect the active Notepad application.',
        ]
        for text in denied:
            with self.subTest(text=text):
                self.assertFalse(confirmed_isolated_browser_inspection(text,'example.org'))
                nav=RecordingNavigator();session=ManagedDesktopBrowserSession(advanced=True,bridge_mode=True,terra_navigator=nav)
                session.on_turn_started(1)
                async def run():
                    return await session.handle(turn=1,selected_tool='browser_action',source='typed',
                        binding='typed:1',transcript=text,arguments={'site':'current','intent':'inspect_page'})
                asyncio.run(run());self.assertFalse(nav.calls)

    def test_requires_isolated_mode(self):
        nav=RecordingNavigator({**ENV,'JARVIS_TERRA_NAV_MODE':'foreground'})
        session=ManagedDesktopBrowserSession(advanced=True,bridge_mode=True,terra_navigator=nav)
        session.on_turn_started(1)
        async def run():return await session.handle(turn=1,selected_tool='browser_action',source='typed',
            binding='typed:1',transcript='Inspect the background browser at example.org.',
            arguments={'site':'example.org','intent':'open'})
        asyncio.run(run());self.assertEqual(nav.calls,[])

    def test_explicit_read_only_overrides_execute_and_typing_opt_in(self):
        driver=SimulatedDriver()
        client=SimulatedClient({'type':'click','x':20,'y':20})
        result=TerraNavigator(ENV,driver=driver,client=client).run(
            'Inspect the background browser at example.org.',read_only=True)
        self.assertEqual(result.code,'preview_only')
        self.assertEqual(driver.actions,[])

    def test_prompt_selects_isolated_navigation_not_user_browser(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[2]
        backend=(root/'apps/desktop_alpha.py').read_text(encoding='utf-8')
        frontend=(root/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        self.assertIn('ISOLATED BACKGROUND BROWSER is ALWAYS navigate_app',backend)
        self.assertIn('MUST use navigate_app, never browser_action',frontend)

if __name__=='__main__':unittest.main()
