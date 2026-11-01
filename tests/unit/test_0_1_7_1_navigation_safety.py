"""New safety, latency, and headless isolation contract tests."""
import unittest
import asyncio
from unittest.mock import patch
from dataclasses import replace
from types import SimpleNamespace
from core.tools.terra_navigation import TerraNavigator, WindowIdentity
from core.tools.foreground_safety import foreground_disruption_reason,user_activity_reason,protected_processes
from core.tools.background_browser import approved_background_url,IsolatedBrowserDriver

class Driver:
    def __init__(self):
        self.window=WindowIdentity(3,'notepad.exe','Note',(0,0,800,500))
        self.actions=[];self.idle=10.;self.fullscreen=False;self.closed=False
    def identity(self):
        if self.closed:raise RuntimeError('window gone')
        return self.window
    def screenshot(self,_):return b'\xff\xd8\xffimage'
    def perform(self,action,_):
        self.actions.append(action)
    def is_fullscreen(self,_):return self.fullscreen
    def idle_seconds(self):return self.idle
    def window_exists(self,h):return not self.closed

class Client:
    def __init__(self, outputs):self.responses=self;self.outputs=outputs;self.calls=[]
    def create(self,**kw):self.calls.append(kw);return self.outputs.pop(0)
def call(action):return SimpleNamespace(output=[{'type':'computer_call','call_id':'c1','actions':[action]}],output_text='')
def done():return SimpleNamespace(output=[],output_text='Done')
ENV={'JARVIS_TERRA_NAV_ENABLED':'1','JARVIS_TERRA_NAV_EXECUTE':'1'}

