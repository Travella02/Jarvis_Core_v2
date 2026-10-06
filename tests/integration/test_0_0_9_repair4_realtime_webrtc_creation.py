from __future__ import annotations

import unittest

import httpx

from providers.voice_frontend.openai_realtime import (
    OpenAIRealtimeConfig,
    create_realtime_webrtc_call,
    hangup_realtime_call,
)


class Repair4RealtimeWebRTCCreationTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_call_posts_multipart_sdp_and_session(self) -> None:
        observed: dict[str, object] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            observed["authorization"] = request.headers.get("authorization")
            observed["content_type"] = request.headers.get("content-type")
            observed["body"] = request.content
            return httpx.Response(
                201,
                headers={"Location": "/v1/realtime/calls/rtc_test_123", "x-request-id": "req_test"},
                text="v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n",
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            call_id, answer = await create_realtime_webrtc_call(
                OpenAIRealtimeConfig(api_key="secret-test", webrtc_url="https://test.invalid/v1/realtime/calls"),
                "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n",
                client=client,
            )

        self.assertEqual(call_id, "rtc_test_123")
        self.assertTrue(answer.endswith("\r\n"))
        self.assertEqual(observed["authorization"], "Bearer secret-test")
        self.assertIn("multipart/form-data", str(observed["content_type"]))
        body = observed["body"]
        self.assertIn(b'name="sdp"', body)
        self.assertIn(b'name="session"', body)
        self.assertIn(b'gpt-realtime-2.1', body)
        self.assertIn(b'delegate_to_jarvis_core', body)
        self.assertNotIn(b'OPENAI_API_KEY', body)

    async def test_hangup_uses_authoritative_server_endpoint(self) -> None:
        paths: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            paths.append(request.url.path)
            return httpx.Response(200)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            ok = await hangup_realtime_call(
                OpenAIRealtimeConfig(api_key="test", webrtc_url="https://api.test/v1/realtime/calls"),
                "rtc_abc",
                client=client,
            )
        self.assertTrue(ok)
        self.assertEqual(paths, ["/v1/realtime/calls/rtc_abc/hangup"])


if __name__ == "__main__":
    unittest.main()
