import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DesktopRepair3OrbTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = (ROOT / "apps" / "desktop" / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
        cls.styles = (ROOT / "apps" / "desktop" / "ui" / "src" / "styles.css").read_text(encoding="utf-8")

    def test_one_persistent_particle_field_is_reused_across_states(self) -> None:
        self.assertIn("particlesRef = useRef<Particle[]>(createParticles(1320))", self.app)
        self.assertNotIn("particlesRef.current = createParticles", self.app)
        self.assertIn("One persistent particle field smoothly eases", self.app)

    def test_state_parameters_are_interpolated_not_hard_swapped(self) -> None:
        self.assertIn("const blend = 1 - Math.exp(-dt / 420)", self.app)
        self.assertIn("blended[key] += (target[key] - blended[key]) * blend", self.app)
        for field in ("speed", "scale", "brightness", "hueShift", "turbulence", "radialMotion", "coreEnergy"):
            self.assertIn(field, self.app)

    def test_each_product_state_has_distinct_visual_targets(self) -> None:
        for state in ("idle", "listening", "thinking", "speaking", "working"):
            self.assertRegex(self.app, rf"{state}:\s+\{{[^}}]+hueShift:")
        self.assertIn("listeningFocus", self.app)
        self.assertIn("thinkingTwist", self.app)
        self.assertIn("workingStream", self.app)

    def test_speaking_bounce_is_intentionally_subtle(self) -> None:
        match = re.search(r"speakingBreath[^\n]+\*\s*([0-9.]+)", self.app)
        self.assertIsNotNone(match)
        self.assertLessEqual(float(match.group(1)), 0.004)
        self.assertIn("less than half a percent scale motion", self.app)

    def test_speaking_brightness_is_higher_than_idle(self) -> None:
        idle = re.search(r"idle:\s+\{[^}]+brightness:\s*([0-9.]+)", self.app)
        speaking = re.search(r"speaking:\s+\{[^}]+brightness:\s*([0-9.]+)", self.app)
        self.assertIsNotNone(idle)
        self.assertIsNotNone(speaking)
        self.assertGreater(float(speaking.group(1)), float(idle.group(1)))

    def test_css_does_not_apply_instant_per_state_filters(self) -> None:
        self.assertIn("State identity is blended inside the persistent canvas field", self.styles)
        self.assertNotIn(".avatar--thinking .avatar__canvas { filter: saturate(1.2) hue-rotate", self.styles)
        self.assertNotIn(".avatar--speaking .avatar__canvas { filter: saturate(1.32) brightness", self.styles)

    def test_repair_remains_presentation_only(self) -> None:
        self.assertIn("gpt-realtime-2.1-mini", (ROOT / "providers" / "voice_frontend" / "openai_realtime" / "config.py").read_text(encoding="utf-8"))
        self.assertIn("captionCharacterDelay", self.app)
        self.assertIn("speech_end_to_first_audio_ms", self.app)


if __name__ == "__main__":
    unittest.main()
