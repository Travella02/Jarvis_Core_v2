import unittest

from core.common.ids import CorrelationContext
from core.voice import (
    AudioFormat,
    AudioFrame,
    EndpointConfig,
    EndpointDetector,
    SpeechEvidenceGate,
)


FMT = AudioFormat(16000)
TRACE = CorrelationContext.create()


def frame(seq: int, amplitude: int) -> AudioFrame:
    samples = int(FMT.sample_rate_hz * 0.03)
    payload = int(amplitude).to_bytes(2, "little", signed=True) * samples
    return AudioFrame(TRACE, seq, FMT, payload)


class SpeechEvidenceTests(unittest.TestCase):
    def _candidate(self, amplitudes, flags):
        config = EndpointConfig(frame_ms=30, start_trigger_ms=60, end_silence_ms=90, preroll_ms=90)
        endpoint = EndpointDetector(config)
        gate = SpeechEvidenceGate(frame_ms=30, preroll_frames=3)
        result = None
        for seq, (amplitude, flag) in enumerate(zip(amplitudes, flags)):
            signal = endpoint.accept(flag)
            candidate = gate.push(frame(seq, amplitude), flag, signal)
            if candidate is not None:
                result = candidate
                break
        self.assertIsNotNone(result)
        return result

    def test_short_false_vad_trigger_is_rejected_before_stt(self):
        # Quiet pre-roll, two false VAD frames, then endpointing silence.
        result = self._candidate(
            [200, 180, 220, 500, 550, 180, 160, 150],
            [False, False, False, True, True, False, False, False],
        )
        self.assertFalse(result.report.accepted)
        self.assertEqual(result.report.reason, "speech-span-too-short")

    def test_normal_high_energy_speech_is_accepted(self):
        result = self._candidate(
            [300, 250, 300] + [8000] * 12 + [250, 220, 200],
            [False, False, False] + [True] * 12 + [False, False, False],
        )
        self.assertTrue(result.report.accepted, result.report)
        self.assertGreaterEqual(result.report.vad_speech_ms, 300)
        self.assertGreater(result.report.peak_rms, 0.2)

    def test_strong_energy_evidence_accepts_vad_blind_candidate(self):
        from core.voice.endpointing import EndpointSignal

        gate = SpeechEvidenceGate(frame_ms=30, preroll_frames=3)
        result = None
        amplitudes = [200, 180, 220] + [12000] * 12 + [200, 180, 160, 150, 140, 130]
        for seq, amplitude in enumerate(amplitudes):
            if seq == 5:
                signal = EndpointSignal.SPEECH_STARTED
            elif seq == len(amplitudes) - 1:
                signal = EndpointSignal.SPEECH_ENDED
            else:
                signal = EndpointSignal.NONE
            candidate = gate.push(frame(seq, amplitude), False, signal)
            if candidate is not None:
                result = candidate
        self.assertIsNotNone(result)
        self.assertTrue(result.report.accepted, result.report)
        self.assertEqual(result.report.vad_speech_ms, 0)
        self.assertGreater(result.report.peak_rms, 0.3)

    def test_quiet_vad_speech_is_not_rejected_by_energy_or_peak(self):
        result = self._candidate(
            [100, 120, 110] + [650] * 8 + [100, 120, 110],
            [False, False, False] + [True] * 8 + [False, False, False],
        )
        self.assertTrue(result.report.accepted, result.report)
        self.assertEqual(result.report.reason, "accepted-for-stt")
        self.assertLess(result.report.peak_rms, 0.03)


if __name__ == "__main__":
    unittest.main()
