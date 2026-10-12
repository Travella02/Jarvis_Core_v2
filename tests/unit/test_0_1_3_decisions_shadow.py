"""0.1.3 shadow: no real calls, no routing mutation, no dependence on audio."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import unittest

import httpx

from providers.intelligence.openai.decisions_shadow import (
    DECISIONS_ENDPOINT, DECISIONS_MODEL, DecisionsShadowProbe,
)
from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig

ROOT = Path(__file__).resolve().parents[2]
HOST = (ROOT / 'apps/desktop_alpha.py').read_text(encoding='utf-8')
APP = (ROOT / 'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
LAUNCHER = (ROOT / 'scripts/realtime_ab.py').read_text(encoding='utf-8')


def answer(route='direct', confidence=0.97, tokens=400):
    return {'answers':[{'name':'jarvis_route','type':'choice','choice':route,
                        'confidence':confidence}], 'usage':{'input_tokens':tokens}}


class ShadowApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_sends_only_to_authorized_decisions_endpoint_and_does_not_route(self):
        captured = []
        async def handler(req):
            captured.append(req)
            return httpx.Response(200, json=answer('sleep'))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            logs=[]
            probe=DecisionsShadowProbe('development-fake-key', client=client, log=logs.append)
            probe.observe_transcript(7, 'Thanks, Jarvis. That is all.')
            probe.observe_mini_route(7,'direct')
            await asyncio.gather(*probe._tasks)
            self.assertEqual(len(captured), 1)
            self.assertEqual(str(captured[0].url), DECISIONS_ENDPOINT)
            self.assertEqual(captured[0].headers['Authorization'],'Bearer development-fake-key')
            self.assertEqual(json.loads(captured[0].read())["model"], DECISIONS_MODEL)
            self.assertTrue(any('phase=compare' in x and 'agreement=no' in x for x in logs))
            self.assertTrue(all('development-fake-key' not in x for x in logs))
            await probe.close()

    async def test_route_before_transcript_still_executes_comparison(self):
        async def handler(req):
            return httpx.Response(200, json=answer('direct'))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            logs=[]
            probe=DecisionsShadowProbe('fake', client=client, log=logs.append)
            probe.observe_mini_route(2, 'none')
            probe.observe_transcript(2,'What is 2+2?')
            await asyncio.gather(*probe._tasks)
            self.assertTrue(any('phase=compare' in x and 'agreement=yes' in x for x in logs))
            await probe.close()

    async def test_duplicate_transcript_does_not_double_bill(self):
        calls=[]
        async def handler(req):
            calls.append(req)
            return httpx.Response(200, json=answer())
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            probe=DecisionsShadowProbe('fake', client=client, log=lambda _:None)
            probe.observe_transcript(5,'hello')
            probe.observe_transcript(5,'hello')
            await asyncio.gather(*probe._tasks)
            self.assertEqual(len(calls),1)
            await probe.close()

    async def test_invalid_response_and_http_errors_are_fail_closed(self):
        async def handler(req):
            return httpx.Response(401, json={'error':{'message':'do not log this private text'}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            logs=[]
            probe=DecisionsShadowProbe('fake', client=client, log=logs.append)
            probe.observe_transcript(3,'hello')
            probe.observe_mini_route(3,'direct')
            await asyncio.gather(*probe._tasks)
            self.assertTrue(any('status=http_401' in x for x in logs))
            self.assertFalse(any('private text' in x for x in logs))
            self.assertTrue(any('agreement=n/a' in x for x in logs))
            await probe.close()

    async def test_skips_empty_and_unbounded_transcripts(self):
        async def handler(req):
            raise AssertionError('unexpected network')
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            logs=[]
            probe=DecisionsShadowProbe('fake', client=client, log=logs.append)
            probe.observe_transcript(1,'')
            probe.observe_transcript(2,'X'*2100)
            self.assertEqual(len(probe._tasks),0)
            self.assertTrue(any('transcript_too_long' in x for x in logs))
            await probe.close()

    async def test_close_cancels_pending_without_mutating_authority(self):
        started=asyncio.Event()
        async def handler(req):
            started.set()
            await asyncio.sleep(99)
            return httpx.Response(200, json=answer())
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            probe=DecisionsShadowProbe('fake', client=client, log=lambda _:None)
            probe.observe_transcript(1,'some question')
            await asyncio.wait_for(started.wait(),1)
            await asyncio.wait_for(probe.close(),1)
            self.assertFalse(probe._tasks)

    async def test_refusal_does_not_produce_route(self):
        async def handler(req):
            return httpx.Response(200, json={'answers':[{'type':'refusal','name':'jarvis_route'}], 'usage':{'input_tokens':200}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            logs=[]
            probe=DecisionsShadowProbe('fake', client=client, log=logs.append)
            probe.observe_transcript(7,'hello')
            probe.observe_mini_route(7, 'direct')
            await asyncio.gather(*probe._tasks)
            self.assertTrue(any('status=refusal' in x for x in logs))
            self.assertTrue(any('agreement=n/a' in x for x in logs))
            await probe.close()


class ShadowWiringTests(unittest.TestCase):
    def test_default_off_and_explicit_optin(self):
        base = OpenAIRealtimeConfig.from_env({'OPENAI_API_KEY':'test'})
        self.assertFalse(base.decisions_shadow_probe)
        enabled = OpenAIRealtimeConfig.from_env({'OPENAI_API_KEY':'test', 'JARVIS_DECISIONS_SHADOW_PROBE':'1'})
        self.assertTrue(enabled.decisions_shadow_probe)

    def test_launcher_does_not_change_existing_mini_overlap(self):
        self.assertIn('"mini-overlap-decisions-shadow"',LAUNCHER)
        self.assertIn('"JARVIS_DECISIONS_SHADOW_PROBE"] = "1" if decisions_shadow else "0"',LAUNCHER)
        self.assertIn('"JARVIS_REALTIME_OVERLAP_PROBE"] = "1" if overlap_probe else "0"', LAUNCHER)

    def test_host_is_only_observer_and_renderer_audio_unchanged(self):
        self.assertIn('self._decisions_shadow.observe_transcript(turn',HOST)
        self.assertIn('self._decisions_shadow.observe_mini_route(turn',HOST)
        self.assertIn('self._decisions_shadow.observe_mini_route(int(message.get("turn") or 0), phase)',HOST)
        self.assertIn('await decisions_shadow.close()',HOST)
        self.assertNotIn('DecisionsShadow',APP)
        self.assertIn("void enterSleep('voice_command')",APP)

if __name__ == '__main__':
    unittest.main()
