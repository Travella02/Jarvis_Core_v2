"""No real browsers, network calls, audio, or model calls in these tests."""
from __future__ import annotations
import asyncio
import unittest

from core.common.ids import CorrelationContext
from core.tools import ToolRequest, ToolResultStatus
from core.tools.gateway import CoreToolGateway, ConfirmedUserAction, _requested_site


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.launched = []
        self.gateway = CoreToolGateway(launch_browser=lambda url: self.launched.append(url) or True)
        self.trace = CorrelationContext.create()
        self.action = ConfirmedUserAction(self.trace.turn_id, "Jarvis, open YouTube.", True, True)

    def request(self, **overrides):
        kwargs = dict(trace=self.trace, tool_name="desktop_browser", operation="open_approved_site",
                      arguments={"site":"youtube"}, idempotency_key="one-command")
        kwargs.update(overrides)
        return ToolRequest(**kwargs)

    async def test_open_is_real_action_only_with_independent_matching_evidence(self):
        result = await self.gateway.execute(self.request(), evidence=self.action)
        self.assertEqual(result.status, ToolResultStatus.SUCCEEDED)
        self.assertEqual(self.launched, ["https://www.youtube.com/"])
        self.assertFalse(result.output["page_loaded_verified"])
        self.assertIn("sent YouTube", result.output["user_message"])

    async def test_model_tool_call_alone_cannot_execute(self):
        result = await self.gateway.execute(self.request(), evidence=None)
        self.assertEqual(result.error_code, "missing_independent_user_authorization")
        self.assertEqual(self.launched, [])

    async def test_unconfirmed_wrong_turn_and_remote_fail_closed(self):
        for ev in [ConfirmedUserAction(self.trace.turn_id, "open youtube", False, True),
                   ConfirmedUserAction("other-turn", "open youtube", True, True),
                   ConfirmedUserAction(self.trace.turn_id, "open youtube", True, False)]:
            self.assertEqual((await self.gateway.execute(self.request(), evidence=ev)).status, ToolResultStatus.DENIED)
        self.assertEqual(self.launched, [])

    async def test_unknown_capability_and_arbitrary_web_sites_rejected(self):
        for request in (self.request(tool_name="shell"), self.request(operation="run"),
                        self.request(arguments={"site":"google"}),
                        self.request(arguments={"site":"youtube","url":"https://evil.example"}),
                        self.request(arguments={"url":"https://www.youtube.com/"})):
            self.assertEqual((await self.gateway.execute(request, evidence=self.action)).status, ToolResultStatus.DENIED)
        self.assertEqual(self.launched, [])

    async def test_model_claim_is_not_authorization_for_other_intent(self):
        for utterance in ["Don't open YouTube", "Please explain how to open YouTube",
                          "Open Youtube and delete my files", "Could you open YouTube later, after I leave?",
                          "Remember: open YouTube", "Jarvis, open Netflix", "quote: open youtube"]:
            ev = ConfirmedUserAction(self.trace.turn_id, utterance, True, True)
            self.assertEqual((await self.gateway.execute(self.request(), evidence=ev)).status, ToolResultStatus.DENIED)
        self.assertEqual(self.launched, [])

    async def test_duplicates_and_concurrent_calls_only_launch_once(self):
        results = await asyncio.gather(*(self.gateway.execute(self.request(), evidence=self.action) for _ in range(5)))
        self.assertTrue(all(r.status == ToolResultStatus.SUCCEEDED for r in results))
        self.assertEqual(len(self.launched), 1)

    async def test_launch_failure_cannot_be_called_success_or_retried_automatically(self):
        attempts = []
        gateway = CoreToolGateway(launch_browser=lambda url: attempts.append(url) or False)
        one = await gateway.execute(self.request(), evidence=self.action)
        two = await gateway.execute(self.request(), evidence=self.action)
        self.assertEqual(one.status, ToolResultStatus.FAILED)
        self.assertEqual(one.error_code, "browser_launch_failed")
        self.assertEqual(two.status, ToolResultStatus.FAILED)
        self.assertEqual(len(attempts), 1)

    async def test_exceptions_report_failure_without_details_leaking(self):
        def fail(url): raise RuntimeError("private paths / tokens should not leak")
        result = await CoreToolGateway(launch_browser=fail).execute(self.request(), evidence=self.action)
        self.assertEqual(result.status, ToolResultStatus.FAILED)
        self.assertNotIn("private", str(result))

    def test_conservative_command_grammar(self):
        self.assertEqual(_requested_site("Hey Jarvis, open YouTube please!"), "youtube")
        self.assertEqual(_requested_site("open youtube.com"), "youtube")
        for cmd in ("I want to open YouTube", "how to open YouTube", "don't open YouTube",
                    "open google", "open youtube. then send mail"):
            self.assertIsNone(_requested_site(cmd))
