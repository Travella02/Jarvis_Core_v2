import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Qwen3StreamingResidentBenchmarkTests(unittest.TestCase):
    def test_resident_worker_loads_model_once_and_runs_warmup_then_multiple_requests(self):
        path = ROOT / "providers" / "tts" / "qwen3_streaming_candidate" / "resident_benchmark.py"
        text = path.read_text(encoding="utf-8")
        ast.parse(text)
        self.assertEqual(text.count("Qwen3TTSModel.from_pretrained("), 1)
        self.assertIn('attn_implementation="sdpa"', text)
        self.assertIn("WARMUP_BEGIN", text)
        self.assertIn("RESIDENT_RUN_BEGIN", text)
        self.assertIn("RESIDENT_BENCHMARK_SUMMARY", text)
        self.assertIn("for run_index in range(1, args.runs + 1)", text)
        self.assertIn("torch.cuda.synchronize", text)

    def test_benchmark_reuses_same_text_for_warmup_to_measure_true_hot_path(self):
        text = (ROOT / "providers" / "tts" / "qwen3_streaming_candidate" / "resident_benchmark.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("text=args.text"), 2)
        self.assertIn("same resident process", text)

    def test_app_uses_existing_candidate_runtime_model_and_voice_library(self):
        path = ROOT / "apps" / "qwen_streaming_resident_benchmark.py"
        text = path.read_text(encoding="utf-8")
        ast.parse(text)
        self.assertIn("VoiceReferenceLibrary", text)
        self.assertIn("qwen3_tts_streaming_candidate", text)
        self.assertIn("Qwen3-TTS-12Hz-0.6B-Base", text)
        self.assertIn("accepted Repair20 provider is untouched", text)
        self.assertIn("--runs", text)


if __name__ == "__main__":
    unittest.main()
