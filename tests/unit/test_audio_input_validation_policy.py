import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VOICE_LAB = ROOT / "apps" / "voice_lab.py"
ENGINE = ROOT / "core" / "voice" / "engine.py"


class AudioInputValidationPolicyTests(unittest.TestCase):
    def test_voice_lab_exposes_listenable_audio_diagnostic(self):
        text = VOICE_LAB.read_text(encoding="utf-8")
        self.assertIn("--audio-diagnostic", text)
        self.assertIn("1_raw_device.wav", text)
        self.assertIn("2_resampled_16k.wav", text)
        self.assertIn("3_whisper_input.wav", text)

    def test_engine_rejects_candidate_before_stt_submission(self):
        text = ENGINE.read_text(encoding="utf-8")
        reject = text.index("if not report.accepted")
        stt = text.index("stream_transcription(accepted_audio()")
        self.assertLess(reject, stt)
        self.assertIn("voice.speech.rejected", text)


if __name__ == "__main__":
    unittest.main()
