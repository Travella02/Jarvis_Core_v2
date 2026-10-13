"""Repair16 Repair2: real Windows audio cue, bounded hold, Core-only budget."""
import asyncio
import io
import sys
import types
import unittest
import wave
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from apps import desktop_cancel_cue as cue
from apps.desktop_alpha import _desktop_core_luna_budget
from apps import desktop_luna
from apps.desktop_luna import DesktopLunaDelegator
from providers.intelligence.openai.config import OpenAIProviderConfig, DEFAULT_VOICE_MAX_OUTPUT_TOKENS
from core.intelligence import DelegationStatus

ROOT = Path(__file__).resolve().parents[2]


class BudgetAndAudioContractTests(unittest.TestCase):
    def test_luna_budget_is_1024_only_for_desktop_default(self):
        config = OpenAIProviderConfig(api_key=None)
        self.assertEqual(DEFAULT_VOICE_MAX_OUTPUT_TOKENS, 256)
        self.assertEqual(_desktop_core_luna_budget(config, {}).voice_max_output_tokens, 1024)
        self.assertEqual(config.voice_max_output_tokens, 256)

    def test_legacy_256_env_still_increases_desktop_luna(self):
        config = OpenAIProviderConfig(api_key=None, voice_max_output_tokens=256)
        self.assertEqual(_desktop_core_luna_budget(config, {'JARVIS_OPENAI_VOICE_MAX_OUTPUT_TOKENS': '256'}).voice_max_output_tokens, 1024)

    def test_explicit_higher_budget_and_dedicated_override(self):
        config = OpenAIProviderConfig(api_key=None, voice_max_output_tokens=2048)
        self.assertEqual(_desktop_core_luna_budget(config, {'JARVIS_OPENAI_VOICE_MAX_OUTPUT_TOKENS': '2048'}).voice_max_output_tokens, 2048)
        self.assertEqual(_desktop_core_luna_budget(config, {'JARVIS_DESKTOP_LUNA_VOICE_MAX_OUTPUT_TOKENS': '1024'}).voice_max_output_tokens, 1024)
        with self.assertRaises(ValueError):
            _desktop_core_luna_budget(config, {'JARVIS_DESKTOP_LUNA_VOICE_MAX_OUTPUT_TOKENS': '100000'})

    def test_generated_cue_is_real_nonempty_wav(self):
        raw = cue.hold_cue_wav()
        self.assertTrue(raw.startswith(b'RIFF'))
        with wave.open(io.BytesIO(raw), 'rb') as stream:
            self.assertEqual(stream.getnchannels(), 1)
            self.assertEqual(stream.getsampwidth(), 2)
            self.assertGreater(stream.getnframes(), 9000)
            self.assertLess(stream.getnframes(), 18000)
            self.assertTrue(any(stream.readframes(32)))

    def test_windows_native_playback_calls_default_wave_device(self):
        recorded = []
        fake = types.SimpleNamespace(SND_MEMORY=4, SND_NODEFAULT=2,
                                     PlaySound=lambda raw, flags: recorded.append((raw, flags)))
        with patch.object(cue.sys, 'platform', 'win32'), patch.dict(sys.modules, {'winsound': fake}):
            self.assertEqual(cue.play_native_hold_cue(), 'playback_api_completed')
        self.assertEqual(recorded[0][1], fake.SND_MEMORY | fake.SND_NODEFAULT)
        self.assertTrue(recorded[0][0].startswith(b'RIFF'))

    def test_native_failure_and_non_windows_are_safe(self):
        def fail(*_): raise OSError('example device name secret')
        fake = types.SimpleNamespace(SND_MEMORY=4, SND_NODEFAULT=2, PlaySound=fail)
        with patch.object(cue.sys, 'platform', 'win32'), patch.dict(sys.modules, {'winsound': fake}):
            self.assertEqual(cue.play_native_hold_cue(), 'playback_api_failed')
        with patch.object(cue.sys, 'platform', 'linux'):
            self.assertEqual(cue.play_native_hold_cue(), 'unsupported_platform')

    def test_renderer_does_not_depend_on_unlocked_web_audio_on_windows(self):
        app = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        self.assertIn("payload.cue_route !== 'native_windows'", app)
        self.assertIn("payload.kind === 'core_luna_cancel_cue_fallback'", app)
        self.assertIn('TEST MODE · INTERRUPT NOW (8 SEC)', app)
        self.assertNotIn('setTimeout(() => setCancelHoldTurn(null), 8500)', app)


