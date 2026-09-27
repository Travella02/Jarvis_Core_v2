import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

class Repair26PlaybackTelemetryTests(unittest.TestCase):
    def test_engine_marks_write_start_completion_and_audible_estimate(self):
        text = (ROOT / "core/voice/engine.py").read_text(encoding="utf-8")
        self.assertIn('"audio_first_write_started"', text)
        self.assertIn('"audio_first_write_completed"', text)
        self.assertIn("estimated_first_audible_monotonic_ns", text)

    def test_voice_lab_exposes_blocking_write_and_keeps_legacy_end_to_end_label(self):
        text = (ROOT / "apps/voice_lab.py").read_text(encoding="utf-8")
        self.assertIn("first PCM write blocking duration", text)
        self.assertIn("first PCM write -> estimated audible audio", text)
        self.assertIn("speech end -> first audible audio", text)

if __name__ == "__main__":
    unittest.main()
