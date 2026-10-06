from __future__ import annotations

import asyncio
import unittest

from core.voice.live_bridge import LiveTranscriptBuffer


class LiveTranscriptBufferTests(unittest.IsolatedAsyncioTestCase):
    async def test_delegation_consumes_ordered_fragments_once(self) -> None:
        buffer = LiveTranscriptBuffer()
        await buffer.append("Tell me ", 100, 250)
        await buffer.append("a joke.", 250, 500)
        text = await buffer.consume_for_delegation(520, timeout_s=0)
        self.assertEqual(text, "Tell me a joke.")
        self.assertEqual(await buffer.consume_for_delegation(520, timeout_s=0), "")

    async def test_late_transcript_can_arrive_while_delegation_waits(self) -> None:
        buffer = LiveTranscriptBuffer()
        await buffer.append("Explain ", 100, 200)

        async def later() -> None:
            await asyncio.sleep(0.01)
            await buffer.append("that.", 200, 480)

        task = asyncio.create_task(later())
        text = await buffer.consume_for_delegation(500, transcript_catchup_ms=20, timeout_s=0.2)
        await task
        self.assertEqual(text, "Explain that.")


if __name__ == "__main__":
    unittest.main()
