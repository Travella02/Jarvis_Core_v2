from __future__ import annotations

import unittest
from pathlib import Path

from core.voice.frontend import VoiceFrontendSessionConfig
from providers.voice_frontend.openai_live.config import OpenAIGPTLiveConfig
from providers.voice_frontend.openai_live.webrtc import build_webrtc_create_payload, normalize_sdp


class Repair3WebRTCSDPFramingTests(unittest.TestCase):
    def test_offer_is_canonicalized_to_crlf_with_terminal_crlf(self) -> None:
        provider = OpenAIGPTLiveConfig(api_key="test")
        session = VoiceFrontendSessionConfig(instructions="x", voice="meridian", sample_rate_hz=24000)
        payload = build_webrtc_create_payload(
            provider,
            session,
            "\ufeff\nv=0\no=- 1 2 IN IP4 127.0.0.1\nm=audio 9 UDP/TLS/RTP/SAVPF 111\n",
        )
        self.assertEqual(
            payload["transport"]["sdp"],
            "v=0\r\no=- 1 2 IN IP4 127.0.0.1\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n",
        )

    def test_normalizer_rejects_internal_blank_lines_and_control_bytes(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty SDP line"):
            normalize_sdp("v=0\n\nm=audio 9 UDP/TLS/RTP/SAVPF 111\n", label="offer")
        with self.assertRaisesRegex(ValueError, "null byte"):
            normalize_sdp("v=0\nfoo=bad\x00value\n", label="offer")

    def test_browser_waits_for_complete_ice_instead_of_sending_partial_offer(self) -> None:
        html = (Path(__file__).resolve().parents[2] / "apps" / "web" / "gpt_live_webrtc_lab.html").read_text(encoding="utf-8")
        self.assertIn("ICE gathering did not complete", html)
        self.assertIn("ICE gathering complete.", html)
        self.assertNotIn("setTimeout(resolve, 2500)", html)


if __name__ == "__main__":
    unittest.main()