class TestConversation:
    async def cancel_active_turn(self, *_): return True

class TestOrchestrator:
    async def execute(self, *_args, **_kwargs):
        return SimpleNamespace(status=DelegationStatus.COMPLETED, text='done',
                               decision=SimpleNamespace(route_name='primary'))


class LiveCueTests(unittest.IsolatedAsyncioTestCase):
    async def wait_until(self, check):
        for _ in range(300):
            if check(): return
            await asyncio.sleep(.005)
        self.fail('held-result phase never arrived')

    async def test_native_audio_completed_before_hold_countdown_and_cancel_stays_safe(self):
        sent=[]
        async def notify(payload): sent.append(payload)
        bridge = DesktopLunaDelegator(orchestrator=TestOrchestrator(),
                                      conversation=TestConversation(), notify=notify,
                                      result_hold_seconds=.09)
        log=io.StringIO()
        def fake_play(): return 'playback_api_completed'
        try:
            with patch.object(desktop_luna.sys, 'platform', 'win32'), patch.object(desktop_luna, 'play_native_hold_cue', fake_play), redirect_stdout(log):
                bridge.transcript(1, 'complex request')
                self.assertTrue(bridge.selected(1))
                await self.wait_until(lambda: 'phase=interrupt_window_open' in log.getvalue())
                self.assertEqual(sent[0]['cue_route'], 'native_windows')
                bridge.new_turn(2)
                await asyncio.sleep(.13)
            self.assertIn('state=playback_api_completed', log.getvalue())
            self.assertIn('outcome=PASS', log.getvalue())
            self.assertFalse(any(x['kind']=='core_luna_result' for x in sent))
        finally:
            await bridge.close()

    async def test_native_failure_notifies_browser_fallback(self):
        sent=[]
        async def notify(payload): sent.append(payload)
        bridge = DesktopLunaDelegator(orchestrator=TestOrchestrator(),
                                      conversation=TestConversation(), notify=notify,
                                      result_hold_seconds=.045)
        log=io.StringIO()
        try:
            with patch.object(desktop_luna.sys, 'platform', 'win32'), patch.object(desktop_luna, 'play_native_hold_cue', lambda: 'playback_api_failed'), redirect_stdout(log):
                bridge.transcript(1, 'complex request')
                self.assertTrue(bridge.selected(1))
                await self.wait_until(lambda: any(x['kind']=='core_luna_cancel_cue_fallback' for x in sent))
                await asyncio.sleep(.08)
            self.assertIn('phase=cue_playback', log.getvalue())
            self.assertIn('outcome=NOT_TESTED', log.getvalue())
        finally:
            await bridge.close()

    async def test_normal_mode_never_notifies_or_plays_test_audio(self):
        sent=[]
        async def notify(payload): sent.append(payload)
        bridge=DesktopLunaDelegator(orchestrator=TestOrchestrator(),
                                     conversation=TestConversation(), notify=notify)
        try:
            with patch.object(desktop_luna.sys,'platform','win32'), patch.object(desktop_luna,'play_native_hold_cue', side_effect=AssertionError('no cue')):
                bridge.transcript(1, 'complex request')
                self.assertTrue(bridge.selected(1))
                await self.wait_until(lambda: any(x['kind']=='core_luna_result' for x in sent))
                self.assertEqual([x['kind'] for x in sent], ['core_luna_result'])
        finally:
            await bridge.close()


if __name__=='__main__': unittest.main()
