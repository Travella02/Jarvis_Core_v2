import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Qwen3TTSCandidateTests(unittest.TestCase):
    def test_setup_is_isolated_and_pins_blackwell_cuda_runtime(self):
        script = (ROOT / "scripts" / "setup_qwen3_tts_runtime.ps1").read_text(encoding="utf-8")
        self.assertIn('.runtime\\voice\\qwen3_tts', script)
        self.assertIn('qwen-tts==0.1.1', script)
        self.assertIn('torch==2.7.1+cu128', script)
        self.assertIn('torchaudio==2.7.1+cu128', script)
        self.assertIn('https://download.pytorch.org/whl/cu128', script)
        self.assertIn('Qwen/Qwen3-TTS-12Hz-0.6B-Base', script)
        self.assertNotIn('flash-attn', script.lower())

    def test_model_downloader_is_resumable_by_huggingface_cache_and_retries(self):
        helper = (ROOT / "scripts" / "download_qwen3_tts_model.py").read_text(encoding="utf-8")
        self.assertIn('snapshot_download', helper)
        self.assertIn('attempts', helper)
        self.assertIn('model.safetensors', helper)
        self.assertIn('max_workers=4', helper)

    def test_sidecar_uses_official_base_clone_and_caches_voice_prompt(self):
        sidecar = (ROOT / "providers" / "tts" / "qwen3" / "sidecar.py").read_text(encoding="utf-8")
        self.assertIn('Qwen3TTSModel.from_pretrained', sidecar)
        self.assertIn('create_voice_clone_prompt', sidecar)
        self.assertIn('generate_voice_clone', sidecar)
        self.assertIn('cached_prompt', sidecar)
        self.assertIn('x_vector_only_mode', sidecar)
        self.assertIn('attn_implementation=args.attention', sidecar)

    def test_sidecar_serializes_waveform_with_official_soundfile_path(self):
        sidecar = (ROOT / "providers" / "tts" / "qwen3" / "sidecar.py").read_text(encoding="utf-8")
        self.assertIn('import soundfile as sf', sidecar)
        self.assertIn('sf.write(str(path), samples, int(sample_rate), subtype="PCM_16")', sidecar)
        self.assertIn('np.isfinite(samples).all()', sidecar)
        self.assertNotIn('(samples * 32767.0).astype(np.int16)', sidecar)

    def test_qwen_voice_clone_forces_stable_non_streaming_generation(self):
        sidecar = (ROOT / "providers" / "tts" / "qwen3" / "sidecar.py").read_text(encoding="utf-8")
        self.assertIn('non_streaming_mode=True', sidecar)
        self.assertIn('generation_kwargs.setdefault("do_sample", True)', sidecar)
        self.assertIn('generation_kwargs.setdefault("max_new_tokens", 512)', sidecar)

    def test_qwen_rejects_implausibly_short_audio_and_reports_duration(self):
        sidecar = (ROOT / "providers" / "tts" / "qwen3" / "sidecar.py").read_text(encoding="utf-8")
        lab = (ROOT / "apps" / "voice_lab.py").read_text(encoding="utf-8")
        self.assertIn('minimum_duration_s', sidecar)
        self.assertIn('implausibly short audio', sidecar)
        self.assertIn('"generation_mode": "stable-non-streaming"', sidecar)
        self.assertIn('duration={duration_ms:.1f} ms', lab)

    def test_voice_lab_can_swap_tts_without_changing_core(self):
        lab = (ROOT / "apps" / "voice_lab.py").read_text(encoding="utf-8")
        self.assertIn('"--tts-provider"', lab)
        self.assertIn('choices=["chatterbox", "qwen3"]', lab)
        self.assertIn('"--voice-ref-text"', lab)
        self.assertIn('provider_hint=args.tts_provider', lab)
        self.assertIn('_tts_provider_from_args(args)', lab)

    def test_qwen_base_requires_reference_audio_at_adapter_boundary(self):
        provider = (ROOT / "providers" / "tts" / "qwen3" / "provider.py").read_text(encoding="utf-8")
        self.assertIn('VoiceProfile.reference_audio_path', provider)
        self.assertIn('Qwen3-TTS Base requires', provider)

    def test_voice_lab_supports_saved_reference_profiles(self):
        lab = (ROOT / "apps" / "voice_lab.py").read_text(encoding="utf-8")
        self.assertIn('"--voice-library"', lab)
        self.assertIn('"--save-voice-profile"', lab)
        self.assertIn('"--voice-profile"', lab)
        self.assertIn('VoiceReferenceLibrary', lab)


    def test_qwen_sidecar_exposes_reference_validation_and_direct_upstream_smoke(self):
        sidecar = (ROOT / "providers" / "tts" / "qwen3" / "sidecar.py").read_text(encoding="utf-8")
        self.assertIn('"diagnose_reference"', sidecar)
        self.assertIn('"upstream_smoke"', sidecar)
        self.assertIn('ref_audio=reference', sidecar)
        self.assertIn('max_new_tokens=2048', sidecar)
        self.assertIn('"official-direct-generate_voice_clone"', sidecar)

    def test_qwen_reference_validation_checks_signal_quality(self):
        sidecar = (ROOT / "providers" / "tts" / "qwen3" / "sidecar.py").read_text(encoding="utf-8")
        self.assertIn('clipping_ratio', sidecar)
        self.assertIn('near_silence_ratio', sidecar)
        self.assertIn('duration_s < 3.0', sidecar)
        self.assertIn('reference level is very quiet', sidecar)

    def test_voice_lab_exposes_qwen_clone_diagnostic(self):
        lab = (ROOT / "apps" / "voice_lab.py").read_text(encoding="utf-8")
        provider = (ROOT / "providers" / "tts" / "qwen3" / "provider.py").read_text(encoding="utf-8")
        self.assertIn('"--qwen-clone-diagnostic"', lab)
        self.assertIn('qwen_clone_diagnostic', lab)
        self.assertIn('upstream_smoke', provider)
        self.assertIn('diagnose_reference', provider)

    def test_qwen_normal_synthesis_defaults_to_xvector_clone_mode(self):
        sidecar = (ROOT / "providers" / "tts" / "qwen3" / "sidecar.py").read_text(encoding="utf-8")
        self.assertIn('full_reference_clone = bool(settings.get("full_reference_clone", False))', sidecar)
        self.assertIn('x_vector_only = not full_reference_clone', sidecar)
        self.assertIn('effective_reference_text = None if x_vector_only else reference_text', sidecar)
        self.assertNotIn('settings.get("x_vector_only", reference_text is None)', sidecar)



if __name__ == "__main__":
    unittest.main()
