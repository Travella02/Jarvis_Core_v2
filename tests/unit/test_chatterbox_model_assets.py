import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ChatterboxModelAssetTests(unittest.TestCase):
    def test_setup_prefetches_only_runtime_required_assets_with_resilient_downloader(self):
        script = (ROOT / "scripts" / "setup_chatterbox_runtime.ps1").read_text(encoding="utf-8")
        for name in (
            "t3_turbo_v1.safetensors",
            "s3gen_meanflow.safetensors",
            "ve.safetensors",
            "conds.pt",
            "tokenizer_config.json",
            "vocab.json",
            "merges.txt",
            "special_tokens_map.json",
            "added_tokens.json",
        ):
            self.assertIn(name, script)
        self.assertNotIn('@{ Name = "s3gen.safetensors";', script)
        self.assertIn("--continue-at", script)
        self.assertIn("--retry-all-errors", script)
        self.assertIn("Start-BitsTransfer", script)
        self.assertIn("Get-FileHash -Algorithm SHA256", script)
        self.assertIn("fcf1f8c1d651bb7e3acd69ee5be269b4ac10c02980b7708213d598bc9f7cdf87", script)
        self.assertIn("d65cb687a2ed581ee6cc297e919ffefa63386944f42364ae13b78a594945514f", script)


    def test_asset_urls_use_pinned_revision_and_safe_formatting(self):
        script = (ROOT / "scripts" / "setup_chatterbox_runtime.ps1").read_text(encoding="utf-8")
        self.assertIn('$ModelRevision = "1e4698ca7cbb41ff030c4185f0927a3b42d76924"', script)
        self.assertIn('$escapedName = [System.Uri]::EscapeDataString($Name)', script)
        self.assertIn('$uri = ("{0}/{1}" -f $ModelBaseUrl.TrimEnd("/"), $escapedName)', script)
        self.assertNotIn('$Name?download', script)
        self.assertNotIn('$ModelRevision = "main"', script)

    def test_sidecar_loads_explicit_local_assets_and_never_downloads_at_startup(self):
        sidecar = (ROOT / "providers" / "tts" / "chatterbox" / "sidecar.py").read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--model-dir", required=True)', sidecar)
        self.assertIn("ChatterboxTurboTTS.from_local", sidecar)
        self.assertNotIn("ChatterboxTurboTTS.from_pretrained", sidecar)
        self.assertIn("Chatterbox model assets are incomplete", sidecar)

    def test_provider_passes_provider_owned_model_directory_to_sidecar(self):
        provider = (ROOT / "providers" / "tts" / "chatterbox" / "provider.py").read_text(encoding="utf-8")
        self.assertIn('"--model-dir"', provider)
        self.assertIn("str(self.config.model_dir)", provider)

    def test_config_has_swappable_provider_local_model_directory(self):
        config = (ROOT / "providers" / "tts" / "chatterbox" / "config.py").read_text(encoding="utf-8")
        self.assertIn("JARVIS_CHATTERBOX_MODEL_DIR", config)
        self.assertIn('"models" / "chatterbox-turbo"', config)

    def test_voice_doctor_reports_local_model_asset_readiness_without_network(self):
        lab = (ROOT / "apps" / "voice_lab.py").read_text(encoding="utf-8")
        self.assertIn('"model_assets_ready"', lab)
        self.assertIn('"model_dir"', lab)


if __name__ == "__main__":
    unittest.main()
