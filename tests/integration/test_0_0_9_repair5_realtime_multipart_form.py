from __future__ import annotations

import unittest

import httpx

from providers.voice_frontend.openai_realtime import OpenAIRealtimeConfig, create_realtime_webrtc_call


class Repair5RealtimeMultipartFormTests(unittest.IsolatedAsyncioTestCase):
    async def _capture_request(self) -> tuple[bytes, str]:
        observed: dict[str, object] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            observed["body"] = request.content
            observed["content_type"] = request.headers.get("content-type", "")
            return httpx.Response(
                201,
                headers={"Location": "/v1/realtime/calls/rtc_repair5"},
                text="v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n",
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await create_realtime_webrtc_call(
                OpenAIRealtimeConfig(api_key="secret-test", webrtc_url="https://test.invalid/v1/realtime/calls"),
                "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n",
                client=client,
            )

        return observed["body"], str(observed["content_type"])

    async def test_sdp_is_an_ordinary_multipart_text_field_not_a_file_upload(self) -> None:
        body, content_type = await self._capture_request()
        self.assertIn("multipart/form-data", content_type)
        self.assertIn(b'name="sdp"', body)
        self.assertIn(b'v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n', body)
        sdp_header = body.split(b'name="sdp"', 1)[1].split(b"\r\n\r\n", 1)[0]
        self.assertNotIn(b"filename=", sdp_header)

    async def test_session_is_an_ordinary_multipart_text_field(self) -> None:
        body, _ = await self._capture_request()
        self.assertIn(b'name="session"', body)
        session_header = body.split(b'name="session"', 1)[1].split(b"\r\n\r\n", 1)[0]
        self.assertNotIn(b"filename=", session_header)
        self.assertIn(b'"type":"realtime"', body)
        self.assertIn(b'"model":"gpt-realtime-2.1-mini"', body)


if __name__ == "__main__":
    unittest.main()
