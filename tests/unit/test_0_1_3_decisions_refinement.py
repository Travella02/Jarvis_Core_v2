"""Safety and instrumentation tests for the 0.1.3 repair1 classifier refinement."""
from __future__ import annotations
import asyncio
import json
import unittest
from pathlib import Path
import httpx

from providers.intelligence.openai.decisions_shadow import (
    DecisionsShadowProbe, QUESTION_SET, format_decisions_input,
)
from scripts.decisions_route_eval import CASES

ROOT=Path(__file__).resolve().parents[2]
HOST=(ROOT/'apps/desktop_alpha.py').read_text(encoding='utf-8')


def response(route='direct',sleep=.1,memory=.05):
    return {'answers':[
        {'name':'jarvis_route','type':'choice','choice':route,'confidence':.9},
        {'name':'explicit_sleep_intent','type':'predicate','probability':sleep},
        {'name':'private_memory_required','type':'predicate','probability':memory},
    ],'usage':{'input_tokens':475}}


class RefinementTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_request_three_questions_and_bounded_context(self):
        payloads=[]
        async def handler(req):
            payloads.append(json.loads(req.content))
            return httpx.Response(200,json=response('sleep', .99, .02))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            logs=[]; shadow=DecisionsShadowProbe('dev-fake',client=client,log=logs.append)
            shadow.observe_transcript(1,'What is 2 + 2?',transcript_ms=160)
            shadow.observe_reply(1, 'Four. ' + 'X'*900)
            await asyncio.gather(*shadow._tasks)
            shadow.observe_transcript(2,"Thanks Jarvis, that's all.",transcript_ms=195)
            shadow.observe_mini_route(2,'sleep')
            await asyncio.gather(*shadow._tasks)
            self.assertEqual(len(payloads),2)
            self.assertEqual(len(payloads[1]['questions']),3)
            self.assertIn("Thanks Jarvis, that's all.",payloads[1]['input'])
            self.assertIn('Previous assistant reply: Four.',payloads[1]['input'])
            self.assertLess(len(payloads[1]['input']), 2600)
            self.assertTrue(any('sleep_probability=0.99' in line for line in logs))
            self.assertTrue(any('estimated_speech_end_to_decisions_ready_ms=' in line for line in logs))
            self.assertFalse(any('X'*50 in line for line in logs))
            await shadow.close()

    async def test_mini_may_win_before_transcript_even_when_api_fast(self):
        async def handler(req): return httpx.Response(200,json=response())
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            logs=[]; shadow=DecisionsShadowProbe('fake',client=client,log=logs.append)
            shadow.observe_mini_route(4,'direct')
            shadow.observe_transcript(4,'What is two plus two?',transcript_ms=800)
            await asyncio.gather(*shadow._tasks)
            self.assertTrue(any('arrival_order=mini_before_transcript' in x for x in logs))
            self.assertTrue(any('counterfactual_first_audio=not_measured' in x for x in logs))
            await shadow.close()

    async def test_no_audio_or_host_authority_mutated(self):
        self.assertIn('observe_voice_timing(',HOST)
        self.assertIn('observe_reply(turn',HOST)
        self.assertIn('observe_transcript(turn',HOST)
        self.assertNotIn('self._decisions_shadow.route_',HOST)
        self.assertNotIn('self._decisions_shadow.execute',HOST)

    async def test_aux_predicate_refusals_and_invalid_probabilities_fail_soft(self):
        async def handler(req):
            body=response('direct');body['answers'][1]={'type':'refusal','name':'explicit_sleep_intent'}
            body['answers'][2]['probability']=2.0
            return httpx.Response(200,json=body)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            logs=[]; shadow=DecisionsShadowProbe('fake',client=client,log=logs.append)
            shadow.observe_transcript(3,'Thanks Jarvis.')
            shadow.observe_mini_route(3,'direct')
            await asyncio.gather(*shadow._tasks)
            self.assertTrue(any('route=direct' in x and 'sleep_probability=n/a' in x for x in logs))
            await shadow.close()

    async def test_original_mini_route_remains_authoritative_even_when_decisions_differs(self):
        async def handler(req): return httpx.Response(200,json=response('direct',.96,.04))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            logs=[]; shadow=DecisionsShadowProbe('fake',client=client,log=logs.append)
            shadow.observe_mini_route(5,'sleep')
            shadow.observe_transcript(5,"That's all, Jarvis.")
            await asyncio.gather(*shadow._tasks)
            self.assertTrue(any('mini_route=sleep | decisions_route=direct | agreement=no | authority=mini' in x for x in logs))
            await shadow.close()

    def test_balanced_case_bank(self):
        ids=[x[0] for x in CASES]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertGreaterEqual(len(ids),25)
        self.assertIn('sleep_thats_all',ids)
        self.assertIn('memory_pet',ids)
        self.assertIn('thanks',ids)
        self.assertEqual(len(QUESTION_SET),3)
        self.assertIn('Previous assistant reply:',format_decisions_input('one more',previous_reply='hello'))

if __name__=='__main__': unittest.main()
