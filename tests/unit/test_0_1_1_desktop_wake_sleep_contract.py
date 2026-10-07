from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / "apps" / "desktop" / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
HOST = (ROOT / "apps" / "desktop_alpha.py").read_text(encoding="utf-8")
WAKE = (ROOT / "core" / "voice" / "wake_listener.py").read_text(encoding="utf-8")


class DesktopWakeSleepContractTests(unittest.TestCase):
    def test_presence_is_separate_from_activity_state(self) -> None:
        self.assertIn("type PresenceState = 'sleeping' | 'awake'", APP)
        self.assertIn("type JarvisState = 'sleeping' | 'waking'", APP)
        self.assertIn("const [presence, setPresence]", APP)

    def test_sleeping_client_uses_local_wake_websocket_not_realtime_media(self) -> None:
        self.assertIn("/ws/wake", APP)
        self.assertIn("presenceRef.current !== 'sleeping'", APP)
        self.assertIn("startWakeAudioTap", APP)
        self.assertIn("LocalWakeListener", HOST)
        self.assertIn("Nothing leaves the machine while", WAKE)

    def test_embedded_wake_command_is_preserved_into_same_realtime_session(self) -> None:
        self.assertIn("command_text", APP)
        self.assertIn("startRealtimeSession(command, 'local_wake_phrase')", APP)
        self.assertIn("dispatchTextToRealtime(preservedCommand)", APP)

    def test_typed_input_can_wake_without_a_parallel_text_brain(self) -> None:
        self.assertIn("startRealtimeSession(text, 'typed_wake')", APP)
        self.assertIn("conversation.item.create", APP)
        self.assertNotIn("/api/luna", APP)

    def test_idle_timeout_and_explicit_sleep_close_realtime_then_restore_local_wake(self) -> None:
        self.assertIn("idleSleepSecondsRef = useRef(60)", APP)
        self.assertIn("enterSleep('idle_timeout')", APP)
        self.assertIn("payload.kind === 'lifecycle_command' && payload.command === 'sleep'", APP)
        self.assertIn("await stopRealtimeSession({ notifyServer: false })", APP)
        self.assertIn("await startWakeListening()", APP)


    def test_electron_keeps_local_wake_media_alive_when_minimized(self) -> None:
        electron = (ROOT / "apps" / "desktop" / "electron" / "main.cjs").read_text(encoding="utf-8")
        self.assertIn("backgroundThrottling: false", electron)

    def test_app_shutdown_releases_wake_realtime_and_microphone(self) -> None:
        self.assertIn("await stopWakeListening()", APP)
        self.assertIn("await stopRealtimeSession()", APP)
        self.assertIn("micRef.current?.getTracks().forEach((track) => track.stop())", APP)


if __name__ == "__main__":
    unittest.main()
