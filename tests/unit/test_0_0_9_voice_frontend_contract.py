from __future__ import annotations

import base64
import unittest

from core.voice.frontend import VoiceFrontendEventType, VoiceFrontendSessionConfig
from providers.voice_frontend.openai_live.config import OpenAIGPTLiveConfig
from providers.voice_frontend.openai_live.provider import OpenAIGPTLiveProvider, OpenAIGPTLiveSession


class VoiceFrontendContractTests(unittest.TestCase):
    def test_live_config_defaults_are_provider_specific_and_client_key_stays_optional(self) -> None:
        cfg = OpenAIGPTLiveConfig.from_env({"OPENAI_API_KEY": "test-key"})
        self.assertEqual(cfg.model, "gpt-live-1")
        self.assertEqual(cfg.audio_rate_hz, 24000)
        self.assertTrue(cfg.voice)
        self.assertEqual(cfg.api_key, "test-key")

    def test_provider_metadata_advertises_full_duplex_client_delegation(self) -> None:
        provider = OpenAIGPTLiveProvider(OpenAIGPTLiveConfig(api_key="test"))
        meta = provider.metadata
        self.assertEqual(meta.provider, "openai-gpt-live")
        self.assertTrue(meta.full_duplex)
        self.assertTrue(meta.client_delegation)
        self.assertFalse(meta.local)

    def test_session_payload_keeps_backend_outside_live_provider(self) -> None:
        provider_cfg = OpenAIGPTLiveConfig(api_key="test", voice="meridian", audio_rate_hz=16000)
        session_cfg = VoiceFrontendSessionConfig(
            instructions="Delegate meaningful work to Jarvis Core.",
            voice="meridian",
            sample_rate_hz=16000,
            history=(
                {"role": "user", "content": "Earlier question"},
                {"role": "assistant", "content": "Earlier answer"},
            ),
        )
        session = OpenAIGPTLiveSession(provider_cfg, session_cfg)
        payload = session._session_payload()
        self.assertEqual(payload["model"], "gpt-live-1")
        self.assertEqual(payload["delegation"], {"type": "client"})
        self.assertNotIn("responses", payload["delegation"])
        self.assertEqual(payload["audio"]["format"]["rate"], 16000)
        self.assertEqual(payload["audio"]["output"]["voice"], "meridian")
        self.assertEqual(len(payload["input"]), 2)

    def test_live_events_convert_to_provider_neutral_events(self) -> None:
        event = OpenAIGPTLiveSession._convert_event(
            {
                "type": "session.input_transcript.delta",
                "delta": "hello ",
                "start_ms": 100,
                "end_ms": 350,
            }
        )
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, VoiceFrontendEventType.INPUT_TRANSCRIPT_DELTA)
        self.assertEqual(event.text, "hello ")
        self.assertEqual(event.start_ms, 100)
        self.assertEqual(event.end_ms, 350)

        delegation = OpenAIGPTLiveSession._convert_event(
            {
                "type": "session.delegation.created",
                "offset_ms": 500,
                "delegation": {"id": "item_123", "target": "client"},
            }
        )
        self.assertEqual(delegation.event_type, VoiceFrontendEventType.DELEGATION_REQUESTED)
        self.assertEqual(delegation.delegation_id, "item_123")
        self.assertEqual(delegation.offset_ms, 500)
        self.assertIsNone(
            OpenAIGPTLiveSession._convert_event(
                {
                    "type": "session.delegation.created",
                    "offset_ms": 500,
                    "delegation": {"id": "response_123", "target": "responses"},
                }
            )
        )

        audio_bytes = b"\x01\x02\x03\x04"
        audio = OpenAIGPTLiveSession._convert_event(
            {
                "type": "session.output_audio.delta",
                "delta": base64.b64encode(audio_bytes).decode("ascii"),
            }
        )
        self.assertEqual(audio.event_type, VoiceFrontendEventType.OUTPUT_AUDIO)
        self.assertEqual(audio.audio, audio_bytes)

    def test_gpt_live_lab_imports_and_publishes_exact_five_phrase_acceptance_set(self) -> None:
        from apps.gpt_live_lab import TEST_PHRASES

        self.assertEqual(len(TEST_PHRASES), 5)
        self.assertEqual(TEST_PHRASES[0], "Jarvis, tell me something interesting about space.")
        self.assertEqual(TEST_PHRASES[3], "Tell me another interesting fact.")
        self.assertEqual(TEST_PHRASES[4], "Tell me a short joke.")

    def test_session_config_rejects_unsupported_pcm_rate(self) -> None:
        with self.assertRaises(ValueError):
            VoiceFrontendSessionConfig(
                instructions="x",
                voice="meridian",
                sample_rate_hz=22050,
            )


if __name__ == "__main__":
    unittest.main()
