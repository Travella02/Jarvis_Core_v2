import os
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.stt.whisper_cpp import WhisperCppConfig, WhisperCppProvider
from providers.tts.chatterbox import ChatterboxConfig, ChatterboxTurboProvider
from providers.tts.qwen3 import Qwen3TTSConfig, Qwen3TTSProvider


class VoiceProviderConfigTests(unittest.TestCase):
    def test_whisper_candidate_is_large_v3_turbo_q5(self):
        provider = WhisperCppProvider(
            WhisperCppConfig(
                server_executable=Path("server"),
                model_path=Path("ggml-large-v3-turbo-q5_0.bin"),
            )
        )
        self.assertEqual(provider.metadata.provider, "whisper.cpp")
        self.assertEqual(provider.metadata.model, "large-v3-turbo-q5_0")
        self.assertTrue(provider.metadata.local)

    def test_chatterbox_candidate_is_local_clone_capable_sidecar(self):
        provider = ChatterboxTurboProvider(ChatterboxConfig(Path("python")))
        self.assertEqual(provider.metadata.provider, "chatterbox")
        self.assertTrue(provider.metadata.local)
        self.assertTrue(provider.metadata.voice_cloning)
        self.assertEqual(provider.metadata.extra["transport"], "isolated-sidecar")



    def test_qwen_candidate_is_local_clone_capable_sidecar(self):
        provider = Qwen3TTSProvider(Qwen3TTSConfig(Path("python")))
        self.assertEqual(provider.metadata.provider, "qwen3-tts")
        self.assertEqual(provider.metadata.model, "12hz-0.6b-base")
        self.assertTrue(provider.metadata.local)
        self.assertTrue(provider.metadata.voice_cloning)
        self.assertEqual(provider.metadata.extra["license"], "Apache-2.0")

    def test_voice_configs_can_read_project_env_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("JARVIS_WHISPER_LANGUAGE=fr\nJARVIS_CHATTERBOX_DEVICE=cpu\nJARVIS_CHATTERBOX_MODEL_DIR=.runtime/custom-tts-model\nJARVIS_QWEN3_TTS_DEVICE=cpu\nJARVIS_QWEN3_TTS_MODEL_DIR=.runtime/qwen-model\n", encoding="utf-8")
            self.assertEqual(WhisperCppConfig.from_env(env={}, env_file=env_file).language, "fr")
            cfg = ChatterboxConfig.from_env(env={}, env_file=env_file)
            self.assertEqual(cfg.device, "cpu")
            self.assertTrue(str(cfg.model_dir).endswith(str(Path(".runtime/custom-tts-model"))))
            qwen = Qwen3TTSConfig.from_env(env={}, env_file=env_file)
            self.assertEqual(qwen.device, "cpu")
            self.assertTrue(str(qwen.model_dir).endswith(str(Path(".runtime/qwen-model"))))

    def test_env_overrides_stay_inside_adapters(self):
        with patch.dict(os.environ, {"JARVIS_WHISPER_LANGUAGE": "es", "JARVIS_CHATTERBOX_DEVICE": "cpu", "JARVIS_QWEN3_TTS_DEVICE": "cpu"}):
            self.assertEqual(WhisperCppConfig.from_env().language, "es")
            self.assertEqual(ChatterboxConfig.from_env().device, "cpu")
            self.assertEqual(Qwen3TTSConfig.from_env().device, "cpu")
