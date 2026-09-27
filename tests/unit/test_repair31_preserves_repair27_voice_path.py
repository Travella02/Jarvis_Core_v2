import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Repair31PreservesRepair27VoicePathTests(unittest.TestCase):
    def test_sidecar_does_not_override_sampling_parameters(self):
        text = (
            ROOT / "providers/tts/qwen3_streaming_candidate/live_sidecar.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("temperature=", text)
        self.assertNotIn("top_k=", text)
        self.assertNotIn("top_p=", text)
        self.assertNotIn("do_sample=", text)

    def test_each_speech_chunk_is_still_queued_separately(self):
        text = (ROOT / "core/voice/engine.py").read_text(encoding="utf-8")
        self.assertIn("await speech_queue.put((trace, spoken))", text)
        self.assertNotIn("merged_for_continuity", text)

    def test_voice_lab_exposes_seed_ab_and_imports_config(self):
        text = (ROOT / "apps/voice_lab.py").read_text(encoding="utf-8")
        self.assertIn("Qwen3StreamingConfig, Qwen3StreamingProvider", text)
        self.assertIn('"--qwen-fixed-seed"', text)
        self.assertIn("Qwen streaming RNG:", text)


if __name__ == "__main__":
    unittest.main()
