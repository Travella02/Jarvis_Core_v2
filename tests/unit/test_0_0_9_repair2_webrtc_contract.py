from __future__ import annotations

import asyncio
import unittest
from pathlib import Path

from core.voice.frontend import VoiceFrontendEventType, VoiceFrontendSessionConfig
from providers.voice_frontend.openai_live.config import OpenAIGPTLiveConfig
from providers.voice_frontend.openai_live.webrtc import (
    BrowserWebRTCRelaySession,
    build_webrtc_create_payload,
)


class Repair2WebRTCContractTests(unittest.TestCase):
    def test_webrtc_payload_uses_media_negotiation_and_client_delegation(self) -> None:
        provider = OpenAIGPTLiveConfig(api_key="test", model="gpt-live-1", voice="meridian")
        session = VoiceFrontendSessionConfig(
            instructions="Delegate meaningful work to Jarvis Core.",
            voice="meridian",
            sample_rate_hz=24000,
            history=(
                {"role": "user", "content": "Earlier question"},
                {"role": "assistant", "content": "Earlier answer"},
            ),
        )
        payload = build_webrtc_create_payload(provider, session, "v=0\r\n...\r\n")
        self.assertEqual(payload["transport"]["type"], "webrtc")
        self.assertEqual(payload["transport"]["sdp"], "v=0\r\n...\r\n")
        self.assertEqual(payload["session"]["delegation"], {"type": "client"})
        self.assertEqual(payload["session"]["audio"], {"output": {"voice": "meridian"}})
        self.assertNotIn("format", payload["session"]["audio"])
        self.assertEqual(len(payload["session"]["input"]), 2)

    def test_webrtc_payload_rejects_empty_offer(self) -> None:
        provider = OpenAIGPTLiveConfig(api_key="test")
        session = VoiceFrontendSessionConfig(instructions="x", voice="meridian", sample_rate_hz=24000)
        with self.assertRaises(ValueError):
            build_webrtc_create_payload(provider, session, "  ")

    def test_config_exposes_separate_webrtc_endpoint(self) -> None:
        cfg = OpenAIGPTLiveConfig.from_env(
            {
                "OPENAI_API_KEY": "test",
                "JARVIS_GPT_LIVE_WEBRTC_URL": "https://example.invalid/live",
            }
        )
        self.assertEqual(cfg.webrtc_url, "https://example.invalid/live")
        self.assertTrue(cfg.url.startswith("wss://"))

    def test_browser_media_page_uses_webrtc_without_embedding_project_key(self) -> None:
        html = (Path(__file__).resolve().parents[2] / "apps" / "web" / "gpt_live_webrtc_lab.html").read_text(encoding="utf-8")
        self.assertIn("RTCPeerConnection", html)
        self.assertIn("getUserMedia", html)
        self.assertNotIn("OPENAI_API_KEY", html)
        self.assertNotIn("session.input_audio.append", html)


class BrowserRelayAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_relay_normalizes_events_and_returns_backend_commentary(self) -> None:
        relay = BrowserWebRTCRelaySession()
        relay.set_session_id("live_browser_test")
        self.assertEqual(relay.session_id, "live_browser_test")

        await relay.feed_live_event(
            {
                "type": "session.input_transcript.delta",
                "delta": "Hello Jarvis",
                "start_ms": 100,
                "end_ms": 400,
            }
        )
        await relay.feed_live_event(
            {
                "type": "session.delegation.created",
                "offset_ms": 420,
                "delegation": {"id": "delegation_1", "target": "client"},
            }
        )

        iterator = relay.events().__aiter__()
        transcript = await asyncio.wait_for(anext(iterator), timeout=1)
        delegation = await asyncio.wait_for(anext(iterator), timeout=1)
        self.assertEqual(transcript.event_type, VoiceFrontendEventType.INPUT_TRANSCRIPT_DELTA)
        self.assertEqual(delegation.event_type, VoiceFrontendEventType.DELEGATION_REQUESTED)
        self.assertEqual(delegation.delegation_id, "delegation_1")

        await relay.send_commentary("delegation_1", "Verified backend result")
        outgoing = relay.outgoing().__aiter__()
        message = await asyncio.wait_for(anext(outgoing), timeout=1)
        self.assertEqual(message["kind"], "live_send")
        self.assertEqual(message["event"]["type"], "session.commentary.append")
        self.assertEqual(message["event"]["delegation_id"], "delegation_1")
        self.assertEqual(message["event"]["content"], "Verified backend result")
        await relay.close()

    async def test_browser_relay_refuses_pcm_injection(self) -> None:
        relay = BrowserWebRTCRelaySession()
        with self.assertRaises(RuntimeError):
            await relay.send_audio(b"\x00\x00")
        await relay.close()


if __name__ == "__main__":
    unittest.main()
