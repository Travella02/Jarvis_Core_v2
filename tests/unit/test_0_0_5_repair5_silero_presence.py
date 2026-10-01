import unittest
from pathlib import Path

from core.common.ids import CorrelationContext
from core.voice.contracts import AudioFormat, AudioFrame, AudioSampleFormat
from providers.vad import SileroVadConfig, WhisperCppSileroVadDetector


ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "core" / "voice" / "engine.py"
CONTROL = ROOT / "core" / "voice" / "conversation_control.py"
VOICE_LAB = ROOT / "apps" / "voice_lab.py"
SETUP = ROOT / "scripts" / "setup_whisper_vad.ps1"


class FakeProbabilitySource:
    def __init__(self, probabilities):
        self.probabilities = list(probabilities)
        self.calls = 0
        self.reset_calls = 0
        self.closed = False

    def probability(self, samples):
        self.calls += 1
        self.asserted_size = len(samples)
        if self.probabilities:
            return self.probabilities.pop(0)
        return 0.0

    def reset(self):
        self.reset_calls += 1

    def close(self):
        self.closed = True


def frame(sequence: int, *, sample_count: int = 480, sample_value: int = 0) -> AudioFrame:
    value = int(sample_value).to_bytes(2, "little", signed=True)
    return AudioFrame(
        trace=CorrelationContext.create(),
        sequence=sequence,
        format=AudioFormat(16_000, 1, AudioSampleFormat.PCM_S16LE),
        payload=value * sample_count,
    )


class Repair5SileroPresenceTests(unittest.TestCase):
    def test_neural_probability_not_pcm_loudness_is_authority(self):
        source = FakeProbabilitySource([0.90])
        detector = WhisperCppSileroVadDetector(
            SileroVadConfig(threshold=0.50), source=source
        )
        # 30 ms = 480 samples, so the first frame only fills the streaming buffer.
        self.assertFalse(detector.is_speech(frame(0, sample_value=0)))
        # The second all-zero frame completes a 512-sample Silero window. The fake
        # neural probability says speech; RMS/amplitude is intentionally irrelevant.
        self.assertTrue(detector.is_speech(frame(1, sample_value=0)))
        self.assertEqual(source.asserted_size, 512)
        self.assertAlmostEqual(detector.last_probability, 0.90)

    def test_probability_below_threshold_is_not_speech_even_for_loud_pcm(self):
        source = FakeProbabilitySource([0.10])
        detector = WhisperCppSileroVadDetector(
            SileroVadConfig(threshold=0.50), source=source
        )
        detector.is_speech(frame(0, sample_value=20_000))
        self.assertFalse(detector.is_speech(frame(1, sample_value=20_000)))

    def test_reset_clears_streaming_state(self):
        source = FakeProbabilitySource([0.9])
        detector = WhisperCppSileroVadDetector(source=source)
        detector.is_speech(frame(0))
        detector.reset()
        self.assertEqual(source.reset_calls, 1)
        self.assertEqual(detector.last_probability, 0.0)
        # Buffer was cleared, so one 30 ms frame still cannot produce a decision.
        self.assertFalse(detector.is_speech(frame(1)))

    def test_close_releases_probability_source(self):
        source = FakeProbabilitySource([])
        detector = WhisperCppSileroVadDetector(source=source)
        detector.close()
        self.assertTrue(source.closed)
        detector.close()  # idempotent

    def test_engine_starts_stt_only_after_neural_vad_speech_start(self):
        text = ENGINE.read_text(encoding="utf-8")
        start_stt = text.index("async def start_stt")
        onset = text.index("signal = onset.accept(vad_speech)")
        invoke = text.index("await start_stt(initial)", onset)
        self.assertLess(start_stt, onset)
        self.assertLess(onset, invoke)
        self.assertNotIn("activity.classify", text)
        self.assertNotIn("SpeechActivityFusion()", text)

    def test_barge_in_uses_neural_speech_started_not_whisper_text(self):
        text = CONTROL.read_text(encoding="utf-8")
        self.assertIn('name="jarvis-interruption-speech-start"', text)
        self.assertIn("neural speech presence during active turn", text)
        self.assertNotIn('name="jarvis-interruption-lexical"', text)

    def test_voice_lab_uses_silero_for_continuous_and_webrtc_only_for_legacy(self):
        text = VOICE_LAB.read_text(encoding="utf-8")
        self.assertIn("WhisperCppSileroVadDetector", text)
        self.assertIn("if args.legacy_half_duplex", text)
        self.assertIn("Speech presence:", text)

    def test_setup_pins_small_vad_model_by_hash(self):
        text = SETUP.read_text(encoding="utf-8")
        self.assertIn("ggml-silero-v6.2.0.bin", text)
        self.assertIn("885098", text)
        self.assertIn(
            "2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987",
            text,
        )

    def test_listener_cancellation_is_cooperative_before_hard_cancel(self):
        text = CONTROL.read_text(encoding="utf-8")
        cancel_capture = text.index('await self.engine.cancel_capture("voice session listener cancelled")')
        wait = text.index("await asyncio.wait({task}, timeout=1.5)", cancel_capture)
        hard_cancel = text.index("task.cancel()", wait)
        self.assertLess(cancel_capture, wait)
        self.assertLess(wait, hard_cancel)


if __name__ == "__main__":
    unittest.main()
