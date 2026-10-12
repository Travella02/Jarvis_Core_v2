"""Repair6 experimental shadow concurrency regression tests; no live API needed."""
import asyncio
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from core.intelligence import IntelligenceEvent, IntelligenceEventType
from providers.voice_frontend.openai_realtime.config import OpenAIRealtimeConfig
from providers.voice_frontend.openai_realtime.parallel_probe import ParallelShadowProbe


class FakeReadOnlyProvider:
    def __init__(self, *, delay=0.0):
        self.calls = []
        self.closed = False
        self.delay = delay
        self.called = asyncio.Event()

    async def stream_response(self, context, tools, policy, token):
        self.calls.append((context, tools, policy, token))
        self.called.set()
        await asyncio.sleep(self.delay)
        yield IntelligenceEvent(event_type=IntelligenceEventType.TEXT_DELTA, text_delta="Mars")
        yield IntelligenceEvent(event_type=IntelligenceEventType.COMPLETED)

    async def close(self):
        self.closed = True


class ParallelShadowTests(unittest.IsolatedAsyncioTestCase):
    async def test_stateless_tool_free_and_no_reply_published(self):
        fake = FakeReadOnlyProvider()
        probe = ParallelShadowProbe(fake)
        output = io.StringIO()
        with redirect_stdout(output):
            probe.on_transcript(1, "What is Mars?")
            # Wait for actual completion instead of assuming Windows completes
            # a scheduled task within a fixed 15 ms scheduler window.
            await asyncio.wait_for(probe._task, timeout=3.0)
            await probe.close()
        self.assertEqual(len(fake.calls), 1)
        context, tools, policy, token = fake.calls[0]
        self.assertEqual(tools, ())
        self.assertEqual(policy.level, "none")
        self.assertEqual(context.messages[-1]["content"], "What is Mars?")
        self.assertEqual(context.metadata["input_channel"], "parallel_shadow_probe")
        self.assertIn("status=completed", output.getvalue())
        self.assertTrue(fake.closed)

    async def test_route_cancels_shadow_before_result(self):
        fake = FakeReadOnlyProvider(delay=1)
        probe = ParallelShadowProbe(fake)
        output = io.StringIO()
        with redirect_stdout(output):
            probe.on_transcript(2, "Investigate this problem")
            # Ensure the fake provider has entered streaming before canceling.
            await asyncio.wait_for(fake.called.wait(), timeout=3.0)
            probe.on_route(2, "reasoning")
            await probe.close()
        self.assertEqual(len(fake.calls), 1)
        self.assertTrue(fake.calls[0][3].is_cancelled)
        self.assertIn("status=cancelled", output.getvalue())

    async def test_late_transcript_does_not_start_work(self):
        fake = FakeReadOnlyProvider()
        probe = ParallelShadowProbe(fake)
        output = io.StringIO()
        with redirect_stdout(output):
            probe.on_route(3, "direct")
            probe.on_transcript(3, "Mars")
            await probe.close()
        self.assertEqual(fake.calls, [])
        self.assertIn("transcript_after_route", output.getvalue())

    async def test_newer_turn_supersedes_prior(self):
        fake = FakeReadOnlyProvider(delay=1)
        probe = ParallelShadowProbe(fake)
        with redirect_stdout(io.StringIO()):
            probe.on_transcript(4, "Old")
            await asyncio.wait_for(fake.called.wait(), timeout=3.0)
            fake.called.clear()
            probe.on_transcript(5, "New")
            await asyncio.wait_for(fake.called.wait(), timeout=3.0)
            await probe.close()
        self.assertEqual(len(fake.calls), 2)
        self.assertTrue(fake.calls[0][3].is_cancelled)

    async def test_deadline(self):
        fake = FakeReadOnlyProvider(delay=1)
        probe = ParallelShadowProbe(fake, deadline_seconds=.01)
        output = io.StringIO()
        with redirect_stdout(output):
            probe.on_transcript(1, "Mars")
            await asyncio.wait_for(probe._task, timeout=3.0)
            await probe.close()
        self.assertIn("status=timeout", output.getvalue())


class ParallelShadowConfigTests(unittest.TestCase):
    def test_default_off(self):
        cfg = OpenAIRealtimeConfig.from_env({"OPENAI_API_KEY": "test"})
        self.assertFalse(cfg.parallel_shadow_probe)

    def test_opt_in(self):
        cfg = OpenAIRealtimeConfig.from_env({"OPENAI_API_KEY": "test", "JARVIS_PARALLEL_SHADOW_PROBE":"yes"})
        self.assertTrue(cfg.parallel_shadow_probe)

    def test_bad_flag_rejected(self):
        with self.assertRaisesRegex(ValueError, "boolean"):
            OpenAIRealtimeConfig.from_env({"JARVIS_PARALLEL_SHADOW_PROBE":"maybe"})

    def test_frontend_is_text_only_and_out_of_band(self):
        source = (Path(__file__).resolve().parents[2] / "apps/desktop/ui/src/App.tsx").read_text(encoding="utf-8")
        start = source.index("const requestParallelShadow")
        end = source.index("const cancelParallelShadows")
        candidate = source[start:end]
        self.assertIn("conversation: 'none'", candidate)
        self.assertIn("output_modalities: ['text']", candidate)
        self.assertIn("tools: []", candidate)
        self.assertIn("tool_choice: 'none'", candidate)
        self.assertNotIn("output_modalities: ['audio']", candidate)
        self.assertIn("response.cancel", source)
        self.assertIn("response_id: id", source)

if __name__ == '__main__':
    unittest.main()
