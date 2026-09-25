import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ChatterboxRuntimeCompatibilityTests(unittest.TestCase):
    def test_modern_cuda_profile_pins_blackwell_compatible_torch_271(self):
        script = (ROOT / "scripts" / "setup_chatterbox_runtime.ps1").read_text(encoding="utf-8")
        self.assertIn('$ModernTorchVersion = "2.7.1"', script)
        self.assertIn('https://download.pytorch.org/whl/cu128', script)
        self.assertIn('"torch==$ModernTorchVersion"', script)
        self.assertIn('"torchaudio==$ModernTorchVersion"', script)
        self.assertNotIn('"torch==2.11.0"', script)
        self.assertNotIn('"torchaudio==2.11.0"', script)

    def test_runtime_setup_forces_exact_torch_pair_and_cuda_smoke_test(self):
        script = (ROOT / "scripts" / "setup_chatterbox_runtime.ps1").read_text(encoding="utf-8")
        self.assertIn("--force-reinstall", script)
        self.assertIn("torch.cuda.get_device_name(0)", script)
        self.assertIn("torch.ones(1, device='cuda')", script)

    def test_sidecar_reports_structured_startup_error(self):
        sidecar = (ROOT / "providers" / "tts" / "chatterbox" / "sidecar.py").read_text(encoding="utf-8")
        self.assertIn('"event": "startup_error"', sidecar)
        self.assertIn("traceback.print_exc(file=sys.stderr)", sidecar)
        self.assertIn("contextlib.redirect_stdout(sys.stderr)", sidecar)

    def test_provider_persists_sidecar_stderr_in_runtime_log(self):
        provider = (ROOT / "providers" / "tts" / "chatterbox" / "provider.py").read_text(encoding="utf-8")
        self.assertIn('self._stderr_path = self._log_dir / "sidecar-stderr.log"', provider)
        self.assertIn("stderr=self._stderr_handle", provider)
        self.assertIn("sidecar log tail", provider)
        self.assertNotIn("stderr=asyncio.subprocess.DEVNULL", provider)

    def test_provider_handles_startup_error_protocol(self):
        provider = (ROOT / "providers" / "tts" / "chatterbox" / "provider.py").read_text(encoding="utf-8")
        self.assertIn('message.get("event") == "startup_error"', provider)
        self.assertIn("invalid Chatterbox startup protocol", provider)


if __name__ == "__main__":
    unittest.main()
