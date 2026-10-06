from __future__ import annotations

import json
import unittest

import httpx

from core.voice.frontend import VoiceFrontendSessionConfig
from providers.voice_frontend.openai_live.config import OpenAIGPTLiveConfig
from providers.voice_frontend.openai_live.webrtc import create_webrtc_session


class Repair2WebRTCSessionCreationTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_session_posts_sdp_without_raw_pcm_format(self) -> None:
        observed: dict[str, object] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            observed["authorization"] = request.headers.get("authorization")
            body = json.loads(request.content.decode("utf-8"))
            observed["body"] = body
            return httpx.Response(
                201,
                json={
                    "session": {"id": "live_webrtc_test"},
                    "transport": {"type": "webrtc", "sdp": "v=0\r\nanswer\r\n"},
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            session_id, answer = await create_webrtc_session(
                OpenAIGPTLiveConfig(api_key="secret-test", webrtc_url="https://test.invalid/live"),
                VoiceFrontendSessionConfig(
                    instructions="Delegate to Jarvis Core.",
                    voice="meridian",
                    sample_rate_hz=24000,
                ),
                "v=0\r\noffer\r\n",
                client=client,
            )

        self.assertEqual(session_id, "live_webrtc_test")
        self.assertEqual(answer, "v=0\r\nanswer\r\n")
        self.assertEqual(observed["authorization"], "Bearer secret-test")
        body = observed["body"]
        self.assertEqual(body["transport"], {"type": "webrtc", "sdp": "v=0\r\noffer\r\n"})
        self.assertEqual(body["session"]["audio"], {"output": {"voice": "meridian"}})
        self.assertNotIn("format", body["session"]["audio"])
        self.assertEqual(body["session"]["delegation"], {"type": "client"})

    async def test_create_session_rejects_malformed_provider_response(self) -> None:
        async def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(201, json={"session": {"id": "live_missing_answer"}, "transport": {"type": "webrtc"}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(RuntimeError):
                await create_webrtc_session(
                    OpenAIGPTLiveConfig(api_key="test"),
                    VoiceFrontendSessionConfig(instructions="x", voice="meridian", sample_rate_hz=24000),
                    "v=0\r\noffer\r\n",
                    client=client,
                )


if __name__ == "__main__":
    unittest.main()
