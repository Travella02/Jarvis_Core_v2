import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class BargeInArmTests(unittest.TestCase):
    def test_engine_uses_neural_speech_start_then_one_live_stt_stream(self):
        text = (ROOT / "core/voice/engine.py").read_text(encoding="utf-8")
        self.assertIn('name="jarvis-live-stt-turn"', text)
        self.assertIn('"voice.speech.started"', text)
        self.assertIn('"speech_presence_authority": "neural-vad"', text)
        self.assertIn("onset.accept(vad_speech)", text)
        self.assertNotIn("_probe_lexical_text", text)
        self.assertNotIn("SpeechActivityFusion()", text)

    def test_session_interrupts_on_independent_neural_speech_start(self):
        text = (ROOT / "core/voice/conversation_control.py").read_text(encoding="utf-8")
        response = text.index('name="jarvis-response"')
        listener = text.index('name="jarvis-full-duplex-listener"', response)
        speech_waiter = text.index('name="jarvis-interruption-speech-start"', response)
        self.assertLess(response, listener)
        self.assertLess(listener, speech_waiter)
        self.assertIn("neural speech presence during active turn", text)
        self.assertNotIn('name="jarvis-interruption-lexical"', text)

    def test_interrupt_contract_is_phase_independent(self):
        text = (ROOT / "core/voice/engine.py").read_text(encoding="utf-8")
        self.assertIn('self._response_phase = "thinking"', text)
        self.assertIn('self._response_phase = "synthesizing"', text)
        self.assertIn('self._response_phase = "speaking"', text)
        self.assertIn('"phase": self._interruption_phase or "unknown"', text)


if __name__ == "__main__":
    unittest.main()
