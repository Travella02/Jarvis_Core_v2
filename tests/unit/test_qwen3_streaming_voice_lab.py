import ast
import unittest
from pathlib import Path

from providers.tts.qwen3_streaming_candidate import Qwen3StreamingConfig, Qwen3StreamingProvider

ROOT = Path(__file__).resolve().parents[2]


class Qwen3StreamingVoiceLabTests(unittest.TestCase):
    def test_provider_is_native_streaming_resident_candidate(self):
        provider = Qwen3StreamingProvider()
        self.assertEqual(provider.metadata.provider, "qwen3-tts-streaming-candidate")
        self.assertTrue(provider.metadata.streaming_output)
        self.assertTrue(provider.metadata.voice_cloning)
        self.assertTrue(provider.metadata.extra["native_streaming"])
        self.assertEqual(provider.metadata.extra["transport"], "resident-binary-sidecar")
        self.assertEqual(provider.metadata.extra["startup_buffer_ms"], 250)
        self.assertEqual(provider.metadata.extra["startup_buffer_strategy"], "single-frame-fast-start")

    def test_config_reuses_isolated_candidate_runtime_and_accepted_model_assets(self):
        cfg = Qwen3StreamingConfig()
        self.assertIn("qwen3_tts_streaming_candidate", str(cfg.python_executable))
        self.assertIn("Qwen3-TTS-12Hz-0.6B-Base", str(cfg.model_dir))
        self.assertEqual(cfg.emit_every_frames, 4)
        self.assertEqual(cfg.decode_window_frames, 80)

    def test_live_sidecar_loads_model_once_and_streams_binary_pcm(self):
        path = ROOT / "providers" / "tts" / "qwen3_streaming_candidate" / "live_sidecar.py"
        text = path.read_text(encoding="utf-8")
        ast.parse(text)
        self.assertEqual(text.count("Qwen3TTSModel.from_pretrained("), 1)
        self.assertIn('attn_implementation="sdpa"', text)
        self.assertIn('op == "prepare_voice"', text)
        self.assertIn('op == "warmup"', text)
        self.assertIn('op == "synthesize"', text)
        self.assertIn("stream_generate_voice_clone", text)
        self.assertIn('astype("<i2"', text)
        self.assertIn("PROTO.write(pcm)", text)

    def test_voice_lab_exposes_streaming_candidate_and_resident_warmup(self):
        text = (ROOT / "apps" / "voice_lab.py").read_text(encoding="utf-8")
        ast.parse(text)
        self.assertIn('"qwen3-streaming"', text)
        self.assertIn("Qwen3StreamingProvider", text)
        self.assertIn('getattr(tts, "warmup", None)', text)
        self.assertIn("TTS resident warmup completed", text)

    def test_voice_engine_uses_provider_neutral_startup_pcm_runway(self):
        text = (ROOT / "core" / "voice" / "engine.py").read_text(encoding="utf-8")
        ast.parse(text)
        self.assertIn('metadata.extra.get("startup_buffer_ms"', text)
        self.assertIn('latency.mark("audio_startup_buffer_ready")', text)
        buffer_block = text[text.index("async def audio_stream"):text.index("async def playback_worker")]
        self.assertNotIn("qwen", buffer_block.lower())


if __name__ == "__main__":
    unittest.main()
