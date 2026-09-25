"""Isolated JSON-line Qwen3-TTS 0.6B Base worker.

No Jarvis imports are allowed here. The worker lives in the provider-specific
runtime so Qwen/PyTorch dependency changes remain replaceable.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import tempfile
import traceback
from pathlib import Path


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
    sys.stdout.flush()



def _reference_metrics(sf, np, reference: str) -> dict:
    info = sf.info(reference)
    data, sample_rate = sf.read(reference, dtype="float32", always_2d=True)
    if data.size == 0:
        raise RuntimeError("reference audio is empty")
    channels = int(data.shape[1])
    mono = data.mean(axis=1, dtype=np.float32)
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(mono), dtype=np.float64))) if mono.size else 0.0
    clipping_ratio = float(np.mean(np.abs(mono) >= 0.999)) if mono.size else 0.0
    near_silence_ratio = float(np.mean(np.abs(mono) <= 0.001)) if mono.size else 1.0
    duration_s = float(len(mono)) / float(sample_rate)
    warnings = []
    if duration_s < 3.0:
        warnings.append("reference is shorter than Qwen's advertised ~3-second rapid-clone target")
    if duration_s > 30.0:
        warnings.append("reference is longer than needed for this diagnostic; use a concise clean clip")
    if peak < 0.01 or rms < 0.003:
        warnings.append("reference level is very quiet")
    if clipping_ratio > 0.001:
        warnings.append("reference contains clipped samples")
    if near_silence_ratio > 0.85:
        warnings.append("reference is mostly near-silence")
    if channels > 2:
        warnings.append("reference has more than two channels")
    return {
        "path": str(Path(reference).resolve()),
        "sample_rate": int(sample_rate),
        "channels": channels,
        "frames": int(len(mono)),
        "duration_ms": round(duration_s * 1000.0, 3),
        "format": str(info.format),
        "subtype": str(info.subtype),
        "peak": round(peak, 6),
        "rms": round(rms, 6),
        "clipping_ratio": round(clipping_ratio, 8),
        "near_silence_ratio": round(near_silence_ratio, 6),
        "warnings": warnings,
    }


def _write_waveform(sf, np, output_dir: Path, request_id: str, label: str, wav, sample_rate: int) -> dict:
    samples = np.asarray(wav, dtype=np.float32).squeeze()
    if samples.ndim != 1 or samples.size == 0:
        raise RuntimeError(f"unexpected Qwen waveform shape: {samples.shape}")
    if not np.isfinite(samples).all():
        raise RuntimeError("Qwen waveform contains NaN/Inf samples")
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(samples), dtype=np.float64))) if samples.size else 0.0
    duration_s = float(samples.size) / float(sample_rate)
    temp = tempfile.NamedTemporaryFile(prefix=f"jarvis_qwen_{request_id}_{label}_", suffix=".wav", dir=output_dir, delete=False)
    temp.close()
    path = Path(temp.name)
    sf.write(str(path), samples, int(sample_rate), subtype="PCM_16")
    return {
        "path": str(path),
        "sample_rate": int(sample_rate),
        "sample_count": int(samples.size),
        "waveform_peak": round(peak, 6),
        "waveform_rms": round(rms, 6),
        "duration_ms": round(duration_s * 1000.0, 3),
        "plausible": duration_s >= 0.5,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--attention", default="sdpa")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        with contextlib.redirect_stdout(sys.stderr):
            import numpy as np
            import soundfile as sf
            import torch
            from qwen_tts import Qwen3TTSModel

            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            model_dir = Path(args.model_dir)
            if not (model_dir / "config.json").is_file() or not (model_dir / "model.safetensors").is_file():
                raise FileNotFoundError(
                    f"Qwen3-TTS model assets are incomplete at {model_dir}; run setup_qwen3_tts_runtime.ps1"
                )
            dtype = getattr(torch, args.dtype)
            device_map = "cuda:0" if args.device == "cuda" else args.device
            model = Qwen3TTSModel.from_pretrained(
                str(model_dir),
                device_map=device_map,
                dtype=dtype,
                attn_implementation=args.attention,
            )
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        emit({"event": "startup_error", "error": f"{type(exc).__name__}: {exc}"})
        return 1

    emit(
        {
            "event": "ready",
            "device": args.device,
            "torch": torch.__version__,
            "cuda": bool(torch.cuda.is_available()),
        }
    )

    cached_prompt = None
    cached_key = None

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        request = None
        try:
            request = json.loads(raw)
            request_id = str(request["id"])
            op = request.get("op")
            if op == "health":
                emit({"id": request_id, "ok": True, "status": "ready"})
                continue
            if op == "diagnose_reference":
                reference = str(request.get("reference_audio_path") or "").strip()
                if not reference or not Path(reference).is_file():
                    raise FileNotFoundError(reference or "reference audio path missing")
                metrics = _reference_metrics(sf, np, reference)
                reference_text = str(request.get("reference_text") or "").strip()
                metrics["reference_text_chars"] = len(reference_text)
                metrics["reference_text_words"] = len(reference_text.split()) if reference_text else 0
                emit({"id": request_id, "ok": True, "reference": metrics})
                continue
            if op == "upstream_smoke":
                text = str(request.get("text") or "").strip()
                reference = str(request.get("reference_audio_path") or "").strip()
                reference_text = str(request.get("reference_text") or "").strip() or None
                language = str(request.get("language") or "English").strip() or "English"
                x_vector_only = bool(request.get("x_vector_only", False))
                if not text:
                    raise ValueError("text cannot be empty")
                if not reference or not Path(reference).is_file():
                    raise FileNotFoundError(reference or "reference audio path missing")
                if not x_vector_only and not reference_text:
                    raise ValueError("full upstream clone requires reference_text")
                with torch.inference_mode(), contextlib.redirect_stdout(sys.stderr):
                    wavs, sample_rate = model.generate_voice_clone(
                        text=text,
                        language=language,
                        ref_audio=reference,
                        ref_text=None if x_vector_only else reference_text,
                        x_vector_only_mode=x_vector_only,
                        max_new_tokens=2048,
                    )
                result = _write_waveform(sf, np, output_dir, request_id, "xvector" if x_vector_only else "full", wavs[0], int(sample_rate))
                result.update({
                    "id": request_id,
                    "ok": True,
                    "mode": "x-vector-only" if x_vector_only else "full-reference-text",
                    "api_path": "official-direct-generate_voice_clone",
                })
                emit(result)
                continue
            if op == "shutdown":
                emit({"id": request_id, "ok": True})
                return 0
            if op != "synthesize":
                raise ValueError(f"unsupported op: {op}")

            text = str(request.get("text", "")).strip()
            if not text:
                raise ValueError("text cannot be empty")
            reference = str(request.get("reference_audio_path") or "").strip()
            if not reference:
                raise ValueError("Qwen3-TTS Base requires a local reference audio path")
            if not Path(reference).is_file():
                raise FileNotFoundError(reference)
            reference_text = str(request.get("reference_text") or "").strip() or None
            language = str(request.get("language") or "English").strip() or "English"
            settings = dict(request.get("settings") or {})
            # Live repair16 A/B testing proved the saved reference audio and Qwen
            # runtime are healthy in x-vector mode, while the transcript-conditioned
            # full clone path can run away into very long garbage audio.  Normal
            # Jarvis synthesis therefore defaults to x-vector cloning regardless of
            # whether a transcript is stored with the VoiceProfile.  Full-reference
            # conditioning remains diagnostic-only until separately accepted.
            full_reference_clone = bool(settings.get("full_reference_clone", False))
            x_vector_only = not full_reference_clone
            if settings.get("x_vector_only") is True:
                x_vector_only = True
            effective_reference_text = None if x_vector_only else reference_text
            cache_key = (reference, effective_reference_text, x_vector_only)

            with torch.inference_mode(), contextlib.redirect_stdout(sys.stderr):
                if cached_prompt is None or cached_key != cache_key:
                    cached_prompt = model.create_voice_clone_prompt(
                        ref_audio=reference,
                        ref_text=effective_reference_text,
                        x_vector_only_mode=x_vector_only,
                    )
                    cached_key = cache_key
                generation_kwargs = {}
                for key in ("temperature", "top_p", "top_k", "repetition_penalty"):
                    if key in settings:
                        generation_kwargs[key] = settings[key]
                # Qwen Base currently defaults voice-clone generation to a
                # simulated-streaming text layout.  For Jarvis Voice Lab we feed
                # complete, prosody-safe phrases, so force the stable offline
                # layout explicitly.  This avoids the upstream speaking-rate /
                # prompt-alignment instability of non_streaming_mode=False.
                generation_kwargs.setdefault("do_sample", True)
                generation_kwargs.setdefault("max_new_tokens", 512)
                wavs, sample_rate = model.generate_voice_clone(
                    text=text,
                    language=language,
                    voice_clone_prompt=cached_prompt,
                    non_streaming_mode=True,
                    **generation_kwargs,
                )

            # Follow Qwen's official examples and let libsndfile serialize the
            # model's float waveform directly.  Manual PCM scaling is deliberately
            # avoided here: this keeps Jarvis aligned with Qwen's supported output
            # contract and prevents provider-specific dtype/range assumptions from
            # turning otherwise valid speech into noise.
            samples = np.asarray(wavs[0], dtype=np.float32).squeeze()
            if samples.ndim != 1 or samples.size == 0:
                raise RuntimeError(f"unexpected Qwen waveform shape: {samples.shape}")
            if not np.isfinite(samples).all():
                raise RuntimeError("Qwen waveform contains NaN/Inf samples")
            peak = float(np.max(np.abs(samples))) if samples.size else 0.0
            rms = float(np.sqrt(np.mean(np.square(samples), dtype=np.float64))) if samples.size else 0.0
            duration_s = float(samples.size) / float(sample_rate)
            # Fail closed on implausibly short clips. A previous integration bug
            # returned only 3,840 samples (160 ms at 24 kHz) for a full sentence
            # and the provider incorrectly treated it as valid speech. Allow very
            # short words, but require at least ~125 ms per whitespace token up
            # to a conservative 1.25 second floor for longer utterances.
            word_count = max(1, len(text.split()))
            minimum_duration_s = min(1.25, max(0.08, word_count / 8.0))
            if duration_s + 1e-9 < minimum_duration_s:
                raise RuntimeError(
                    "Qwen generated implausibly short audio "
                    f"({duration_s:.3f}s for {word_count} words; "
                    f"minimum expected {minimum_duration_s:.3f}s). "
                    "Generation was rejected instead of forwarding noise to playback."
                )
            temp = tempfile.NamedTemporaryFile(
                prefix=f"jarvis_qwen_{request_id}_",
                suffix=".wav",
                dir=output_dir,
                delete=False,
            )
            temp.close()
            path = Path(temp.name)
            sf.write(str(path), samples, int(sample_rate), subtype="PCM_16")
            emit(
                {
                    "id": request_id,
                    "ok": True,
                    "path": str(path),
                    "sample_rate": int(sample_rate),
                    "sample_count": int(samples.size),
                    "waveform_peak": round(peak, 6),
                    "waveform_rms": round(rms, 6),
                    "duration_ms": round(duration_s * 1000.0, 3),
                    "generation_mode": "stable-non-streaming",
                    "voice_prompt_cached": True,
                }
            )
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            emit(
                {
                    "id": str(request.get("id", "unknown")) if isinstance(request, dict) else "unknown",
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
