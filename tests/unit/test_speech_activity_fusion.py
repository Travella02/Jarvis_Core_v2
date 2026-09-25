import unittest

from core.common.ids import CorrelationContext
from core.voice import AudioFormat, AudioFrame, SpeechActivityFusion

FMT = AudioFormat(16000)
TRACE = CorrelationContext.create()


def frame(seq: int, amplitude: int) -> AudioFrame:
    samples = int(FMT.sample_rate_hz * 0.03)
    payload = int(amplitude).to_bytes(2, "little", signed=True) * samples
    return AudioFrame(TRACE, seq, FMT, payload)


class SpeechActivityFusionTests(unittest.TestCase):
    def test_vad_positive_remains_active(self):
        fusion = SpeechActivityFusion()
        decision = fusion.classify(frame(0, 200), vad_speech=True)
        self.assertTrue(decision.active)
        self.assertFalse(decision.acoustic_rescue)

    def test_quiet_noise_does_not_rescue_vad(self):
        fusion = SpeechActivityFusion()
        decisions = [fusion.classify(frame(i, 500), vad_speech=False) for i in range(12)]
        self.assertTrue(all(not item.active for item in decisions))

    def test_strong_speech_rescues_blind_vad(self):
        fusion = SpeechActivityFusion()
        for i in range(6):
            fusion.classify(frame(i, 200), vad_speech=False)
        decision = fusion.classify(frame(6, 12000), vad_speech=False)
        self.assertTrue(decision.active)
        self.assertTrue(decision.acoustic_rescue)
        self.assertGreater(decision.rms, decision.acoustic_threshold_rms)


if __name__ == "__main__":
    unittest.main()
