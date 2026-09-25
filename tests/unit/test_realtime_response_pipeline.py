import unittest
from pathlib import Path

from core.voice import SpeechTextChunker


ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "core" / "voice" / "engine.py"
VOICE_LAB = ROOT / "apps" / "voice_lab.py"
SIDECAR = ROOT / "providers" / "tts" / "chatterbox" / "sidecar.py"


class RealtimeResponsePipelineTests(unittest.TestCase):
    def test_first_phrase_waits_for_complete_sentence_instead_of_mid_clause_cut(self):
        chunker = SpeechTextChunker()
        self.assertEqual(chunker.push("A day on Venus is longer than its"), ())
        self.assertEqual(
            chunker.push(" year."),
            ("A day on Venus is longer than its year.",),
        )

    def test_first_long_comma_clause_can_start_tts_without_mid_word_cut(self):
        chunker = SpeechTextChunker()
        self.assertEqual(
            chunker.push("Venus rotates extremely slowly, likely because the Sun pulls on it"),
            ("Venus rotates extremely slowly.",),
        )

    def test_engine_has_independent_text_synthesis_and_audio_queues(self):
        text = ENGINE.read_text(encoding="utf-8")
        self.assertIn("speech_queue", text)
        self.assertIn("audio_queue", text)
        self.assertIn("jarvis-voice-tts", text)
        self.assertIn("jarvis-voice-playback", text)
        self.assertIn("normalize_speech_text", text)

    def test_latency_telemetry_separates_chunking_synthesis_and_playback(self):
        text = ENGINE.read_text(encoding="utf-8")
        for mark in (
            "speech_first_chunk_ready",
            "tts_first_request_started",
            "tts_first_waveform_ready",
            "audio_first_played",
        ):
            self.assertIn(mark, text)
        lab = VOICE_LAB.read_text(encoding="utf-8")
        self.assertIn("Luna first text -> first speech chunk", lab)
        self.assertIn("TTS request -> first waveform", lab)
        self.assertIn("Speech chunk:", lab)

    def test_chatterbox_generation_uses_inference_mode(self):
        text = SIDECAR.read_text(encoding="utf-8")
        self.assertIn("torch.inference_mode()", text)

    def test_voice_lab_can_measure_warm_multi_turn_provider_latency(self):
        text = VOICE_LAB.read_text(encoding="utf-8")
        self.assertIn("--turns", text)
        self.assertIn("Voice Lab turn", text)
        self.assertIn("remain resident for this session", text)


if __name__ == "__main__":
    unittest.main()