class SafetyTests(unittest.TestCase):
    def test_fullscreen_refused_before_capture_or_api(self):
        d=Driver();d.fullscreen=True;c=Client([done()])
        r=TerraNavigator(ENV,driver=d,client=c).run('Click the File menu.')
        self.assertEqual(r.code,'immersive_foreground_active');self.assertEqual(c.calls,[])
    def test_protected_process_refused_even_windowed(self):
        d=Driver();d.window=replace(d.window,process='rocketleague.exe');c=Client([])
        self.assertEqual(TerraNavigator(ENV,driver=d,client=c).run('Click menu.').code,'protected_application_active')
    def test_user_active_prevents_injection(self):
        d=Driver();d.idle=.2;c=Client([call({'type':'click','x':5,'y':5})])
        r=TerraNavigator(ENV,driver=d,client=c).run('Click the File menu.')
        self.assertEqual(r.code,'user_currently_active');self.assertEqual(d.actions,[])
    def test_executed_action_target_closed_is_not_false_error(self):
        d=Driver()
        def action(a,w):d.actions.append(a);d.closed=True
        d.perform=action
        c=Client([call({'type':'click','x':5,'y':5})])
        r=TerraNavigator(ENV,driver=d,client=c).run('Click the Exit menu.')
        self.assertEqual(r.code,'target_window_closed_unverified')
        self.assertEqual(r.actions,1);self.assertTrue(r.spoken)
    def test_foreground_change_with_open_window_is_not_success(self):
        d=Driver()
        def action(a,w):d.actions.append(a);d.window=replace(d.window,handle=9)
        d.perform=action
        r=TerraNavigator(ENV,driver=d,client=Client([call({'type':'click','x':5,'y':5})])).run('Click File menu.')
        self.assertEqual(r.code,'window_changed')
    def test_telemetry_and_jpeg_image(self):
        d=Driver();c=Client([done()]);r=TerraNavigator(ENV,driver=d,client=c).run('Inspect the current menu.')
        self.assertEqual(r.code,'observed_only')
        self.assertIn('model_ms',r.timings);self.assertIn('total_ms',r.timings)
        self.assertTrue(c.calls[0]['input'][0]['content'][1]['image_url'].startswith('data:image/jpeg;base64,'))
    def test_invalid_navigation_mode(self):
        self.assertEqual(TerraNavigator({**ENV,'JARVIS_TERRA_NAV_MODE':'gpu'},driver=Driver()).run('Click File menu.').code,'invalid_navigation_mode')
    def test_app_launch_refuses_protected_foreground(self):
        from apps.desktop_unified_actions import UnifiedDesktopActionSession
        session=UnifiedDesktopActionSession(app_launcher=lambda _name:True)
        session.on_turn_started(1)
        async def check():
            with patch('core.tools.foreground_safety.protect_existing_desktop_action',
                       return_value='immersive_foreground_active'):
                return await session.handle(turn=1,selected_tool='launch_app',source='typed',
                     binding='typed:1',transcript='Open Notepad',arguments={'app':'notepad'})
        self.assertEqual(asyncio.run(check()).code,'immersive_foreground_active')
    def test_focus_changing_browser_route_refuses_protected_foreground(self):
        from apps.desktop_managed_browser import ManagedDesktopBrowserSession
        session=ManagedDesktopBrowserSession(advanced=True,bridge_mode=True)
        session.on_turn_started(1)
        async def check():
            with patch('core.tools.foreground_safety.protect_existing_desktop_action',
                       return_value='protected_application_active'):
                return await session.handle(turn=1,selected_tool='browser_action',source='typed',
                    binding='typed:1',transcript='Search YouTube for cats',
                    arguments={'site':'youtube.com','intent':'search','query':'cats'})
        self.assertEqual(asyncio.run(check()).code,'protected_application_active')

    def test_isolated_mode_rejects_unrelated_app_task(self):
        d=Driver();env={**ENV,'JARVIS_TERRA_NAV_MODE':'isolated_browser',
            'JARVIS_TERRA_BACKGROUND_URL':'https://example.org/',
            'JARVIS_TERRA_BACKGROUND_HOSTS':'example.org'}
        r=TerraNavigator(env,driver=d,client=Client([])).run('Click the File menu in Notepad.')
        self.assertEqual(r.code,'background_target_unverified')
        self.assertEqual(d.actions,[])
    def test_isolated_mode_can_be_explicitly_selected(self):
        d=Driver();env={**ENV,'JARVIS_TERRA_NAV_MODE':'isolated_browser',
            'JARVIS_TERRA_BACKGROUND_URL':'https://example.org/',
            'JARVIS_TERRA_BACKGROUND_HOSTS':'example.org'}
        c=Client([done()])
        r=TerraNavigator(env,driver=d,client=c).run('Inspect this background browser.')
        self.assertEqual(r.code,'observed_only')

    def test_headless_url_allowlist(self):
        self.assertEqual(approved_background_url('https://example.org/a','example.org'),'https://example.org/a')
        for url in ('http://example.org','https://other.org','https://example.org@evil.org','file:///etc/passwd','https://example.org:444/a'):
            self.assertIsNone(approved_background_url(url,'example.org'),url)
    def test_process_override_doesnt_remove_default_protection(self):
        self.assertIn('rocketleague.exe',protected_processes({'JARVIS_PROTECTED_PROCESSES':'customgame.exe'}))
        self.assertIn('customgame.exe',protected_processes({'JARVIS_PROTECTED_PROCESSES':'customgame.exe'}))
    def test_background_driver_never_uses_user_cursor(self):
        class P:
            def __init__(self):self.url='https://example.org/';self.mouse=self;self.keyboard=self;self.ops=[]
            def on(self,*a):pass
            def goto(self,*a,**k):pass
            def screenshot(self,**k):return b'\xff\xd8\xffimage'
            def click(self,*a,**k):self.ops.append('click')
            def move(self,*a):self.ops.append('move')
            def wheel(self,*a):self.ops.append('wheel')
            def press(self,*a):self.ops.append('press')
            def type(self,*a,**k):self.ops.append('type')
        class Context:
            def __init__(self):self.p=P();self.pages=[]
            def new_page(self):self.pages=[self.p];return self.p
            def close(self):pass
        class Browser:
            def __init__(self):self.context=Context()
            def new_context(self,**k):return self.context
            def close(self):pass
        class Factory:
            def __init__(self):self.browser=Browser()
            def launch(self,**k):self.headless=k['headless'];return self.browser
        f=Factory()
        with IsolatedBrowserDriver('https://example.org/','example.org',factory=f) as driver:
            w=driver.identity();driver.perform({'type':'click','x':10,'y':20},w)
            driver.perform({'type':'scroll','x':30,'y':30,'scroll_y':250},w)
            self.assertEqual(f.browser.context.p.ops,['click','move','wheel'])
            self.assertTrue(f.headless)
    def test_background_driver_rejects_escape_after_click(self):
        class Fake:
            def __init__(self):self.url='https://example.org/';self.mouse=self
            def click(self,*a,**k):self.url='https://outside.net/'
        d=IsolatedBrowserDriver('https://example.org/','example.org')
        d.page=Fake();d.context=SimpleNamespace(pages=[d.page]);d.window=WindowIdentity(-1,'isolated-browser.exe','Test',(0,0,800,500))
        with self.assertRaisesRegex(RuntimeError,'background_origin_changed'):
            d.perform({'type':'click','x':3,'y':3},d.window)

if __name__=='__main__':unittest.main()
