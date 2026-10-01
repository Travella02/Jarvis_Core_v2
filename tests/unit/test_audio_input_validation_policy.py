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

    def test_engine_uses_neural_presence_instead_of_energy_or_transcript_self_authority(self):
        text = ENGINE.read_text(encoding="utf-8")
        self.assertIn("onset.accept(vad_speech)", text)
        self.assertIn("jarvis-live-stt-turn", text)
        self.assertIn("speech_presence_authority", text)
        self.assertNotIn("SpeechActivityFusion()", text)
        self.assertNotIn("transcript.confirms_final", text)
        self.assertNotIn('reason == "insufficient-energy"', text)
        self.assertNotIn('reason == "peak-below-threshold"', text)


if __name__ == "__main__":
    unittest.main()
