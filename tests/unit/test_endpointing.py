import unittest

from core.common.ids import CorrelationContext
from core.voice import AudioFormat, AudioFrame, EndpointConfig, EndpointDetector, EndpointSignal, UtteranceBuffer


def frame(seq: int) -> AudioFrame:
    return AudioFrame(CorrelationContext("corr", "req"), seq, AudioFormat(16000), b"\x00\x00" * 480)


class EndpointingTests(unittest.TestCase):
    def test_start_and_end_are_orvex_owned(self):
        detector = EndpointDetector(EndpointConfig(start_trigger_ms=60, end_silence_ms=90))
        signals = [detector.accept(value) for value in [False, True, True, True, False, False, False]]
        self.assertIn(EndpointSignal.SPEECH_STARTED, signals)
        self.assertEqual(signals[-1], EndpointSignal.SPEECH_ENDED)

    def test_waiting_silence_does_not_consume_max_utterance_budget(self):
        detector = EndpointDetector(
            EndpointConfig(start_trigger_ms=30, end_silence_ms=300, max_utterance_ms=90)
        )
        for _ in range(20):
            self.assertEqual(detector.accept(False), EndpointSignal.NONE)
        self.assertEqual(detector.accept(True), EndpointSignal.SPEECH_STARTED)
        self.assertEqual(detector.accept(True), EndpointSignal.NONE)
        self.assertEqual(detector.accept(True), EndpointSignal.MAX_DURATION)

    def test_utterance_buffer_includes_preroll(self):
        config = EndpointConfig(frame_ms=30, start_trigger_ms=30, end_silence_ms=30, preroll_ms=60)
        buffer = UtteranceBuffer(config)
        self.assertIsNone(buffer.push(frame(0), EndpointSignal.NONE))
        self.assertIsNone(buffer.push(frame(1), EndpointSignal.SPEECH_STARTED))
        result = buffer.push(frame(2), EndpointSignal.SPEECH_ENDED)
        self.assertEqual([item.sequence for item in result], [0, 1, 2])
