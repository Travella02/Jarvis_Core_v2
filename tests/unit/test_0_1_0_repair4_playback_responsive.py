import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DesktopRepair4PlaybackResponsiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = (ROOT / "apps" / "desktop" / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
        cls.styles = (ROOT / "apps" / "desktop" / "ui" / "src" / "styles.css").read_text(encoding="utf-8")

    def test_speaking_state_follows_webrtc_playback_lifecycle(self) -> None:
        self.assertIn("type === 'output_audio_buffer.started'", self.app)
        self.assertIn("type === 'output_audio_buffer.stopped'", self.app)
        self.assertIn("audioPlayingRef.current = true", self.app)
        self.assertIn("audioPlayingRef.current = false", self.app)
        self.assertIn("Stay SPEAKING until its output buffer is actually drained", self.app)

    def test_caption_pacing_no_longer_drives_speaking_state(self) -> None:
        tick = re.search(r"const tick = \(\) => \{(.+?)\n\s*\};", self.app, re.S)
        self.assertIsNotNone(tick)
        self.assertNotIn("setStateSafely('speaking'", tick.group(1))
        self.assertIn("captions never end the speaking state", self.app)

    def test_playback_stop_finishes_caption_and_returns_ready(self) -> None:
        stopped = re.search(r"type === 'output_audio_buffer\.stopped'\)(.+?)else if \(type === 'output_audio_buffer\.cleared'", self.app, re.S)
        self.assertIsNotNone(stopped)
        body = stopped.group(1)
        self.assertIn("captionIndexRef.current = captionSourceRef.current.length", body)
        self.assertIn("setCaption(normalizeCaptionForDisplay(captionSourceRef.current))", body)
        self.assertIn("scheduleIdle(140)", body)

    def test_barge_in_clear_does_not_overwrite_newer_state(self) -> None:
        self.assertIn("type === 'output_audio_buffer.cleared'", self.app)
        self.assertIn("current === 'speaking' ? 'idle' : current", self.app)
        self.assertIn("output_audio_buffer.clear", self.app)

    def test_orb_canvas_uses_responsive_measured_size(self) -> None:
        self.assertIn("canvas.getBoundingClientRect().width", self.app)
        self.assertIn("const resizeObserver = new ResizeObserver(resize)", self.app)
        self.assertIn("resizeObserver.observe(canvas)", self.app)
        self.assertIn("const visualScale = cssSize / logicalSize", self.app)

    def test_presence_scales_from_smaller_viewport_dimension(self) -> None:
        self.assertIn("smaller viewport dimension (vmin)", self.styles)
        self.assertRegex(self.styles, r"\.avatar\s*\{[^}]*width:\s*min\(56vmin,\s*66vw\)", re.S)
        self.assertRegex(self.styles, r"\.caption\s*\{[^}]*font-size:\s*2\.8vmin", re.S)
        self.assertRegex(self.styles, r"\.composer\s*\{[^}]*width:\s*min\(72vw,\s*70vmin\)", re.S)

    def test_repair_remains_presentation_only(self) -> None:
        realtime = (ROOT / "providers" / "voice_frontend" / "openai_realtime" / "config.py").read_text(encoding="utf-8")
        self.assertIn("gpt-realtime-2.1-mini", realtime)
        self.assertIn("captionCharacterDelay", self.app)
        self.assertIn("const blend = 1 - Math.exp(-dt / 420)", self.app)


if __name__ == "__main__":
    unittest.main()
