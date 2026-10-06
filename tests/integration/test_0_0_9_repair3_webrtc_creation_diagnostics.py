from __future__ import annotations

import json
import unittest

import httpx

from core.voice.frontend import VoiceFrontendSessionConfig
from providers.voice_frontend.openai_live.config import OpenAIGPTLiveConfig
from providers.voice_frontend.openai_live.webrtc import (
    GPTLiveWebRTCSessionCreationError,
    create_webrtc_session,
)


class Repair3WebRTCCreationDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_openai_rejection_preserves_safe_body_and_request_id(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode("utf-8"))
            self.assertTrue(body["transport"]["sdp"].endswith("\r\n"))
            return httpx.Response(
                400,
                headers={"x-request-id": "req_webrtc_test"},
                json={"error": {"message": "Invalid SDP framing", "type": "invalid_request_error"}},
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(GPTLiveWebRTCSessionCreationError) as caught:
                await create_webrtc_session(
                    OpenAIGPTLiveConfig(api_key="secret-test", webrtc_url="https://test.invalid/live"),
                    VoiceFrontendSessionConfig(instructions="x", voice="meridian", sample_rate_hz=24000),
                    "v=0\no=- 1 2 IN IP4 127.0.0.1\nm=audio 9 UDP/TLS/RTP/SAVPF 111\n",
                    client=client,
                )

        message = str(caught.exception)
        self.assertIn("400", message)
        self.assertIn("Invalid SDP framing", message)
        self.assertIn("req_webrtc_test", message)
        self.assertNotIn("secret-test", message)
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(caught.exception.request_id, "req_webrtc_test")

    async def test_success_answer_is_canonicalized_before_browser_receives_it(self) -> None:
        async def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                201,
                json={
                    "session": {"id": "live_repair3"},
                    "transport": {"type": "webrtc", "sdp": "v=0\no=- 9 9 IN IP4 127.0.0.1\n"},
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            session_id, answer = await create_webrtc_session(
                OpenAIGPTLiveConfig(api_key="test"),
                VoiceFrontendSessionConfig(instructions="x", voice="meridian", sample_rate_hz=24000),
                "v=0\no=- 1 2 IN IP4 127.0.0.1\nm=audio 9 UDP/TLS/RTP/SAVPF 111\n",
                client=client,
            )

        self.assertEqual(session_id, "live_repair3")
        self.assertEqual(answer, "v=0\r\no=- 9 9 IN IP4 127.0.0.1\r\n")


if __name__ == "__main__":
    unittest.main()
