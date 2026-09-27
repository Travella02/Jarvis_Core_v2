"""0.0.4 local Voice Lab with swappable STT/TTS provider candidates."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import shutil
import sys
import wave
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.conversation import ConversationContext, ConversationCore
from core.conversation.engine import VOICE_RESPONSE_INSTRUCTION
from core.intelligence import IntelligenceContext, IntelligenceEventType, ReasoningPolicy
from core.voice import (
    AudioFormat,
    AudioSampleFormat,
    EndpointConfig,
    EndpointDetector,
    EndpointSignal,
    SpeechEvidenceGate,
    VoiceLabEngine,
    VoiceProfile,
    VoiceProviderRegistry,
    VoiceReferenceLibrary,
    pcm16_rms,
)
from integrations.audio import SoundDeviceAudioInput, SoundDeviceAudioOutput, WebRtcVadDetector
from providers.intelligence.openai import OpenAIProvider, OpenAIProviderConfig
from providers.stt.whisper_cpp import WhisperCppConfig, WhisperCppProvider
from providers.tts.chatterbox import ChatterboxConfig, ChatterboxTurboProvider
from providers.tts.qwen3 import Qwen3TTSConfig, Qwen3TTSProvider
from providers.tts.qwen3_streaming_candidate import Qwen3StreamingConfig, Qwen3StreamingProvider


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIO_PREFS_PATH = PROJECT_ROOT / ".runtime" / "voice" / "audio_devices.json"
VOICE_REFERENCE_ROOT = PROJECT_ROOT / ".runtime" / "voice" / "references"
VOICE_INPUT_FORMAT = AudioFormat(16000, 1, AudioSampleFormat.PCM_S16LE)


def _present(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _load_audio_preferences() -> dict[str, int]:
    try:
        payload = json.loads(AUDIO_PREFS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    result: dict[str, int] = {}
    for key in ("input_device", "output_device"):
        value = payload.get(key)
        if isinstance(value, int) and value >= 0:
            result[key] = value
    return result


def _save_audio_preferences(input_device: int | None, output_device: int | None) -> None:
    current = _load_audio_preferences()
    if input_device is not None:
        current["input_device"] = input_device
    if output_device is not None:
        current["output_device"] = output_device
    if not current:
        raise ValueError("provide --input-device and/or --output-device with --save-devices")
    AUDIO_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = AUDIO_PREFS_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    temp.replace(AUDIO_PREFS_PATH)


def _apply_saved_devices(args: argparse.Namespace) -> None:
    saved = _load_audio_preferences()
    if args.input_device is None:
        args.input_device = saved.get("input_device")
    if args.output_device is None:
        args.output_device = saved.get("output_device")


def _voice_library() -> VoiceReferenceLibrary:
    return VoiceReferenceLibrary(VOICE_REFERENCE_ROOT)


def _list_voice_library() -> int:
    library = _voice_library()
    root = library.ensure()
    profiles = library.list_profiles()
    print(f"Voice reference library: {root}")
    if not profiles:
        print("No saved voice profiles yet.")
        print("Use --save-voice-profile with --voice-ref to add one.")
        return 0
    for profile in profiles:
        print(
            f"[{profile.profile_id}] {profile.display_name} | "
            f"references={len(profile.references)} | primary={profile.primary_reference_id}"
        )
        for reference in profile.references:
            marker = "*" if reference.reference_id == profile.primary_reference_id else " "
            transcript = "transcript=yes" if reference.transcript else "transcript=no"
            print(
                f"  {marker} {reference.reference_id} | {reference.language} | "
                f"{transcript} | {reference.relative_audio_path}"
            )
    return 0


def _save_voice_profile(args: argparse.Namespace) -> int:
    if not args.voice_ref:
        raise ValueError("--save-voice-profile requires --voice-ref")
    library = _voice_library()
    profile = library.add_reference(
        display_name=args.save_voice_profile,
        source_audio=Path(args.voice_ref),
        transcript=args.voice_ref_text,
        language=args.voice_language,
        profile_id=args.voice_profile_id,
        provider_hint=args.tts_provider,
        make_primary=not args.keep_primary_reference,
    )
    print(f"Saved voice profile: [{profile.profile_id}] {profile.display_name}")
    print(f"Library: {library.root}")
    print(f"References: {len(profile.references)} | primary={profile.primary_reference_id}")
    print(
        "Use it with: python -m apps.voice_lab --turns 3 "
        f"--tts-provider {args.tts_provider} --voice-profile {profile.profile_id}"
    )
    return 0


def _apply_voice_profile(args: argparse.Namespace) -> VoiceProfile | None:
    if not args.voice_profile:
        return None
    profile = _voice_library().resolve_voice_profile(
        args.voice_profile,
        reference_id=args.voice_reference_id,
        provider_hint=args.tts_provider,
    )
    args.voice_ref = profile.reference_audio_path
    args.voice_ref_text = profile.settings.get("reference_text")
    args.voice_language = str(profile.settings.get("language") or args.voice_language)
    if profile.settings.get("x_vector_only"):
        args.qwen_xvector_only = True
    return profile


def _tts_provider_from_args(args: argparse.Namespace | None = None):
    provider_name = getattr(args, "tts_provider", "chatterbox") if args is not None else "chatterbox"
    if provider_name == "qwen3":
        return Qwen3TTSProvider(Qwen3TTSConfig.from_env(env_file=PROJECT_ROOT / ".env"))
    if provider_name == "qwen3-streaming":
        fixed_seed = getattr(args, "qwen_fixed_seed", None) if args is not None else None
        return Qwen3StreamingProvider(Qwen3StreamingConfig(fixed_seed=fixed_seed))
    return ChatterboxTurboProvider(ChatterboxConfig.from_env(env_file=PROJECT_ROOT / ".env"))


def _qwen_doctor_payload() -> dict[str, object]:
    provider = Qwen3TTSProvider(Qwen3TTSConfig.from_env(env_file=PROJECT_ROOT / ".env"))
    cfg = provider.config
    return {
        "provider": provider.metadata.provider,
        "model": provider.metadata.model,
        "runtime_python_exists": cfg.python_executable.is_file(),
        "runtime_python": str(cfg.python_executable),
        "model_dir": str(cfg.model_dir),
        "model_assets_ready": (cfg.model_dir / "config.json").is_file() and (cfg.model_dir / "model.safetensors").is_file(),
        "device": cfg.device,
        "attention": cfg.attention,
    }


def doctor() -> int:
    stt = WhisperCppProvider(WhisperCppConfig.from_env(env_file=PROJECT_ROOT / ".env"))
    tts = ChatterboxTurboProvider(ChatterboxConfig.from_env(env_file=PROJECT_ROOT / ".env"))
    payload = {
        "version": (PROJECT_ROOT / "VERSION").read_text().strip(),
        "audio": {
            "sounddevice_installed": _present("sounddevice"),
            "webrtcvad_installed": _present("webrtcvad"),
            "saved_devices": _load_audio_preferences(),
        },
        "voice_reference_library": {
            "path": str(VOICE_REFERENCE_ROOT),
            "exists": VOICE_REFERENCE_ROOT.is_dir(),
            "profiles": len(_voice_library().list_profiles()),
        },
        "stt": {
            "provider": stt.metadata.provider,
            "model": stt.metadata.model,
            "server_exists": stt.config.server_executable.is_file(),
            "model_exists": stt.config.model_path.is_file(),
            "server": str(stt.config.server_executable),
            "model_path": str(stt.config.model_path),
        },
        "tts": {
            "selected_default": "chatterbox",
            "chatterbox": {
                "provider": tts.metadata.provider,
                "model": tts.metadata.model,
                "runtime_python_exists": tts.config.python_executable.is_file(),
                "runtime_python": str(tts.config.python_executable),
                "model_dir": str(tts.config.model_dir),
                "model_assets_ready": all(
                    (tts.config.model_dir / name).is_file()
                    for name in (
                        "ve.safetensors",
                        "t3_turbo_v1.safetensors",
                        "s3gen_meanflow.safetensors",
                        "tokenizer_config.json",
                        "vocab.json",
                        "merges.txt",
                        "special_tokens_map.json",
                        "added_tokens.json",
                        "conds.pt",
                    )
                ),
                "device": tts.config.device,
            },
            "qwen3": _qwen_doctor_payload(),
        },
        "note": "Doctor performs no model load, microphone capture, or network request.",
    }
    print(json.dumps(payload, indent=2))
    return 0


async def devices() -> int:
    source = SoundDeviceAudioInput()
    rows = await source.devices()
    for item in rows:
        host = f" | host={item.host_api}" if item.host_api else ""
        print(
            f"[{item.device_id}] {item.name} | in={item.max_input_channels} "
            f"out={item.max_output_channels} | native={item.default_sample_rate_hz or '-'} Hz{host}"
        )
    return 0


async def tts_diagnostic(args: argparse.Namespace) -> int:
    """Synthesize one provider clip to disk without speaker playback.

    This isolates TTS model/waveform correctness from PortAudio/output-device
    behavior.  The resulting WAV is the exact provider-neutral PCM stream Jarvis
    would otherwise send to the speaker integration.
    """

    tts = _tts_provider_from_args(args)
    profile = getattr(args, "resolved_voice_profile", None)
    if profile is None:
        profile = VoiceProfile(
            profile_id="tts-diagnostic",
            display_name="TTS Diagnostic",
            provider_hint=args.tts_provider,
            reference_audio_path=args.voice_ref,
            settings={
                "reference_text": args.voice_ref_text,
                "language": args.voice_language,
                "x_vector_only": bool(args.qwen_xvector_only),
            },
        )
    health = await tts.health()
    if not health.ready:
        print(f"TTS: {health.status} - {health.detail or ''}")
        await tts.close()
        return 2
    trace = CorrelationContext.create()
    token = CancellationToken()
    frames = []
    try:
        async for frame in tts.stream_speech(trace, args.tts_diagnostic_text, profile, token):
            frames.append(frame)
    finally:
        await tts.close()
    if not frames:
        raise RuntimeError("TTS diagnostic produced no audio frames")
    fmt = frames[0].format
    if fmt.channels != 1 or fmt.sample_format is not AudioSampleFormat.PCM_S16LE:
        raise RuntimeError(f"TTS diagnostic only supports mono PCM16; got {fmt}")
    for frame in frames[1:]:
        if frame.format != fmt:
            raise RuntimeError("TTS provider changed audio format within one diagnostic clip")
    root = PROJECT_ROOT / ".runtime" / "voice" / "diagnostics"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = root / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"tts_{args.tts_provider}.wav"
    _write_pcm16_wav(path, sample_rate_hz=fmt.sample_rate_hz, payload=b"".join(f.payload for f in frames))
    print(f"TTS diagnostic provider: {args.tts_provider}")
    print(f"Text: {args.tts_diagnostic_text}")
    payload_bytes = sum(len(frame.payload) for frame in frames)
    duration_ms = (payload_bytes / 2 / fmt.sample_rate_hz) * 1000.0
    print(
        f"Format: {fmt.sample_rate_hz} Hz | mono PCM16 | frames={len(frames)} | "
        f"duration={duration_ms:.1f} ms"
    )
    print(f"Saved exact provider output: {path}")
    print("Listen to this WAV before testing speaker playback.")
    return 0



async def qwen_clone_diagnostic(args: argparse.Namespace) -> int:
    """Validate one reference and run Qwen's direct upstream clone paths.

    This intentionally bypasses Jarvis chunking, cached voice prompts, speaker
    playback, and the normal TextToSpeechProvider streaming loop. It tells us
    whether a failure belongs to the reference/official Qwen clone call or to
    Jarvis's optimized adapter path.
    """

    profile = getattr(args, "resolved_voice_profile", None)
    if profile is None:
        profile = VoiceProfile(
            profile_id="qwen-clone-diagnostic",
            display_name="Qwen Clone Diagnostic",
            provider_hint="qwen3",
            reference_audio_path=args.voice_ref,
            settings={
                "reference_text": args.voice_ref_text,
                "language": args.voice_language,
            },
        )
    if not profile.reference_audio_path:
        raise ValueError("Qwen clone diagnostic requires a saved voice profile or --voice-ref")
    reference_text = profile.settings.get("reference_text")
    language = str(profile.settings.get("language") or args.voice_language or "English")

    provider = Qwen3TTSProvider(Qwen3TTSConfig.from_env(env_file=PROJECT_ROOT / ".env"))
    health = await provider.health()
    if not health.ready:
        print(f"Qwen: {health.status} - {health.detail or ''}")
        await provider.close()
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = PROJECT_ROOT / ".runtime" / "voice" / "diagnostics" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        metrics = await provider.diagnose_reference(
            reference_audio_path=profile.reference_audio_path,
            reference_text=str(reference_text) if reference_text else None,
        )
        print("Qwen reference validation:")
        print(f"  path: {metrics['path']}")
        print(
            f"  format: {metrics['format']}/{metrics['subtype']} | "
            f"{metrics['sample_rate']} Hz | channels={metrics['channels']} | "
            f"duration={metrics['duration_ms']:.1f} ms"
        )
        print(
            f"  peak={metrics['peak']:.6f} | rms={metrics['rms']:.6f} | "
            f"clipping={metrics['clipping_ratio']:.6f} | "
            f"near-silence={metrics['near_silence_ratio']:.3f}"
        )
        print(
            f"  reference transcript: words={metrics['reference_text_words']} "
            f"chars={metrics['reference_text_chars']}"
        )
        if metrics.get("warnings"):
            for warning in metrics["warnings"]:
                print(f"  WARNING: {warning}")
        else:
            print("  reference signal checks: PASS")

        results: dict[str, dict | None] = {"full": None, "xvector": None}
        errors: dict[str, str] = {}
        if reference_text:
            try:
                results["full"] = await provider.upstream_smoke(
                    text=args.tts_diagnostic_text,
                    reference_audio_path=profile.reference_audio_path,
                    reference_text=str(reference_text),
                    language=language,
                    x_vector_only=False,
                )
            except Exception as exc:
                errors["full"] = f"{type(exc).__name__}: {exc}"
        else:
            errors["full"] = "skipped: no saved reference transcript"

        try:
            results["xvector"] = await provider.upstream_smoke(
                text=args.tts_diagnostic_text,
                reference_audio_path=profile.reference_audio_path,
                reference_text=None,
                language=language,
                x_vector_only=True,
            )
        except Exception as exc:
            errors["xvector"] = f"{type(exc).__name__}: {exc}"

        plausible = 0
        for key, label in (("full", "full-reference-text"), ("xvector", "x-vector-only")):
            result = results[key]
            if result is None:
                print(f"{label}: {errors.get(key, 'not run')}")
                continue
            source = Path(str(result["path"]))
            destination = out_dir / f"qwen_upstream_{key}.wav"
            shutil.copy2(source, destination)
            try:
                source.unlink(missing_ok=True)
            except OSError:
                pass
            print(
                f"{label}: duration={float(result['duration_ms']):.1f} ms | "
                f"peak={float(result['waveform_peak']):.6f} | "
                f"rms={float(result['waveform_rms']):.6f} | "
                f"plausible={bool(result['plausible'])}"
            )
            print(f"  saved: {destination}")
            if result["plausible"]:
                plausible += 1

        if plausible == 2:
            print("Diagnosis: Qwen's direct upstream clone paths both produce plausible audio.")
            print("The remaining failure is in Jarvis's cached/optimized Qwen adapter path.")
            return 0
        if results["xvector"] and results["xvector"].get("plausible") and not (
            results["full"] and results["full"].get("plausible")
        ):
            print("Diagnosis: x-vector cloning works but full transcript-conditioned cloning does not.")
            print("Check the reference transcript for an exact match and the ICL/reference-code path.")
            return 0
        print("Diagnosis: direct upstream-style Qwen generation is still failing or producing tiny audio.")
        print("If the reference checks above are clean, the runtime/model combination is the leading cause.")
        return 1
    finally:
        await provider.close()


async def provider_health(args: argparse.Namespace) -> int:
    stt = WhisperCppProvider(WhisperCppConfig.from_env(env_file=PROJECT_ROOT / ".env"))
    tts = _tts_provider_from_args(args)
    stt_health = await stt.health()
    tts_health = await tts.health()
    print(f"STT: {stt_health.status} - {stt_health.detail or ''}")
    print(f"TTS: {tts_health.status} - {tts_health.detail or ''}")
    await stt.close()
    await tts.close()
    return 0 if stt_health.ready and tts_health.ready else 2


async def mic_test(args: argparse.Namespace) -> int:
    source = SoundDeviceAudioInput(args.input_device)
    info = await source.selected_device()
    if info.max_input_channels < 1:
        raise RuntimeError(f"Selected device [{info.device_id}] {info.name!r} has no input channels")
    print(
        f"Mic test input: [{info.device_id}] {info.name} | host={info.host_api or 'unknown'} | "
        f"native={info.default_sample_rate_hz or '-'} Hz -> Jarvis=16000 Hz"
    )
    print(f"Speak for {args.mic_test_seconds:.1f} seconds. A moving meter confirms this exact endpoint is live.")
    token = CancellationToken()
    trace = CorrelationContext.create()
    started = monotonic()
    window_peak = 0.0
    next_print = started + 0.25
    frames = 0
    async for frame in source.stream(
        trace=trace,
        audio_format=VOICE_INPUT_FORMAT,
        frame_ms=30,
        cancellation_token=token,
    ):
        frames += 1
        window_peak = max(window_peak, pcm16_rms(frame.payload))
        now = monotonic()
        if now >= next_print:
            bars = min(40, round(window_peak * 100))
            print(f"level [{'#' * bars}{'.' * (40 - bars)}] {window_peak:.3f}")
            window_peak = 0.0
            next_print = now + 0.25
        if now - started >= args.mic_test_seconds:
            token.cancel("mic test complete")
            break
    return 0 if frames else 2


def _write_pcm16_wav(path: Path, *, sample_rate_hz: int, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate_hz)
        handle.writeframes(payload)


async def audio_diagnostic(args: argparse.Namespace) -> int:
    """Capture/listenable raw + resampled audio and the exact accepted STT bytes."""

    source = SoundDeviceAudioInput(args.input_device)
    info = await source.selected_device()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = (
        Path(args.audio_diagnostic_dir).expanduser().resolve()
        if args.audio_diagnostic_dir
        else PROJECT_ROOT / ".runtime" / "voice" / "diagnostics" / stamp
    )
    print(
        f"Audio diagnostic input: [{info.device_id}] {info.name} | host={info.host_api or 'unknown'} | "
        f"native={info.default_sample_rate_hz or '-'} Hz -> Jarvis=16000 Hz"
    )
    print(
        f"Capturing {args.audio_diagnostic_seconds:.1f}s. Stay quiet for ~1s, say one normal sentence, "
        "then stay quiet again."
    )
    capture = await source.capture_diagnostic(
        duration_s=args.audio_diagnostic_seconds,
        audio_format=VOICE_INPUT_FORMAT,
        frame_ms=30,
    )

    raw_path = output_dir / "1_raw_device.wav"
    resampled_path = output_dir / "2_resampled_16k.wav"
    whisper_path = output_dir / "3_whisper_input.wav"
    manifest_path = output_dir / "manifest.json"
    _write_pcm16_wav(
        raw_path,
        sample_rate_hz=capture.native_sample_rate_hz,
        payload=capture.raw_native_pcm16,
    )
    _write_pcm16_wav(
        resampled_path,
        sample_rate_hz=VOICE_INPUT_FORMAT.sample_rate_hz,
        payload=b"".join(frame.payload for frame in capture.processed_frames),
    )

    endpoint_config = EndpointConfig(end_silence_ms=args.end_silence_ms)
    endpoint = EndpointDetector(endpoint_config)
    gate = SpeechEvidenceGate(
        frame_ms=endpoint_config.frame_ms,
        preroll_frames=max(1, endpoint_config.preroll_ms // endpoint_config.frame_ms),
    )
    vad = WebRtcVadDetector(args.vad)
    reports: list[dict[str, object]] = []
    accepted = None
    for frame in capture.processed_frames:
        is_speech = vad.is_speech(frame)
        signal = endpoint.accept(is_speech)
        candidate = gate.push(frame, is_speech, signal)
        if candidate is None:
            continue
        reports.append(candidate.report.as_dict())
        if candidate.report.accepted:
            accepted = candidate
            break
        endpoint.reset()

    if accepted is not None:
        _write_pcm16_wav(
            whisper_path,
            sample_rate_hz=VOICE_INPUT_FORMAT.sample_rate_hz,
            payload=b"".join(frame.payload for frame in accepted.frames),
        )

    payload = {
        "input_device": {
            "id": info.device_id,
            "name": info.name,
            "host_api": info.host_api,
            "native_sample_rate_hz": capture.native_sample_rate_hz,
        },
        "jarvis_sample_rate_hz": VOICE_INPUT_FORMAT.sample_rate_hz,
        "capture_seconds": args.audio_diagnostic_seconds,
        "candidate_reports": reports,
        "accepted_for_stt": accepted is not None,
        "files": {
            "raw_device": str(raw_path),
            "resampled_16k": str(resampled_path),
            "whisper_input": str(whisper_path) if accepted is not None else None,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Diagnostic files: {output_dir}")
    print(f"  raw device:      {raw_path.name}")
    print(f"  resampled 16k:   {resampled_path.name}")
    if accepted is not None:
        print(f"  exact STT input: {whisper_path.name}")
        print("Speech evidence: ACCEPTED for STT")
        print(json.dumps(accepted.report.as_dict(), indent=2))
        return 0
    print("  exact STT input: not created (no candidate passed speech evidence)")
    print("Speech evidence: REJECTED; Whisper would receive no audio.")
    if reports:
        print(json.dumps(reports[-1], indent=2))
    return 3


def build_engine(args: argparse.Namespace):
    intelligence_config = OpenAIProviderConfig.from_env(env_file=PROJECT_ROOT / ".env")
    intelligence_config = replace(intelligence_config, voice_transport=args.luna_transport)
    intelligence = OpenAIProvider(intelligence_config)
    core = ConversationCore(
        context=ConversationContext.create(
            user_id="local-development-user",
            speaker_id="voice-lab-user",
            device_id="voice-lab",
        ),
        provider=intelligence,
    )
    stt = WhisperCppProvider(WhisperCppConfig.from_env(env_file=PROJECT_ROOT / ".env"))
    tts = _tts_provider_from_args(args)
    profile = getattr(args, "resolved_voice_profile", None)
    if profile is None:
        profile = VoiceProfile(
            profile_id="voice-lab",
            display_name="Voice Lab",
            provider_hint=args.tts_provider,
            reference_audio_path=args.voice_ref,
            settings={
                "reference_text": args.voice_ref_text,
                "language": args.voice_language,
                "x_vector_only": bool(args.qwen_xvector_only),
            },
        )
    engine = VoiceLabEngine(
        conversation=core,
        providers=VoiceProviderRegistry(stt=stt, tts=tts),
        audio_input=SoundDeviceAudioInput(args.input_device),
        audio_output=SoundDeviceAudioOutput(args.output_device),
        vad=WebRtcVadDetector(args.vad),
        endpoint_config=EndpointConfig(end_silence_ms=args.end_silence_ms),
        voice=profile,
        tts_response_mode=args.tts_response_mode,
    )
    return engine, stt, tts


async def _print_selected_audio(engine: VoiceLabEngine) -> None:
    input_getter = getattr(engine.audio_input, "selected_device", None)
    output_getter = getattr(engine.audio_output, "selected_device", None)
    if callable(input_getter):
        info = await input_getter()
        print(
            f"Input:  [{info.device_id}] {info.name} | host={info.host_api or 'unknown'} | "
            f"native={info.default_sample_rate_hz or '-'} Hz -> Jarvis=16000 Hz"
        )
    if callable(output_getter):
        info = await output_getter()
        print(
            f"Output: [{info.device_id}] {info.name} | host={info.host_api or 'unknown'} | "
            f"native={info.default_sample_rate_hz or '-'} Hz"
        )


async def _prewarm_voice(engine: VoiceLabEngine, stt, tts) -> None:
    started = monotonic()
    print("Preparing providers before listening (moves cold-start work out of the response path)...")
    stt_health, tts_health = await asyncio.gather(stt.health(), tts.health())
    if not stt_health.ready:
        raise RuntimeError(f"STT is not ready: {stt_health.status} - {stt_health.detail or ''}")
    if not tts_health.ready:
        raise RuntimeError(f"TTS is not ready: {tts_health.status} - {tts_health.detail or ''}")

    # whisper-server startup loads the model, but the first actual GPU inference
    # can still pay CUDA/kernel setup. Warm that inference before listening.
    stt_warmup = getattr(stt, "warmup", None)
    if callable(stt_warmup):
        stt_started = monotonic()
        await stt_warmup()
        print(f"STT inference warmup completed in {monotonic() - stt_started:.2f}s (output discarded).")

    # Health checks load TTS models, but CUDA/JIT kernels and clone-prompt caches
    # can still be cold until the first real synthesis. Native resident providers
    # may expose a stronger warmup that prepares the voice + compiled streaming
    # path without routing hidden PCM through Core. Other providers retain the
    # existing tiny synthesis warmup.
    tts_started = monotonic()
    provider_warmup = getattr(tts, "warmup", None)
    if callable(provider_warmup):
        await provider_warmup(engine.voice)
        print(f"TTS resident warmup completed in {monotonic() - tts_started:.2f}s (output discarded).")
        if tts.metadata.provider == "qwen3-tts-streaming-candidate":
            seed = tts.metadata.extra.get("fixed_seed")
            strategy = tts.metadata.extra.get("seed_strategy")
            print(f"Qwen streaming RNG: fixed_seed={seed} | strategy={strategy}")
    else:
        warm_trace = CorrelationContext.create()
        warm_token = CancellationToken()
        warm_bytes = 0
        async for frame in tts.stream_speech(warm_trace, "Ready.", engine.voice, warm_token):
            warm_bytes += len(frame.payload)
        if warm_bytes <= 0:
            raise RuntimeError("TTS inference warmup produced no audio")
        print(f"TTS inference warmup completed in {monotonic() - tts_started:.2f}s ({warm_bytes} bytes discarded).")

    # Warm the intelligence provider's HTTP/TLS connection without mutating the
    # authoritative ConversationContext. This is a tiny provider-neutral request
    # whose output is discarded before Jarvis begins listening.
    intelligence_started = monotonic()
    probe_context = IntelligenceContext(
        trace=CorrelationContext.create(),
        messages=(
            {"role": "developer", "content": VOICE_RESPONSE_INSTRUCTION},
            {"role": "user", "content": "Reply with exactly one word: Ready."},
        ),
        metadata={"input_channel": "voice", "conversation_id": "voice-lab-prewarm"},
    )
    probe_token = CancellationToken()
    first_text_ms = None
    async for event in engine.conversation.provider.stream_response(
        probe_context, (), ReasoningPolicy(level="none", allow_escalation=False), probe_token
    ):
        if event.event_type is IntelligenceEventType.TEXT_DELTA and first_text_ms is None:
            first_text_ms = (monotonic() - intelligence_started) * 1000.0
    elapsed_ms = (monotonic() - intelligence_started) * 1000.0
    first_label = f"{first_text_ms:.0f} ms TTFT" if first_text_ms is not None else "no text delta"
    transport = getattr(engine.conversation.provider.config, "voice_transport", "http")
    print(
        f"Luna {transport} warmup completed in {elapsed_ms:.0f} ms "
        f"({first_label}; output discarded)."
    )
    print(f"Providers ready in {monotonic() - started:.2f}s. They remain resident for this session.")


def _print_timing_summary(marks: dict[str, float]) -> None:
    pairs = (
        ("endpoint -> STT final", "speech_ended", "stt_final"),
        ("STT final -> Luna first text", "stt_final", "luna_first_text"),
        ("Luna first text -> Luna response complete", "luna_first_text", "luna_response_complete"),
        ("Luna response complete -> TTS request", "luna_response_complete", "tts_first_request_started"),
        ("Luna first text -> first speech chunk", "luna_first_text", "speech_first_chunk_ready"),
        ("first speech chunk -> TTS request", "speech_first_chunk_ready", "tts_first_request_started"),
        ("TTS request -> first waveform", "tts_first_request_started", "tts_first_waveform_ready"),
        ("first waveform -> startup buffer ready", "tts_first_waveform_ready", "audio_startup_buffer_ready"),
        ("startup buffer ready -> first PCM write", "audio_startup_buffer_ready", "audio_first_write_started"),
        ("first PCM write -> estimated audible audio", "audio_first_write_started", "audio_first_played"),
        ("first PCM write blocking duration", "audio_first_write_started", "audio_first_write_completed"),
        ("first waveform -> estimated audible audio", "tts_first_waveform_ready", "audio_first_played"),
        # Keep the legacy label for regression compatibility; Repair26 changes
        # its timestamp source to the PortAudio latency estimate.
        ("speech end -> first audible audio", "speech_ended", "audio_first_played"),
    )
    print("Turn timing summary:")
    for label, start, end in pairs:
        if start in marks and end in marks:
            print(f"  {label}: {max(0.0, marks[end] - marks[start]):.1f} ms")


async def run_session(args: argparse.Namespace) -> int:
    engine, stt, tts = build_engine(args)

    def on_rejected(event) -> None:
        payload = dict(event.payload)
        print(
            "Ignored non-speech candidate "
            f"(reason={payload.get('reason', 'unknown')}, "
            f"vad={payload.get('vad_speech_ms', '?')}ms, "
            f"peak={payload.get('peak_rms', '?')}). Listening continues..."
        )

    def on_acoustic_rescue(event) -> None:
        payload = dict(event.payload)
        print(
            "Acoustic speech rescue engaged "
            f"(VAD missed onset; rms={payload.get('rms', '?')}, "
            f"threshold={payload.get('threshold', '?')})."
        )

    unsubscribe_rejected = engine.conversation.event_bus.subscribe("voice.speech.rejected", on_rejected)
    unsubscribe_rescue = engine.conversation.event_bus.subscribe("voice.speech.acoustic_rescue", on_acoustic_rescue)
    try:
        await _print_selected_audio(engine)
        print(f"TTS response mode: {args.tts_response_mode}")
        if not args.no_prewarm:
            await _prewarm_voice(engine, stt, tts)

        completed = 0
        for turn_number in range(1, args.turns + 1):
            if args.turns > 1:
                print(f"\n--- Voice Lab turn {turn_number}/{args.turns} ---")
            print("Listening... speak naturally. Jarvis will answer after the endpoint is detected.")
            result = await engine.run_once(
                reasoning_policy=ReasoningPolicy(level=args.reasoning, allow_escalation=False)
            )
            print(f"You: {result.transcript}")
            print(f"Jarvis: {result.response_text}")
            print(f"Status: {result.status} | turn={result.turn_id}")
            print("Latency marks (ms from first mark):")
            print(json.dumps(result.latency_ms, indent=2))
            _print_timing_summary(result.latency_ms)
            if result.speech_metrics:
                print(
                    "Speech chunk: "
                    f"first={result.speech_metrics.get('first_chunk_words', 0)} words / "
                    f"{result.speech_metrics.get('first_chunk_chars', 0)} chars"
                )
                if "whole_response_words" in result.speech_metrics:
                    print(
                        "Whole-response TTS unit: "
                        f"{result.speech_metrics.get('whole_response_words', 0)} words / "
                        f"{result.speech_metrics.get('whole_response_chars', 0)} chars"
                    )
            print(
                f"Playback: queued={result.playback.queued_bytes} bytes, "
                f"played={result.playback.played_bytes} bytes, unheard={result.playback.unheard_bytes}"
            )
            if result.status != "completed":
                return 1
            completed += 1
        return 0 if completed == args.turns else 1
    finally:
        unsubscribe_rejected()
        unsubscribe_rescue()
        await stt.close()
        await tts.close()
        provider_close = getattr(engine.conversation.provider, "close", None)
        if callable(provider_close):
            await provider_close()


async def _main(args: argparse.Namespace) -> int:
    if args.doctor:
        return doctor()
    if args.devices:
        return await devices()
    if args.save_devices:
        _save_audio_preferences(args.input_device, args.output_device)
        print(f"Saved audio preferences to {AUDIO_PREFS_PATH}")
        return 0
    if args.voice_library:
        return _list_voice_library()
    if args.save_voice_profile:
        return _save_voice_profile(args)
    _apply_saved_devices(args)
    args.resolved_voice_profile = _apply_voice_profile(args)
    if args.mic_test:
        return await mic_test(args)
    if args.audio_diagnostic:
        return await audio_diagnostic(args)
    if args.qwen_clone_diagnostic:
        return await qwen_clone_diagnostic(args)
    if args.tts_diagnostic:
        return await tts_diagnostic(args)
    if args.provider_health:
        return await provider_health(args)
    return await run_session(args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jarvis Core v2 0.0.4 local Voice Lab")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--doctor", action="store_true", help="local configuration check; no model load/network")
    mode.add_argument("--devices", action="store_true", help="list local audio devices with host API/native rate")
    mode.add_argument("--provider-health", action="store_true", help="load/probe local STT and TTS runtimes")
    mode.add_argument("--tts-diagnostic", action="store_true", help="synthesize one TTS clip to WAV without speaker playback")
    mode.add_argument("--qwen-clone-diagnostic", action="store_true", help="validate the Qwen reference and run direct upstream full/x-vector clone smoke tests")
    mode.add_argument("--mic-test", action="store_true", help="meter one selected microphone without STT/Luna/TTS")
    mode.add_argument("--audio-diagnostic", action="store_true", help="save raw/resampled/exact-STT WAVs and speech-evidence metrics")
    mode.add_argument("--save-devices", action="store_true", help="persist explicit input/output IDs under ignored .runtime")
    mode.add_argument("--voice-library", action="store_true", help="create/list named local voice reference profiles")
    mode.add_argument("--save-voice-profile", metavar="NAME", help="copy --voice-ref into the private voice library as a named profile")
    parser.add_argument("--input-device", type=int)
    parser.add_argument("--output-device", type=int)
    parser.add_argument("--mic-test-seconds", type=float, default=5.0)
    parser.add_argument("--audio-diagnostic-seconds", type=float, default=8.0)
    parser.add_argument("--audio-diagnostic-dir", help="optional output directory for diagnostic WAVs")
    parser.add_argument("--voice-ref", help="optional local reference clip for TTS voice cloning")
    parser.add_argument("--voice-ref-text", help="exact transcript of --voice-ref; improves Qwen clone fidelity")
    parser.add_argument("--voice-profile", help="saved voice profile ID from --voice-library")
    parser.add_argument("--voice-reference-id", help="optional reference ID within --voice-profile; defaults to its primary reference")
    parser.add_argument("--voice-profile-id", help="optional stable ID when creating/updating --save-voice-profile")
    parser.add_argument("--keep-primary-reference", action="store_true", help="when adding another clip to an existing profile, keep the previous primary reference")
    parser.add_argument("--voice-language", default="English", help="target TTS language (default: English)")
    parser.add_argument("--tts-diagnostic-text", default="Jarvis voice diagnostic. This sentence should sound clear and natural.")
    parser.add_argument("--tts-provider", default="chatterbox", choices=["chatterbox", "qwen3", "qwen3-streaming"], help="local TTS adapter to A/B test")
    parser.add_argument("--qwen-xvector-only", action="store_true", help="Qwen clone without reference transcript; faster setup, potentially lower likeness")
    parser.add_argument(
        "--qwen-fixed-seed",
        type=int,
        default=None,
        help=(
            "Repair31 A/B: reset the same RNG seed before each separate Qwen synthesis request. "
            "Omit this option to preserve Repair27's original random sampling."
        ),
    )
    parser.add_argument("--vad", type=int, default=2, choices=[0, 1, 2, 3])
    parser.add_argument("--end-silence-ms", type=int, default=360)
    parser.add_argument(
        "--tts-response-mode",
        choices=["streaming", "whole"],
        default="streaming",
        help=(
            "Repair33 A/B: 'streaming' preserves Repair31 separate-chunk TTS; "
            "'whole' waits for Luna's complete natural response and sends one Qwen request."
        ),
    )
    parser.add_argument("--no-prewarm", action="store_true", help="debug only: include local model startup in turn latency")
    parser.add_argument(
        "--luna-transport",
        choices=["websocket", "http"],
        default="websocket",
        help="voice-only Luna transport; websocket keeps one Responses connection/session warm",
    )
    parser.add_argument(
        "--turns",
        type=int,
        default=1,
        help="number of half-duplex voice turns to run in one warm provider/session process",
    )
    parser.add_argument(
        "--reasoning",
        default="none",
        choices=["none", "quick", "standard", "high", "extreme"],
    )
    args = parser.parse_args(argv)
    if args.qwen_clone_diagnostic:
        args.tts_provider = "qwen3"
    if args.mic_test_seconds <= 0:
        parser.error("--mic-test-seconds must be positive")
    if args.audio_diagnostic_seconds <= 0:
        parser.error("--audio-diagnostic-seconds must be positive")
    if args.turns <= 0:
        parser.error("--turns must be positive")
    if args.qwen_fixed_seed is not None and not 0 <= args.qwen_fixed_seed <= 0xFFFFFFFF:
        parser.error("--qwen-fixed-seed must be between 0 and 4294967295")
    if args.save_devices and args.input_device is None and args.output_device is None:
        parser.error("--save-devices requires --input-device and/or --output-device")
    if args.save_voice_profile and not args.voice_ref:
        parser.error("--save-voice-profile requires --voice-ref")
    if args.voice_reference_id and not args.voice_profile:
        parser.error("--voice-reference-id requires --voice-profile")
    if args.voice_profile and args.voice_ref:
        parser.error("use either --voice-profile or --voice-ref, not both")
    if args.qwen_clone_diagnostic and not args.voice_profile and not args.voice_ref:
        parser.error("--qwen-clone-diagnostic requires --voice-profile or --voice-ref")
    if args.tts_provider in {"qwen3", "qwen3-streaming"} and not (
        args.doctor
        or args.devices
        or args.provider_health
        or args.mic_test
        or args.audio_diagnostic
        or args.save_devices
        or args.voice_library
        or args.save_voice_profile
    ):
        if not args.voice_ref and not args.voice_profile:
            parser.error(f"--tts-provider {args.tts_provider} requires --voice-profile or --voice-ref for the 0.6B Base clone model")
        if args.tts_provider == "qwen3" and args.voice_ref and not args.voice_ref_text and not args.qwen_xvector_only:
            parser.error("Qwen full clone requires --voice-ref-text; use --qwen-xvector-only only for a transcript-free test")
    try:
        return asyncio.run(_main(args))
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
