from __future__ import annotations

import asyncio
import base64
import json
import unittest

import websockets

from core.voice.frontend import VoiceFrontendEventType, VoiceFrontendSessionConfig
from providers.voice_frontend.openai_live import OpenAIGPTLiveConfig, OpenAIGPTLiveProvider


class OpenAIGPTLiveTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_websocket_transport_uses_live_session_contract_and_graceful_close(self) -> None:
        received: list[dict] = []

        async def handler(socket) -> None:
            start = json.loads(await socket.recv())
            received.append(start)
            self.assertEqual(start["type"], "session.start")
            self.assertEqual(start["session"]["delegation"], {"type": "client"})
            self.assertEqual(start["session"]["audio"]["format"], {"type": "audio/pcm", "rate": 24000})
            await socket.send(
                json.dumps(
                    {
                        "type": "session.started",
                        "event_id": "server-started",
                        "session": {"id": "live_test_session"},
                    }
                )
            )

            while True:
                message = json.loads(await socket.recv())
                received.append(message)
                if message["type"] == "session.input_audio.append":
                    self.assertEqual(base64.b64decode(message["audio"]), b"\x01\x02\x03\x04")
                    await socket.send(
                        json.dumps(
                            {
                                "type": "session.input_transcript.delta",
                                "delta": "Hello Jarvis",
                                "start_ms": 100,
                                "end_ms": 400,
                            }
                        )
                    )
                    await socket.send(
                        json.dumps(
                            {
                                "type": "session.delegation.created",
                                "offset_ms": 420,
                                "delegation": {
                                    "id": "delegation_1",
                                    "type": "delegation",
                                    "target": "client",
                                },
                            }
                        )
                    )
                    await socket.send(
                        json.dumps(
                            {
                                "type": "session.output_audio.delta",
                                "delta": base64.b64encode(b"\x05\x06").decode("ascii"),
                            }
                        )
                    )
                    await socket.send(
                        json.dumps(
                            {
                                "type": "session.usage.updated",
                                "usage": {"seconds": 1.25},
                            }
                        )
                    )
                elif message["type"] == "session.commentary.append":
                    self.assertEqual(message["delegation_id"], "delegation_1")
                    self.assertEqual(message["content"], "Verified backend result")
                elif message["type"] == "session.close":
                    await socket.send(
                        json.dumps(
                            {
                                "type": "session.closed",
                                "reason": "close_requested",
                                "usage": {"seconds": 1.5},
                                "session": {"id": "live_test_session"},
                            }
                        )
                    )
                    return

        server = await websockets.serve(handler, "127.0.0.1", 0)
        try:
            port = server.sockets[0].getsockname()[1]
            provider = OpenAIGPTLiveProvider(
                OpenAIGPTLiveConfig(
                    api_key="test-key",
                    url=f"ws://127.0.0.1:{port}",
                    audio_rate_hz=24000,
                    open_timeout_seconds=2,
                    close_timeout_seconds=2,
                )
            )
            session = await provider.open_session(
                VoiceFrontendSessionConfig(
                    instructions="Delegate meaningful work to Jarvis Core.",
                    voice="meridian",
                    sample_rate_hz=24000,
                )
            )
            self.assertEqual(session.session_id, "live_test_session")
            await session.send_audio(b"\x01\x02\x03\x04")

            iterator = session.events().__aiter__()
            events = []
            while len(events) < 5:
                events.append(await asyncio.wait_for(anext(iterator), timeout=2))

            types = [item.event_type for item in events]
            self.assertIn(VoiceFrontendEventType.SESSION_STARTED, types)
            self.assertIn(VoiceFrontendEventType.INPUT_TRANSCRIPT_DELTA, types)
            self.assertIn(VoiceFrontendEventType.DELEGATION_REQUESTED, types)
            self.assertIn(VoiceFrontendEventType.OUTPUT_AUDIO, types)
            self.assertIn(VoiceFrontendEventType.USAGE_UPDATED, types)

            await session.send_commentary("delegation_1", "Verified backend result")
            await session.close()

            closed = await asyncio.wait_for(anext(iterator), timeout=2)
            self.assertEqual(closed.event_type, VoiceFrontendEventType.SESSION_CLOSED)
            self.assertEqual(closed.usage_seconds, 1.5)
            self.assertTrue(any(item["type"] == "session.commentary.append" for item in received))
            self.assertTrue(any(item["type"] == "session.close" for item in received))
        finally:
            server.close()
            await server.wait_closed()


if __name__ == "__main__":
    unittest.main()
