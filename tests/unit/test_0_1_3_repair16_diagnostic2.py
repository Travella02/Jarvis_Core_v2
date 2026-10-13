"""Repair16 Diagnostic2: provider budget/reason telemetry with no secret leakage."""
from __future__ import annotations
import asyncio
import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace

from apps.desktop_luna import DesktopLunaDelegator, _safe_core_budget_fields
from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.intelligence import IntelligenceContext, IntelligenceEventType, ReasoningPolicy, DelegationStatus
from providers.intelligence.openai.config import OpenAIProviderConfig
from providers.intelligence.openai.provider import OpenAIProvider


class EventStream:
    def __init__(self, events): self.items = list(events)
    def __aiter__(self): return self
    async def __anext__(self):
        if not self.items: raise StopAsyncIteration
        return self.items.pop(0)
    async def close(self): pass

class Responses:
    def __init__(self, events): self.events = events; self.calls = []
    async def create(self, **kwargs): self.calls.append(kwargs); return EventStream(self.events)

class FakeRouter:
    def __init__(self, provider): self.provider = provider
    def resolve(self, route):
        if route != 'primary': raise KeyError(route)
        return self.provider

class FakeCore:
    def __init__(self, provider, result):
        self.provider_router = FakeRouter(provider)
        self.result = result
    async def execute(self, request, *, conversation): return self.result

class FakeConversation:
    async def cancel_active_turn(self, reason): return True


def event(name, **kwargs): return SimpleNamespace(type=name, **kwargs)
def response(identifier, **kwargs): return SimpleNamespace(id=identifier, **kwargs)

class Diagnostic2Tests(unittest.IsolatedAsyncioTestCase):
    async def build(self, *, reason='max_output_tokens', usage=True, model='gpt-6-luna'):
        fake_secret = 'sk-veryprivate_should_not_appear'
        details = {'reason': reason}
        usage_values = {'input_tokens': 123, 'output_tokens': 256,
                        'output_tokens_details': {'reasoning_tokens': 210}} if usage else None
        resp = response('resp_42', model=model, status='incomplete',
                        incomplete_details=details, usage=usage_values,
                        text=fake_secret, error=fake_secret)
        api = Responses([
            event('response.created', response=response('resp_42')),
            event('response.output_text.delta', delta='Partial answer should not be spoken.'),
            event('response.incomplete', response=resp),
        ])
        provider = OpenAIProvider(OpenAIProviderConfig(api_key='fake', model='gpt-6-luna', voice_max_output_tokens=256),
                                  client=SimpleNamespace(responses=api))
        context = IntelligenceContext(
            trace=CorrelationContext('c', 'request-1', 't'),
            messages=({'role':'user', 'content': 'Analyze three architectures'},),
            metadata={'input_channel':'voice'},
        )
        events = [e async for e in provider.stream_response(context, (), ReasoningPolicy(level='low'), CancellationToken())]
        return provider, events, api, fake_secret

    async def test_incomplete_response_records_budget_and_tokens_without_raw_text(self):
        provider, events, api, secret = await self.build()
        self.assertEqual(events[-1].event_type, IntelligenceEventType.DEGRADED)
        self.assertEqual(events[-1].detail, 'OpenAI response ended incomplete')
        self.assertEqual(api.calls[0]['max_output_tokens'], 256)
        diag = provider.response_diagnostics('resp_42')
        self.assertEqual(diag['requested_output_limit'], 256)
        self.assertEqual(diag['requested_model'], 'gpt-6-luna')
        self.assertEqual(diag['incomplete_reason'], 'max_output_tokens')
        self.assertEqual(diag['input_tokens'], 123)
        self.assertEqual(diag['output_tokens'], 256)
        self.assertEqual(diag['reasoning_tokens'], 210)
        self.assertNotIn(secret, repr(diag))
        self.assertEqual(provider.response_diagnostics('not-the-response'), {})
        self.assertEqual(provider.response_diagnostics(None), {})

    async def test_privacy_and_missing_usage(self):
        provider, events, _, secret = await self.build(reason='sensitive_user_text_and_'+ 'sk-veryprivate_should_not_appear',usage=False,model=secret if False else 'gpt-6-luna')
        diag=provider.response_diagnostics('resp_42')
        self.assertEqual(diag['incomplete_reason'], 'unknown')
        self.assertNotIn('output_tokens',diag)
        self.assertNotIn(secret,repr(diag))
        result=SimpleNamespace(status=DelegationStatus.FAILED,text=secret,detail='OpenAI response ended incomplete',
                               decision=SimpleNamespace(route_name='primary'),provider_response_id='resp_42')
        fields=_safe_core_budget_fields(FakeCore(provider,result),result)
        self.assertEqual(fields['diagnostic_match'],'true')
        self.assertEqual(fields['reason'],'unknown')
        self.assertEqual(fields['output_tokens'],'n/a')
        self.assertNotIn(secret,repr(fields))
        result.provider_response_id='other_resp'
        self.assertEqual(_safe_core_budget_fields(FakeCore(provider,result),result)['diagnostic_match'],'false')

    async def test_logs_only_safe_budget_fields_and_keeps_failure_speech(self):
        provider, events, _, secret = await self.build()
        result=SimpleNamespace(status=DelegationStatus.FAILED,text=secret,detail='OpenAI response ended incomplete',
                               decision=SimpleNamespace(route_name='primary'),provider_response_id='resp_42')
        sent=[]
        async def notify(value): sent.append(value)
        bridge=DesktopLunaDelegator(orchestrator=FakeCore(provider,result),conversation=FakeConversation(),notify=notify)
        log=io.StringIO()
        with redirect_stdout(log):
            bridge.transcript(1,'Compare 3 architectures')
            self.assertTrue(bridge.selected(1))
            for _ in range(200):
                if not bridge._tasks: break
                await asyncio.sleep(.001)
            else: self.fail('Task did not finish')
            await bridge.close()
        printed=log.getvalue()
        self.assertIn('phase=provider_terminal',printed)
        for expected in ('model=gpt-6-luna','output_limit=256','incomplete_reason=max_output_tokens',
                         'output_tokens=256','reasoning_tokens=210','diagnostic_match=true'):
            self.assertIn(expected,printed)
        self.assertNotIn(secret,printed)
        self.assertEqual(sent[0]['status'],'failed')
        self.assertEqual(sent[0]['text'],"I couldn't complete that request with Luna. Please try again.")

    def test_bad_sdk_fields_never_enter_telemetry(self):
        unsafe='sk-secret-not-for-terminal'
        obj=response('resp_42',status=['sensitive'],incomplete_details={'reason':{'raw':unsafe}},
                     usage={'input_tokens':unsafe,'output_tokens':True,'output_tokens_details':{'reasoning_tokens':-3}},
                     raw_text=unsafe)
        diag=OpenAIProvider._safe_response_telemetry(obj)
        self.assertEqual(diag['incomplete_reason'],'unknown')
        self.assertNotIn('reasoning_tokens',diag)
        self.assertNotIn('output_tokens',diag)
        self.assertNotIn(unsafe,repr(diag))

if __name__ == '__main__': unittest.main()
