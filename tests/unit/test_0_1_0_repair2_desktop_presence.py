import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DesktopRepair2PresenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = (ROOT / "apps" / "desktop" / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
        cls.styles = (ROOT / "apps" / "desktop" / "ui" / "src" / "styles.css").read_text(encoding="utf-8")

    def test_orb_is_larger_and_denser(self) -> None:
        match = re.search(r"createParticles\((\d+)\)", self.app)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 1000)
        self.assertIn("const logicalSize = 420", self.app)
        self.assertIn('width="420" height="420"', self.app)
        self.assertIn("width: min(56vmin, 66vw)", self.styles)

    def test_orb_particles_form_a_flowing_spherical_dust_field(self) -> None:
        self.assertIn("shellRadius", self.app)
        self.assertIn("innerRadius", self.app)
        self.assertIn("flowA", self.app)
        self.assertIn("flowB", self.app)
        self.assertIn("flowC", self.app)
        self.assertIn("globalCompositeOperation = 'lighter'", self.app)

    def test_captions_reveal_character_by_character(self) -> None:
        self.assertIn("captionIndexRef", self.app)
        self.assertIn("captionCharacterDelay(character", self.app)
        self.assertIn("source.slice(0, captionIndexRef.current)", self.app)
        self.assertNotIn("captionQueueRef", self.app)
        self.assertNotIn("completeTokens", self.app)

    def test_caption_reveal_waits_for_audio_playout_start(self) -> None:
        self.assertIn("captionAudioStartedRef", self.app)
        self.assertIn("output_audio_buffer.started", self.app)
        self.assertIn("pumpCaption(45)", self.app)
        self.assertIn("if (captionAudioStartedRef.current) pumpCaption()", self.app)

    def test_caption_display_repairs_basic_spacing_and_punctuation(self) -> None:
        self.assertIn("normalizeCaptionForDisplay", self.app)
        self.assertIn(r".replace(/\s+([,.;:!?])/g, '$1')", self.app)
        self.assertIn(".replace(/([.!?])(?=[A-Z0-9])/g, '$1 ')", self.app)
        self.assertIn(".replace(/([,;:])(?=[A-Za-z0-9])/g, '$1 ')", self.app)

    def test_repair_is_presentation_only(self) -> None:
        self.assertIn("gpt-realtime-2.1-mini", (ROOT / "providers" / "voice_frontend" / "openai_realtime" / "config.py").read_text(encoding="utf-8"))
        self.assertNotIn("semantic_vad", self.styles)


if __name__ == "__main__":
    unittest.main()
