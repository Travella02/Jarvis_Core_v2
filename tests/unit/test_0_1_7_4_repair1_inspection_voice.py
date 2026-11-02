"""0.1.7.4 Repair1: inspection cannot execute; stale cancel cannot silence Core speech."""
import asyncio
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.tools.background_browser import IsolatedBrowserDriver
from core.tools.terra_navigation import (
    TerraNavigator, confirmed_isolated_browser_inspection,
    _isolated_inspection_intent,
)
from tests.unit.test_0_1_7_3_background_reuse import Factory

ENV = {
    'JARVIS_TERRA_NAV_ENABLED':'1',
    'JARVIS_TERRA_NAV_MODE':'isolated_browser',
    'JARVIS_TERRA_NAV_EXECUTE':'1',
    'JARVIS_TERRA_NAV_ALLOW_TYPING':'1',
    'JARVIS_TERRA_BACKGROUND_NATIVE_INSPECT':'1',
    'JARVIS_TERRA_BACKGROUND_DIRECT_LINKS':'1',
    'JARVIS_TERRA_BACKGROUND_URL':'https://example.org/',
    'JARVIS_TERRA_BACKGROUND_HOSTS':'example.org',
}

class CountingClient:
    def __init__(self, actions=None):
        self.calls=0
        self.actions=actions
        self.responses=SimpleNamespace(create=self.create)
    def create(self,**kw):
        self.calls+=1
        if self.actions is not None:
            return SimpleNamespace(output=[{'type':'computer_call','call_id':'call1','actions':self.actions}],output_text='')
        return SimpleNamespace(output=[],output_text='Read-only screenshot understood.')

class TestReadOnlyInspectionBoundary(unittest.TestCase):
    def test_checklist_markers_still_authorize_nothing_but_inspection(self):
        for text in ('[ ] Inspect the isolated background browser at example.org.',
                     '- [ ] Inspect the isolated background browser at example.org.',
                     '* [x] Inspect the isolated background browser at example.org.'):
            self.assertTrue(confirmed_isolated_browser_inspection(text,'example.org'))
            self.assertTrue(_isolated_inspection_intent(text))
        f=Factory();client=CountingClient();n=TerraNavigator(ENV,client=client)
        old=IsolatedBrowserDriver.__enter__
        def enter(driver):driver.factory=f;return old(driver)
        try:
            with patch.object(IsolatedBrowserDriver,'__enter__',enter):
                first=asyncio.run(n.run_async('[ ] Inspect the isolated background browser at example.org.'))
                second=asyncio.run(n.run_async('Inspect the isolated background browser at example.org.'))
            for result in (first,second):
                self.assertEqual(result.code,'observed_only')
                self.assertEqual(result.actions,0)
                self.assertEqual(result.timings['model_ms'],0.0)
            self.assertEqual(client.calls,0)
            self.assertEqual(len(f.launched),1)
            self.assertEqual(f.launched[0].context.pages[0].calls,[('goto','https://example.org/')])
        finally:n.close()

    def test_ambiguous_or_compound_inspection_denied_even_if_execute_enabled(self):
        client=CountingClient();n=TerraNavigator(ENV,client=client)
        requests=(
            'Inspect the isolated backgroundbrowser at example.org.',
            'Inspect the isolated background browser at example.org then click About.',
            'Inspect the isolated background browser at example.org; open a link.',
            'Inspect the isolated background browser at evil.org.',
            'Describe the isolated background browser at example.org and delete a file.',
            'Click the "Inspect" link in the isolated background browser at example.org.',
        )
        for phrase in requests:
            with self.subTest(phrase=phrase):
                r=n.run(phrase)
                self.assertIn(r.code,('inspection_request_unverified','unverified_user_intent'))
                self.assertEqual(r.actions,0)
        self.assertEqual(client.calls,0)
        self.assertIsNone(n._background_driver)

    def test_disabled_native_inspector_may_call_terra_but_cannot_execute_click(self):
        f=Factory();client=CountingClient([{'type':'click','x':24,'y':24}])
        env={**ENV,'JARVIS_TERRA_BACKGROUND_NATIVE_INSPECT':'0'}
        n=TerraNavigator(env,client=client)
        old=IsolatedBrowserDriver.__enter__
        def enter(driver):driver.factory=f;return old(driver)
        try:
            with patch.object(IsolatedBrowserDriver,'__enter__',enter):
                r=asyncio.run(n.run_async('Inspect the background browser at example.org.'))
            self.assertEqual(r.code,'preview_only')
            self.assertEqual(r.actions,0)
            self.assertEqual(client.calls,1)
            self.assertEqual(f.launched[0].context.pages[0].calls,[('goto','https://example.org/')])
        finally:n.close()

    def test_explicit_quoted_link_still_navigates_on_execution_opt_in(self):
        f=Factory();n=TerraNavigator(ENV)
        old=IsolatedBrowserDriver.__enter__
        def enter(driver):driver.factory=f;return old(driver)
        try:
            with patch.object(IsolatedBrowserDriver,'__enter__',enter):
                r=asyncio.run(n.run_async('Click the "About" link in the isolated background browser at example.org.'))
            self.assertEqual(r.code,'background_link_navigated')
            self.assertEqual(r.actions,1)
        finally:n.close()

class TestVoiceErrorOwnership(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(Path(__file__).resolve().parents[2]/'apps/desktop/ui/src/App.tsx').read_text('utf-8')

    def test_late_cancel_not_active_is_nonfatal(self):
        src=self.source
        self.assertIn("if (reason === 'response_cancel_not_active')",src)
        start=src.index("if (reason === 'response_cancel_not_active')")
        fallback=src.index("if (!fallbackCoreLunaVoice(turn,reason)",start)
        self.assertIn("phase:'cancellation_error_ignored'",src[start:fallback])
        self.assertIn('return;',src[start:fallback])

    def test_finished_candidate_not_cancelled_when_tool_chosen(self):
        src=self.source
        self.assertEqual(src.count('overlapCandidateIdRef.current && !overlapCandidateDoneRef.current && dcRef.current?.readyState'),2)

    def test_hypothetical_prompt_does_not_assume_foreground_required(self):
        self.assertIn('WITHOUT focusing the users real browser or foreground window',self.source)
        self.assertIn('do not assert a specific link exists',self.source)

if __name__=='__main__':unittest.main()
