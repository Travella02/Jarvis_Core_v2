import unittest

from core.voice import PlaybackLedger, VoiceLatencyTrace


class VoiceTelemetryPlaybackTests(unittest.TestCase):
    def test_latency_uses_monotonic_marks(self):
        trace = VoiceLatencyTrace()
        trace.mark("start", now_ns=2_000_000)
        trace.mark("end", now_ns=7_500_000)
        self.assertEqual(trace.elapsed_ms("start", "end"), 5.5)
        self.assertEqual(trace.as_milliseconds()["end"], 5.5)

    def test_playback_ledger_is_honest_about_unheard_bytes(self):
        ledger = PlaybackLedger()
        ledger.queue(100)
        ledger.played(65)
        ledger.interrupt()
        self.assertEqual(ledger.unheard_bytes, 35)
        self.assertTrue(ledger.interrupted)
