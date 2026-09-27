import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class Qwen3StreamingCandidateTests(unittest.TestCase):
    def test_candidate_is_isolated_from_accepted_qwen_runtime(self):
        setup = (ROOT / "scripts" / "setup_qwen3_tts_streaming_candidate.ps1").read_text(encoding="utf-8")
        self.assertIn("qwen3_tts_streaming_candidate", setup)
        self.assertIn("Qwen3-TTS-streaming.git", setup)
        self.assertIn("py -3.12", setup)
        self.assertIn("cu130", setup)
        self.assertIn("flash_attn", setup)
        self.assertNotIn("qwen3_tts\\.venv", setup)

    def test_worker_uses_true_streaming_voice_clone_api(self):
        worker = (ROOT / "providers" / "tts" / "qwen3_streaming_candidate" / "worker.py").read_text(encoding="utf-8")
        self.assertIn("stream_generate_voice_clone", worker)
        self.assertIn("emit_every_frames", worker)
        self.assertIn("enable_streaming_optimizations", worker)
        self.assertIn("stream.write", worker)
        self.assertIn("STREAMING_CANDIDATE_SUMMARY", worker)
        self.assertIn("x_vector_only_mode=True", worker)

    def test_candidate_reuses_existing_model_and_voice_library(self):
        app = (ROOT / "apps" / "qwen_streaming_candidate.py").read_text(encoding="utf-8")
        self.assertIn("Qwen3-TTS-12Hz-0.6B-Base", app)
        self.assertIn("VoiceReferenceLibrary", app)
        self.assertIn("--voice-profile", app)
        self.assertIn("accepted Repair20 provider is untouched", app)

if __name__ == "__main__":
    unittest.main()
