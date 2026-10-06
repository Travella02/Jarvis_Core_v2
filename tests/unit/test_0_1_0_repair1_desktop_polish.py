import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DesktopRepair1PolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = (ROOT / "apps" / "desktop" / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
        cls.styles = (ROOT / "apps" / "desktop" / "ui" / "src" / "styles.css").read_text(encoding="utf-8")
        cls.host = (ROOT / "apps" / "desktop_alpha.py").read_text(encoding="utf-8")

    def test_avatar_is_code_native_particle_orb(self) -> None:
        self.assertIn("function ParticleOrb", self.app)
        self.assertRegex(self.app, r"createParticles\(\d{3,}\)")
        self.assertIn("requestAnimationFrame(draw)", self.app)
        self.assertIn("<canvas", self.app)
        self.assertNotIn("freepik", (self.app + self.styles).lower())
        self.assertNotIn("avatar__orbit", self.app)

    def test_particle_orb_reacts_to_initial_states(self) -> None:
        for state in ("listening", "thinking", "speaking", "working"):
            self.assertIn(f"avatar--{state}", self.styles)
        self.assertIn("current === 'speaking'", self.app)
        self.assertIn("current === 'working'", self.app)

    def test_caption_is_paced_instead_of_dumped_directly(self) -> None:
        self.assertIn("captionSourceRef", self.app)
        self.assertIn("captionCharacterDelay", self.app)
        self.assertIn("enqueueCaptionDelta", self.app)
        self.assertIn("window.setTimeout(tick", self.app)
        self.assertNotIn("setCaption((current) => `${current}${event.delta || ''}`)", self.app)

    def test_cancelled_response_drops_unspoken_caption_backlog(self) -> None:
        self.assertIn("generated but never actually spoken", self.app)
        self.assertIn("event.response?.status === 'cancelled'", self.app)
        self.assertIn("clearCaptionPacing(false)", self.app)

    def test_latency_telemetry_captures_turn_boundaries_and_first_output(self) -> None:
        for event_name in (
            "input_audio_buffer.speech_started",
            "input_audio_buffer.speech_stopped",
            "response.created",
            "response.output_audio_transcript.delta",
            "output_audio_buffer.started",
        ):
            self.assertIn(event_name, self.app)
        self.assertIn("speech_end_to_response_created_ms", self.app)
        self.assertIn("speech_end_to_first_audio_ms", self.app)
        self.assertIn("response_created_to_first_audio_ms", self.app)
        self.assertIn("[Desktop latency]", self.host)

    def test_http_ui_fallback_does_not_mount_staticfiles_at_root(self) -> None:
        self.assertNotIn("StaticFiles", self.host)
        self.assertIn('@app.get("/{asset_path:path}")', self.host)
        self.assertIn("websocket scopes never enter this GET-only route", self.host)


if __name__ == "__main__":
    unittest.main()
