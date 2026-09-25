import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ChatterboxLocalLoaderCompatibilityTests(unittest.TestCase):
    def test_turbo_sidecar_uses_release_compatible_from_local_signature(self):
        sidecar = (
            ROOT / "providers" / "tts" / "chatterbox" / "sidecar.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "ChatterboxTurboTTS.from_local(model_dir, device=args.device)",
            sidecar,
        )
        self.assertNotIn("from_local(model_dir, device=args.device, nano=", sidecar)

    def test_turbo_provider_does_not_depend_on_nano_loader_switch(self):
        sidecar = (
            ROOT / "providers" / "tts" / "chatterbox" / "sidecar.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"t3_turbo_v1.safetensors"', sidecar)
        self.assertNotIn('"t3_nano_v1.safetensors"', sidecar)


if __name__ == "__main__":
    unittest.main()
