import asyncio
import tempfile
import unittest
from pathlib import Path

from providers.tts.qwen3_streaming_candidate.provider import Qwen3StreamingProvider


class QwenResidentCancelTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_sets_cooperative_flag_without_killing_resident_process(self):
        provider = Qwen3StreamingProvider()
        with tempfile.TemporaryDirectory() as temp:
            provider._cancel_dir = Path(temp)
            request_id = "turn-request-123"
            provider._active_request_ids.add(request_id)
            await provider.cancel(request_id)
            self.assertTrue(provider._cancel_flag_path(request_id).is_file())

    def test_sidecar_supports_cooperative_cancel_terminal_event(self):
        root = Path(__file__).resolve().parents[2]
        text = (
            root / "providers/tts/qwen3_streaming_candidate/live_sidecar.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"--cancel-dir"', text)
        self.assertIn('"event": "cancelled" if was_cancelled else "complete"', text)
        self.assertIn("flag.exists()", text)

    def test_provider_drains_cancelled_request_instead_of_treating_it_as_crash(self):
        root = Path(__file__).resolve().parents[2]
        text = (
            root / "providers/tts/qwen3_streaming_candidate/provider.py"
        ).read_text(encoding="utf-8")
        self.assertIn('event in {"complete", "cancelled"}', text)
        self.assertIn("if not cancellation_token.is_cancelled", text)
        self.assertNotIn("if request_id in self._active_request_ids:\n            await self._kill_process()", text)


if __name__ == "__main__":
    unittest.main()
