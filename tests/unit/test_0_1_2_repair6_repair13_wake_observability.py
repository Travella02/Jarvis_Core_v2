from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import WebSocketDisconnect
from apps.desktop_alpha import DesktopWakeService
from core.voice.wake_listener import WakeListenerResult

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
HOST = (ROOT / 'apps/desktop_alpha.py').read_text(encoding='utf-8')


class FakeWakeWebsocket:
    def __init__(self, messages):
        self.messages = list(messages)
        self.sent = []
        self.accepted = False
        self.closed = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        self.sent.append(message)

    async def receive(self):
        if self.messages:
            return self.messages.pop(0)
        raise WebSocketDisconnect()

    async def close(self):
        self.closed = True


class FakeListener:
    def __init__(self, result=None, *, error=None):
        self.config = SimpleNamespace(wake_phrases=('jarvis',), idle_timeout_seconds=60)
        self.result = result
        self.error = error

    async def health(self):
        return SimpleNamespace(ready=True)

    async def warmup(self):
        if self.error:
            raise self.error

    def reset(self):
        pass

    async def feed_pcm(self, payload):
        return self.result


class WakeTraceTests(unittest.IsolatedAsyncioTestCase):
    async def test_ready_listening_and_rejected_transcript_visible_only_in_dev(self):
        socket = FakeWakeWebsocket([
            {'text': json.dumps({'kind': 'wake_audio_tap_ready'})},
            {'bytes': b'\0' * 960},
        ])
        with patch('apps.desktop_alpha.merged_environment', return_value={'JARVIS_DESKTOP_CONVERSATION_TRACE': '1'}):
            service = DesktopWakeService(runtime=object(), listener=FakeListener(WakeListenerResult('hello computer', None)))
        output = io.StringIO()
        with redirect_stdout(output):
            await service.listen(socket)
        self.assertIn('[Jarvis Wake] phase=ready', output.getvalue())
        self.assertIn('phase=listening | microphone=active', output.getvalue())
        self.assertIn('phase=ignored | transcript="hello computer"', output.getvalue())
        self.assertTrue(any(x['kind'] == 'wake_ignored' for x in socket.sent))

    async def test_production_trace_does_not_print_ignored_transcript(self):
        socket = FakeWakeWebsocket([{'bytes': b'\0' * 960}])
        with patch('apps.desktop_alpha.merged_environment', return_value={}):
            service = DesktopWakeService(runtime=object(), listener=FakeListener(WakeListenerResult('private speech', None)))
        output = io.StringIO()
        with redirect_stdout(output):
            await service.listen(socket)
        self.assertIn('phase=ignored | transcript=hidden', output.getvalue())
        self.assertNotIn('private speech', output.getvalue())

    async def test_warmup_failure_reports_local_wake_unavailable(self):
        socket = FakeWakeWebsocket([])
        with patch('apps.desktop_alpha.merged_environment', return_value={}):
            service = DesktopWakeService(runtime=object(), listener=FakeListener(error=RuntimeError('STT not ready')))
        output = io.StringIO()
        with redirect_stdout(output):
            await service.listen(socket)
        self.assertIn('phase=unavailable', output.getvalue())
        self.assertTrue(any(x['kind'] == 'wake_unavailable' for x in socket.sent))

    def test_old_socket_callbacks_cannot_rearm_wake_listener(self):
        self.assertIn('wakeGenerationRef.current += 1', APP)
        self.assertIn('wakeGenerationRef.current !== generation || wakeWsRef.current !== ws', APP)
        self.assertIn('wakeGenerationRef.current === generation && presenceRef.current', APP)

    def test_mic_tap_reports_start_or_error(self):
        self.assertIn("kind: 'wake_audio_tap_ready'", APP)
        self.assertIn("kind: 'wake_audio_tap_error'", APP)
        self.assertIn('phase=mic_error', HOST)

    def test_typed_wake_is_not_logged_as_voice_wake(self):
        self.assertIn("if (reason === 'typed_wake') dispatchTextToRealtime(preservedCommand, 'typed')", APP)
        self.assertIn("else dispatchTextToRealtime(preservedCommand, 'wake_transcript')", APP)


if __name__ == '__main__':
    unittest.main()
