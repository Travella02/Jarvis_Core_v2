from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class Repair4WebRTCLifecycleTests(unittest.TestCase):
    def test_gpt_live_browser_closes_peer_if_core_control_socket_closes(self) -> None:
        text = (ROOT / "apps" / "web" / "gpt_live_webrtc_lab.html").read_text(encoding="utf-8")
        self.assertIn("ws.onclose", text)
        self.assertIn("stopTest()", text)

    def test_realtime_browser_closes_peer_if_core_control_socket_closes(self) -> None:
        text = (ROOT / "apps" / "web" / "gpt_realtime_webrtc_lab.html").read_text(encoding="utf-8")
        self.assertIn("ws.onclose", text)
        self.assertIn("Realtime media session closed automatically", text)

    def test_browser_pages_never_embed_project_api_key(self) -> None:
        for rel in ("apps/web/gpt_live_webrtc_lab.html", "apps/web/gpt_realtime_webrtc_lab.html"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("OPENAI_API_KEY", text)
            self.assertNotIn("Bearer ", text)


if __name__ == "__main__":
    unittest.main()
