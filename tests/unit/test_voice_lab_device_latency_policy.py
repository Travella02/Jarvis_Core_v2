import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VOICE_LAB = ROOT / "apps" / "voice_lab.py"


class VoiceLabDeviceLatencyPolicyTests(unittest.TestCase):
    def test_voice_lab_has_explicit_mic_test_and_device_persistence(self):
        text = VOICE_LAB.read_text(encoding="utf-8")
        self.assertIn('"--mic-test"', text)
        self.assertIn('"--save-devices"', text)
        self.assertIn('audio_devices.json', text)
        self.assertIn('native=', text)
        self.assertIn('-> Jarvis=16000 Hz', text)


    def test_voice_lab_has_tts_waveform_diagnostic_mode(self):
        text = VOICE_LAB.read_text(encoding="utf-8")
        self.assertIn('"--tts-diagnostic"', text)
        self.assertIn('Saved exact provider output:', text)
        self.assertIn('Listen to this WAV before testing speaker playback.', text)

    def test_voice_lab_preloads_local_providers_before_listening(self):
        tree = ast.parse(VOICE_LAB.read_text(encoding="utf-8"))
        run_session = next(
            node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "run_session"
        )
        source = ast.get_source_segment(VOICE_LAB.read_text(encoding="utf-8"), run_session) or ""
        self.assertLess(source.find("_prewarm_voice"), source.find('print("Listening...'))
        self.assertIn("speech end -> first audible audio", VOICE_LAB.read_text(encoding="utf-8"))

    def test_voice_lab_runs_real_hidden_tts_and_luna_warmups_before_listening(self):
        text = VOICE_LAB.read_text(encoding="utf-8")
        self.assertIn('tts.stream_speech(warm_trace, "Ready."', text)
        self.assertIn('warmup completed', text)
        self.assertIn('TTS inference warmup completed', text)
        self.assertIn('STT inference warmup completed', text)
        self.assertIn('--luna-transport', text)
        self.assertIn('IntelligenceEventType.TEXT_DELTA', text)


if __name__ == "__main__":
    unittest.main()
