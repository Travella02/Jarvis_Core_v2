from __future__ import annotations

import asyncio
import unittest

from core.runtime import IntelligenceProviderRouter, JarvisRuntime, RuntimeEventStream, RuntimeSettings


class RuntimeEventStreamTests(unittest.IsolatedAsyncioTestCase):
    def _runtime(self, *, history: int = 64) -> JarvisRuntime:
        runtime = JarvisRuntime(
            settings=RuntimeSettings(event_history_limit=history),
            provider_router=IntelligenceProviderRouter(default_route="primary"),
            version="0.0.7-test",
        )
        runtime.start()
        return runtime

    async def test_live_event_after_snapshot_is_delivered_once(self) -> None:
        runtime = self._runtime()
        stream = RuntimeEventStream(runtime)
        try:
            cursor = runtime.snapshot().event_cursor
            sync = await stream.open(after_sequence=cursor, expected_runtime_id=runtime.runtime_id)
            self.assertTrue(sync.resume_accepted)
            event = runtime.event_bus.emit("live.event", origin="test")
            received = await asyncio.wait_for(stream.next_event(), timeout=1.0)
            self.assertEqual(received.sequence, event.sequence)
            self.assertEqual(stream.last_sequence, event.sequence)
        finally:
            await stream.close()
            runtime.close()

    async def test_nonzero_cursor_requires_runtime_identity(self) -> None:
        runtime = self._runtime()
        stream = RuntimeEventStream(runtime)
        try:
            runtime.event_bus.emit("a", origin="test")
            sync = await stream.open(after_sequence=1)
            self.assertFalse(sync.resume_accepted)
            self.assertEqual(sync.reset_reason, "runtime-identity-required")
            self.assertEqual(sync.replay_events, ())
        finally:
            await stream.close()
            runtime.close()

    async def test_runtime_identity_mismatch_forces_snapshot_reset(self) -> None:
        runtime = self._runtime()
        stream = RuntimeEventStream(runtime)
        try:
            runtime.event_bus.emit("a", origin="test")
            sync = await stream.open(after_sequence=1, expected_runtime_id="runtime-old")
            self.assertFalse(sync.resume_accepted)
            self.assertEqual(sync.reset_reason, "runtime-changed")
        finally:
            await stream.close()
            runtime.close()

    async def test_stale_cursor_reports_history_gap(self) -> None:
        runtime = self._runtime(history=64)
        for number in range(80):
            runtime.event_bus.emit(f"event.{number}", origin="test")
        stream = RuntimeEventStream(runtime)
        try:
            sync = await stream.open(after_sequence=1, expected_runtime_id=runtime.runtime_id)
            self.assertFalse(sync.resume_accepted)
            self.assertEqual(sync.reset_reason, "history-gap")
        finally:
            await stream.close()
            runtime.close()

    async def test_slow_client_overflow_is_detected_not_silently_dropped(self) -> None:
        runtime = self._runtime()
        stream = RuntimeEventStream(runtime, queue_limit=1)
        try:
            cursor = runtime.snapshot().event_cursor
            await stream.open(after_sequence=cursor, expected_runtime_id=runtime.runtime_id)
            runtime.event_bus.emit("one", origin="test")
            runtime.event_bus.emit("two", origin="test")
            await asyncio.sleep(0)
            self.assertTrue(stream.overflowed)
        finally:
            await stream.close()
            runtime.close()


if __name__ == "__main__":
    unittest.main()
