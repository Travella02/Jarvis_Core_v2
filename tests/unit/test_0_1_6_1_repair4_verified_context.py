"""0.1.6.1 Repair4: verified task context and safe ordinal reconciliation."""
import unittest
from pathlib import Path
from apps.desktop_managed_browser import ManagedDesktopBrowserSession
from core.tools.default_browser_bridge import DefaultBrowserBridgeAdapter
from tests.unit.test_0_1_5_9_browser_result_selection import FakeBrowserBridge

ROOT = Path(__file__).resolve().parents[2]

class VerifiedContextTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bridge = FakeBrowserBridge()
        self.adapter = DefaultBrowserBridgeAdapter(self.bridge, open_default=lambda _:self.fail('unexpected browser open'))
        self.session = ManagedDesktopBrowserSession(browser=self.adapter, advanced=True, bridge_mode=True)
        self.turn = 0

    async def ask(self, utterance, args):
        self.turn += 1
        self.session.on_turn_started(self.turn)
        return await self.session.handle(turn=self.turn,selected_tool='browser_action',source='voice',binding='item_1', transcript=utterance,arguments=args)

    async def test_wrong_proposed_host_repaired_only_from_independent_speech(self):
        result = await self.ask('Let us watch the first video', {'site':'first video','intent':'open'})
        self.assertEqual(result.status,'completed',result)
        self.assertEqual(result.action_context, {'category':'browser','intent':'select_result'})
        self.assertEqual([op for op,_ in self.bridge.ops if op=='navigate'], ['navigate'])

    async def test_direct_tool_ordinal_mismatch_is_not_silently_corrected(self):
        result = await self.ask('Play the first video',{'site':'current','intent':'select_result','value':2})
        self.assertEqual(result.status,'failed')
        self.assertIsNone(result.action_context)
        self.assertFalse(any(op=='navigate' for op,_ in self.bridge.ops))

    async def test_normal_site_open_is_not_reinterpreted_as_result_selection(self):
        result = await self.ask('Open Wikipedia',{'site':'wikipedia.org','intent':'open'})
        # Fake bridge deliberately cannot open unrelated sites; what matters
        # is that it never converted this action into numbered selection.
        self.assertEqual(result.status,'failed',result)
        self.assertIsNone(result.action_context)
        self.assertFalse(any(op=='navigate' and '/watch?' in str(args.get('url','')) for op,args in self.bridge.ops))

    async def test_hypothetical_never_selects_result(self):
        result = await self.ask('What if we watched the first video?', {'site':'first video','intent':'open'})
        self.assertEqual(result.status,'failed')
        self.assertFalse(any(op=='navigate' for op,_ in self.bridge.ops))

    async def test_missing_active_search_page_still_rejected(self):
        self.bridge.tabs[0]['url']='https://www.wikipedia.org/'
        result = await self.ask('Play the first video',{'site':'first video','intent':'open'})
        self.assertEqual(result.status,'failed')
        self.assertFalse(any(op=='navigate' for op,_ in self.bridge.ops))

    def test_renderer_only_accepts_core_verified_context(self):
        text = (ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        self.assertIn("payload.action_context",text)
        self.assertIn("const recentContextNote = recentVerified",text)
        self.assertIn("instructions:(coreLunaProbeRef.current",text)
        self.assertIn("+ recentContextNote}}));",text)
        self.assertIn("context?.category === 'browser'",text)
        self.assertIn("lastVerified.turn === latencyRef.current.turn - 1",text)
        self.assertIn("performance.now() - lastVerified.at <= 15000",text)

    def test_core_reports_verified_context_not_raw_tool_arguments(self):
        text = (ROOT/'apps/desktop_alpha.py').read_text(encoding='utf-8')
        self.assertIn("'action_context':result.action_context if result.status=='completed' else None",text)
        self.assertNotIn("'action_context':msg.get('arguments')",text)

if __name__=='__main__': unittest.main()
