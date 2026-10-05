import unittest

from core.diagnostics import collect_diagnostics


class DiagnosticsTests(unittest.TestCase):
    def test_reports_voice_lab_without_loading_live_runtimes(self) -> None:
        data = collect_diagnostics()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["network_probe"], "not-run")
        self.assertEqual(data["audio_probe"], "not-run")
        self.assertEqual(data["external_actions"], "disabled-in-core-diagnostics")
        self.assertEqual(data["providers"]["intelligence"], "provider-layer-ready")
        self.assertEqual(data["providers"]["runtime_probe"], "not-run")
        self.assertEqual(data["providers"]["stt_candidate"], "whisper.cpp/large-v3-turbo-q5_0")
        self.assertEqual(data["conversation"]["context"], "ready")
        self.assertEqual(data["conversation"]["voice_path"], "ready")
        self.assertEqual(data["voice"]["engine"], "ready")
        self.assertEqual(data["runtime"]["host"], "ready")
        self.assertEqual(data["runtime"]["event_replay"], "sequence-cursor-ready")
        self.assertEqual(data["voice"]["full_duplex"], "ready-headset-first")


if __name__ == "__main__":
    unittest.main()
