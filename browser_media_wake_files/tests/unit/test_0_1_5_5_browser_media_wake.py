"""0.1.5.5 alpha: silent, isolated checks; no network, microphone or GUI."""
from __future__ import annotations
import asyncio
import subprocess
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from apps.desktop_managed_browser import ManagedDesktopBrowserSession
from core.voice.conversation_control import WakePhraseDetector, WakeSleepConfig
from core.tools.managed_browser import trusted_intent

ROOT=Path(__file__).resolve().parents[2]

class BrowserStub:
    def __init__(self): self.calls=[]; self.ok=True
    async def navigate(self,url): self.calls.append(('navigate',url));return self.ok
    async def select_tab(self,host): self.calls.append(('select_tab',host));return self.ok
    async def close_named_tab(self,host):self.calls.append(('close_named_tab',host));return self.ok
    async def media(self,op,value=None):self.calls.append(('media',op,value));return self.ok
    async def close(self):pass

class BrowserMediaTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.b=BrowserStub();self.s=ManagedDesktopBrowserSession(browser=self.b,advanced=True)

    async def call(self,text,op,site='current',value=None):
        turn=self.s.active_turn+1;self.s.on_turn_started(turn)
        args={'intent':op,'site':site}
        if value is not None:args['value']=value
        return await self.s.handle(turn=turn,selected_tool='browser_action',source='voice',
                                   binding='item_'+str(turn),transcript=text,arguments=args)

    async def test_named_tab_works_only_for_explicit_exact_site(self):
        self.assertEqual((await self.call('Close Google', 'close_named_tab','google.com')).status,'completed')
        self.assertEqual((await self.call('Please switch to Wikipedia', 'select_tab','wikipedia.org')).status,'completed')
        self.assertEqual(len(self.b.calls),2)
        for text,op,site in [
            ('Close Wikipedia','close_named_tab','google.com'),
            ('Do not close Google','close_named_tab','google.com'),
            ('Close Google and Wikipedia','close_named_tab','google.com'),
            ('Switch to google.com.evil.net','select_tab','google.com'),
            ('Close the tab','close_named_tab','google.com'),
        ]:
            self.assertEqual((await self.call(text,op,site)).status,'failed',text)
        self.assertEqual(len(self.b.calls),2)

    async def test_video_commands(self):
        samples=[('Play the video','play'),('Please pause the video','pause'),
                 ('Mute the video please','mute'),('Unmute the video','unmute')]
        for text,op in samples:
            got=await self.call(text,op)
            self.assertEqual(got.status,'completed',text)
        got=await self.call('Turn the volume down to 30%','volume',value=30)
        self.assertEqual(got.status,'completed')
        self.assertEqual(self.b.calls[-1],('media','volume',30))

    async def test_never_trust_unspoken_volume_or_fake_media_request(self):
        accepted=len(self.b.calls)
        for text,op,value in [
            ('Set volume to 30 percent','volume',90),('Set volume to ninety','volume',90),
            ('Lower the volume by 30%','volume',30),('Set volume from 30 to 90','volume',30),
            ('Do not play the video','play',None),('What happens when I pause videos?','pause',None),
            ('Mute Google','mute',None),
        ]:
            result=await self.call(text,op,value=value)
            self.assertEqual(result.status,'failed',text)
        self.assertEqual(len(self.b.calls),accepted)

    async def test_old_browser_mode_does_not_gain_permissions(self):
        stable=ManagedDesktopBrowserSession(browser=self.b)
        stable.on_turn_started(1)
        got=await stable.handle(turn=1,selected_tool='browser_action',source='voice',binding='item_1',
                                transcript='Close Google',arguments={'site':'google.com','intent':'close_named_tab'})
        self.assertEqual(got.status,'failed')
        self.assertEqual(self.b.calls,[])

    async def test_false_browser_result_reports_failure(self):
        self.b.ok=False
        got=await self.call('Please pause the video','pause')
        self.assertEqual(got.status,'failed')
        self.assertIn('could not find',got.text.lower())

class WakePronunciationTests(unittest.TestCase):
    def test_jervis_dervis_are_name_calls_when_enabled(self):
        detector=WakePhraseDetector(('hey jarvis','jarvis'),phonetic_enabled=True)
        for text in ('Hey Jervis', 'Hey Dervis', 'Jervis, what is 17 times 6?',
                     'Dervis, open Google please', 'Hey Jarvis, good morning'):
            got=detector.match(text)
            self.assertIsNotNone(got,text)
        self.assertEqual(detector.match('Hey Dervis, open Google please').command_text,'open Google please')
        self.assertEqual(detector.match('Hey Dervis').phrase,'hey jarvis')

    def test_not_overly_fuzzy_or_mid_sentence(self):
        detector=WakePhraseDetector(('hey jarvis','jarvis'),phonetic_enabled=True)
        for text in ('Hey nervous', 'Hey service', 'Harvest', 'Davis', 'Hey Jars',
                     'I met Jervis yesterday', 'Yesterday Dervis asked me a question',
                     'I said hey Dervis but he ignored me', 'Hey Elvis', 'Hey Davis'):
            self.assertIsNone(detector.match(text),text)

    def test_existing_mode_remains_exact_custom_phrases_remain_exact(self):
        stable=WakePhraseDetector(('hey jarvis','jarvis'))
        self.assertIsNone(stable.match('Hey Jervis'))
        custom=WakePhraseDetector(('computer',),phonetic_enabled=True)
        self.assertIsNone(custom.match('Compoter, hello'))
        self.assertEqual(custom.match('Computer, hello').command_text,'hello')
        cfg=WakeSleepConfig.from_env(env={'JARVIS_PHONETIC_WAKE':'1'})
        self.assertTrue(cfg.phonetic_wake_enabled)

class ContractTests(unittest.TestCase):
    def test_mode_isolation(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('ab_0155',ROOT/'scripts/realtime_ab.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with patch.object(sys,'argv',['realtime_ab.py','mini-overlap-luna-trim-guided-browser-media']), patch.object(subprocess,'call',return_value=0) as call:
            self.assertEqual(module.main(),0)
        flags=call.call_args.kwargs['env']
        for key in ('JARVIS_CORE_LUNA_PROBE','JARVIS_REALTIME_OVERLAP_PROBE',
                    'JARVIS_MANAGED_BROWSER_PROBE','JARVIS_BROWSER_MEDIA_PROBE',
                    'JARVIS_PHONETIC_WAKE','JARVIS_0141_DELEGATION_GUIDANCE'):
            self.assertEqual(flags[key],'1',key)
        with patch.object(sys,'argv',['realtime_ab.py','mini-overlap-luna-trim-guided-managed-browser']), patch.object(subprocess,'call',return_value=0) as old_call:
            self.assertEqual(module.main(),0)
        for key in ('JARVIS_BROWSER_MEDIA_PROBE','JARVIS_PHONETIC_WAKE'):
            self.assertEqual(old_call.call_args.kwargs['env'][key],'0',key)
        src=(ROOT/'scripts/realtime_ab.py').read_text(encoding='utf8')
        self.assertIn('mini-overlap-luna-trim-guided-browser-media',src)
        self.assertIn('JARVIS_PHONETIC_WAKE',src)
        self.assertIn('JARVIS_BROWSER_MEDIA_PROBE',src)
        src=(ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf8')
        self.assertIn('browserMediaRef.current',src)
        self.assertIn('max_output_tokens:1024,tools:[],tool_choice:\'none\'',src)

if __name__=='__main__':unittest.main()
