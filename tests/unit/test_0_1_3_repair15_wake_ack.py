"""Repair15: wake-only words produce one Realtime acknowledgment turn.

The live audio and Core authority path remain those of accepted Repair13.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import WebSocketDisconnect
from apps.desktop_alpha import DesktopWakeService
from core.voice.conversation_control import WakePhraseDetector, WakeSleepConfig
from core.voice.wake_listener import WakeListenerResult

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
HOST = (ROOT / 'apps/desktop_alpha.py').read_text(encoding='utf-8')


class Socket:
    def __init__(self):
        self.outbound = []
    async def accept(self):
        pass
    async def send_json(self, payload):
        self.outbound.append(payload)
    async def receive(self):
        if not hasattr(self, 'fed'):
            self.fed = True
            return {'bytes': b'\0' * 960}
        raise WebSocketDisconnect()
    async def close(self):
        pass


class Listener:
    def __init__(self, transcript):
        self.transcript = transcript
        self.config = SimpleNamespace(wake_phrases=('hey jarvis', 'jarvis'), idle_timeout_seconds=60)
        self.detector = WakePhraseDetector(self.config.wake_phrases)
    async def health(self):
        return SimpleNamespace(ready=True)
    async def warmup(self):
        pass
    def reset(self):
        pass
    async def feed_pcm(self, frame):
        return WakeListenerResult(self.transcript, self.detector.match(self.transcript))


class Repair15WakeAckTests(unittest.IsolatedAsyncioTestCase):
    async def make_wake(self, transcript):
        socket = Socket()
        service = DesktopWakeService(runtime=object(), listener=Listener(transcript))
        with patch('apps.desktop_alpha._emit_presence'):
            await service.listen(socket)
        wake = [x for x in socket.outbound if x.get('kind') == 'wake_detected']
        self.assertEqual(len(wake), 1)
        return wake[0]

    async def test_bare_jarvis_retains_exact_transcript(self):
        wake = await self.make_wake('Jarvis.')
        self.assertEqual(wake['command_text'], '')
        self.assertEqual(wake['wake_only_transcript'], 'Jarvis.')

    async def test_hey_jarvis_retains_exact_transcript(self):
        wake = await self.make_wake('Hey Jarvis!')
        self.assertEqual(wake['command_text'], '')
        self.assertEqual(wake['wake_only_transcript'], 'Hey Jarvis!')

    async def test_embedded_command_does_not_create_preliminary_greeting(self):
        wake = await self.make_wake('Hey Jarvis, what is nine times eight?')
        self.assertEqual(wake['command_text'], 'what is nine times eight?')
        self.assertEqual(wake['wake_only_transcript'], '')

    async def test_no_matching_wake_is_silent(self):
        socket = Socket()
        service = DesktopWakeService(runtime=object(), listener=Listener('hello computer'))
        with patch('apps.desktop_alpha._emit_presence'):
            await service.listen(socket)
        self.assertFalse(any(x.get('kind') == 'wake_detected' for x in socket.outbound))

    def test_embedded_command_unchanged_and_no_ack_first(self):
        self.assertIn("if (command) {", APP)
        self.assertIn("void startRealtimeSession(command, 'local_wake_phrase');", APP)
        self.assertIn("void startRealtimeSession(wakeOnly, wakeOnly ? 'wake_only' : 'local_wake_phrase')", APP)
        self.assertIn("const wakeOnly = String(payload.wake_only_transcript || '').trim();", APP)

    def test_wake_only_is_a_real_verified_user_turn(self):
        self.assertIn("dispatchTextToRealtime(preservedCommand, 'wake_transcript', reason === 'wake_only')", APP)
        self.assertIn('wakeOnlyTurnRef.current = wakeOnly ? turnCounterRef.current : 0', APP)
        self.assertIn('wakeOnlyTurnRef.current === latencyRef.current.turn', APP)
        self.assertIn("type: 'conversation.item.create'", APP)
        self.assertIn("kind: 'desktop_user'", APP)

    def test_ack_is_model_generated_not_pre_recorded(self):
        self.assertIn('Reply naturally in 1 to 5 spoken words', APP)
        self.assertIn('Vary your wording', APP)
        self.assertIn("metadata:{jarvis_stage:'overlap_candidate'", APP)
        self.assertIn("output_modalities:['audio']", APP)
        self.assertNotIn('sayWakeGreeting', APP)
        self.assertNotIn('playCannedWakeAudio', APP)

    def test_core_authority_and_trim_remain(self):
        self.assertIn("pcm_trim", (ROOT / 'scripts/realtime_ab.py').read_text(encoding='utf-8'))
        self.assertIn('overlapDirectVerifiedRef.current', APP)
        self.assertIn('gate_authorized', APP)
        self.assertIn('trim', (ROOT / 'apps/desktop/ui/src/pcmGateProcessor.js').read_text(encoding='utf-8'))

    def test_configuration_stays_phonetic_future_scope(self):
        self.assertEqual(WakeSleepConfig().wake_phrases, ('hey jarvis', 'jarvis'))


if __name__ == '__main__':
    unittest.main()
