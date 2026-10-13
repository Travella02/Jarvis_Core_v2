"""Repair16 diagnostic-only follow-up, privacy, behavior, and provider error labels."""
from __future__ import annotations
import asyncio
import io
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from apps.desktop_luna import DesktopLunaDelegator, _safe_core_failure_fields
from core.intelligence import DelegationStatus
from providers.intelligence.openai.provider import OpenAIProvider

class FakeCore:
    def __init__(self, result): self.result=result
    async def execute(self, request, *, conversation): return self.result

class FakeConversation:
    async def cancel_active_turn(self, message): return True

class LogTests(IsolatedAsyncioTestCase):
    async def run_case(self, result):
        delivered=[]
        async def notify(message): delivered.append(message)
        delegator=DesktopLunaDelegator(orchestrator=FakeCore(result),conversation=FakeConversation(),notify=notify)
        stream=io.StringIO()
        with redirect_stdout(stream):
            delegator.transcript(1,'Analyze multi-tenant access boundaries')
            self.assertTrue(delegator.selected(1))
            for _ in range(100):
                if not delegator._tasks: break
                await asyncio.sleep(.001)
            else: self.fail('Delegation did not complete')
            await delegator.close()
        return stream.getvalue(),delivered

    async def test_http_400_is_identified_without_leaking_detail(self):
        secret='sk-secret-must-never-be-logged'
        result=SimpleNamespace(status=DelegationStatus.FAILED,text='',
            detail='OpenAI request failed with HTTP 400 (BadRequestError; code=unsupported_parameter; param=prompt_cache_options)\n'+secret,
            decision=SimpleNamespace(route_name='strong'),provider_response_id=None)
        output,sent=await self.run_case(result)
        for needle in ('phase=core_failed','status=failed','route=strong','http_status=400',
                       'error_type=BadRequestError','error_code=unsupported_parameter',
                       'error_param=prompt_cache_options','response_id_present=False'):
            self.assertIn(needle,output)
        self.assertNotIn(secret,output)
        self.assertNotIn('prompt_cache_options)\n',output)
        self.assertEqual(len(sent),1)
        self.assertEqual(sent[0]['status'],'failed')
        self.assertNotIn(secret,str(sent))

    async def test_unknown_errors_do_not_print_untrusted_text(self):
        secret='PRIVATE_USER_PROMPT_AND_BEARER_ABC123'
        result=SimpleNamespace(status=DelegationStatus.FAILED,text='',detail=secret,
            decision=SimpleNamespace(route_name=secret),provider_response_id=secret)
        output,sent=await self.run_case(result)
        self.assertIn('detail_class=unclassified',output)
        self.assertIn('route=redacted',output)
        self.assertIn('response_id_present=True',output)
        self.assertNotIn(secret,output)

    async def test_success_remains_unchanged(self):
        result=SimpleNamespace(status=DelegationStatus.COMPLETED,text='Three recommended designs',detail=None,
            decision=SimpleNamespace(route_name='strong'),provider_response_id='resp_opaque')
        output,sent=await self.run_case(result)
        self.assertNotIn('phase=core_failed',output)
        self.assertEqual(sent[0]['text'],'Three recommended designs')
        self.assertEqual(sent[0]['status'],'completed')

class ProviderTests(TestCase):
    def test_safe_exception_labels_only(self):
        class BadRequestError(Exception):
            status_code=400
            code='unsupported_parameter'
            param='prompt_cache_options'
            body={'error':{'message':'sk-secret and prompt content'}}
            def __str__(self): return 'sk-secret and prompt content'
        detail=OpenAIProvider._safe_exception_detail(BadRequestError('sk-secret'))
        self.assertIn('HTTP 400',detail)
        self.assertIn('BadRequestError',detail)
        self.assertIn('code=unsupported_parameter',detail)
        self.assertIn('param=prompt_cache_options',detail)
        self.assertNotIn('sk-secret',detail)
    def test_invalid_metadata_is_rejected(self):
        class Unsafe(Exception):
            status_code=429
            code='sk-secret/malicious'
            param='user.email@private.test'
        detail=OpenAIProvider._safe_exception_detail(Unsafe())
        self.assertEqual(detail,'OpenAI request failed with HTTP 429 (Unsafe)')
    def test_no_raw_detail_reemitted_from_parser(self):
        fields=_safe_core_failure_fields('Bearer secret user content')
        self.assertEqual(fields['detail_class'],'unclassified')
        self.assertEqual(fields['http_status'],'n/a')
