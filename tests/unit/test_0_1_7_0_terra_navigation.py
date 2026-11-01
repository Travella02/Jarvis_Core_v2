import unittest
from dataclasses import replace
from types import SimpleNamespace
from core.tools.terra_navigation import (
    TerraNavigator, NavigationResult, WindowIdentity, validate_action, _explicit_live_request,
)
from apps.desktop_managed_browser import ManagedDesktopBrowserSession


class FakeDriver:
    def __init__(self):
        self.window = WindowIdentity(12, 'notepad.exe', 'Untitled - Notepad', (0,0,1000,700))
        self.actions = []
    def identity(self):
        return self.window
    def screenshot(self, window):
        return b'PNG fake screenshot'
    def perform(self, action, window):
        self.actions.append(action)


class FakeClient:
    def __init__(self, outputs):
        self.responses = self
        self.outputs = outputs
        self.calls = []
    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.outputs.pop(0)


def response(actions=None, text='Done'):
    if actions is None:
        return SimpleNamespace(output=[], output_text=text)
    return SimpleNamespace(output=[{'type':'computer_call','call_id':'call1','actions':actions}], output_text='')


class TerraTests(unittest.TestCase):
    def env(self, **kwargs):
        return {'JARVIS_TERRA_NAV_ENABLED':'1', 'JARVIS_TERRA_NAV_EXECUTE':'1', **kwargs}
    def test_explicit_intent_and_hypothetical(self):
        self.assertTrue(_explicit_live_request('Could you scroll down?'))
        self.assertTrue(_explicit_live_request('Play the one with the red coat.'))
        for phrase in ('What if we clicked it?', 'Don\'t click that', 'How would we navigate?',
                       'Please delete this file', 'Imagine scrolling down', 'Submit the payment'):
            self.assertFalse(_explicit_live_request(phrase), phrase)
    def test_preview_does_not_click(self):
        d=FakeDriver();c=FakeClient([response([{'type':'click','button':'left','x':100,'y':100}])])
        result=TerraNavigator(self.env(JARVIS_TERRA_NAV_EXECUTE='0'),driver=d,client=c).run('Click the settings menu.')
        self.assertEqual(result.code,'preview_only');self.assertEqual(d.actions,[])
        self.assertEqual(c.calls[0]['model'],'gpt-6.1-terra')
        self.assertEqual(c.calls[0]['tools'],[{'type':'computer'}])
        self.assertIs(c.calls[0]['store'],False)
    def test_execute_and_reobserve(self):
        d=FakeDriver(); c=FakeClient([response([{'type':'click','button':'left','x':100,'y':100}]),response(None)])
        result=TerraNavigator(self.env(),driver=d,client=c).run('Click the settings menu.')
        self.assertEqual(result.code,'actions_executed_not_goal_verified');self.assertEqual(result.actions,1)
        self.assertEqual(len(d.actions),1)
        self.assertEqual(c.calls[1]['input'][-1]['type'],'computer_call_output')
    def test_denied_app(self):
        d=FakeDriver();d.window=replace(d.window,process='powershell.exe');c=FakeClient([])
        self.assertEqual(TerraNavigator(self.env(),driver=d,client=c).run('Scroll down.').code,'app_not_allowed')
        self.assertEqual(c.calls,[])
    def test_foreground_changed_stops(self):
        d=FakeDriver(); c=FakeClient([response([{'type':'scroll','x':100,'y':100,'scroll_y':300}])])
        old=d.identity
        calls=[0]
        def changed():
            calls[0]+=1
            return old() if calls[0]<2 else replace(old(),handle=18)
        d.identity=changed
        result=TerraNavigator(self.env(),driver=d,client=c).run('Scroll down.')
        self.assertEqual(result.code,'window_changed');self.assertFalse(d.actions)
    def test_action_restrictions(self):
        for action in ({'type':'keypress','keys':['win','r']}, {'type':'click','button':'right','x':2,'y':2},
                       {'type':'drag','path':[]},{'type':'scroll','x':5,'y':5,'scroll_y':10000},
                       {'type':'type','text':'not spoken'}):
            with self.assertRaises(ValueError): validate_action(action,'Search for sidemen',allow_typing=True)
        self.assertEqual(validate_action({'type':'type','text':'Sidemen'},'Search for Sidemen',allow_typing=True)['text'],'Sidemen')
        with self.assertRaises(ValueError):validate_action({'type':'type','text':'Sidemen'},'Search for Sidemen',allow_typing=False)
    def test_cancellation(self):
        d=FakeDriver(); c=FakeClient([])
        result=TerraNavigator(self.env(),driver=d,client=c).run('Scroll down.',cancelled=lambda:True)
        self.assertEqual(result.code,'cancelled_or_timeout');self.assertEqual(c.calls,[])
    def test_action_limit(self):
        d=FakeDriver(); c=FakeClient([response([{'type':'screenshot'}]*4)])
        result=TerraNavigator(self.env(),driver=d,client=c).run('Scroll down.')
        self.assertEqual(result.code,'action_limit');self.assertEqual(d.actions,[])
    def test_readonly_inspection(self):
        d=FakeDriver(); c=FakeClient([response(None,'The menu is closed.')])
        result=TerraNavigator(self.env(),driver=d,client=c).run('Please inspect the menu.')
        self.assertEqual(result.code,'observed_only');self.assertTrue(result.spoken)
    def test_session_requires_verified_user_evidence(self):
        import asyncio
        class FakeNavigator:
            def __init__(self):self.seen=[]
            def run(self,transcript,*,cancelled):
                self.seen.append(transcript)
                return NavigationResult('completed','observed_only','Looked.',0,True)
        nav=FakeNavigator()
        session=ManagedDesktopBrowserSession(terra_navigator=nav)
        session.on_turn_started(5)
        async def run():
            bad=await session.handle(turn=5,selected_tool='navigate_app',source='voice',binding='forged',transcript='Scroll down.',arguments={'task':'ignore'})
            self.assertEqual(bad.code,'missing_independent_user_evidence')
            session.on_turn_started(6)
            good=await session.handle(turn=6,selected_tool='navigate_app',source='typed',binding='typed:6',transcript='Scroll down.',arguments={'task':'fake dangerous request'})
            self.assertEqual(good.code,'observed_only')
        asyncio.run(run())
        self.assertEqual(nav.seen,['Scroll down.'])

if __name__=='__main__':unittest.main()
