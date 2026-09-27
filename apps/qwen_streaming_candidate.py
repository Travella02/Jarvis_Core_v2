"""Repair22 isolated Qwen streaming candidate benchmark.

This does not alter Jarvis's accepted Qwen provider. It resolves an existing
Voice Lab profile, then launches the experimental runtime as a child process.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from core.voice import VoiceReferenceLibrary

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VOICE_ROOT = PROJECT_ROOT / ".runtime" / "voice" / "references"
RUNTIME_ROOT = PROJECT_ROOT / ".runtime" / "voice" / "qwen3_tts_streaming_candidate"
PYTHON = RUNTIME_ROOT / ".venv" / "Scripts" / "python.exe"
MODEL_DIR = PROJECT_ROOT / ".runtime" / "voice" / "qwen3_tts" / "models" / "Qwen3-TTS-12Hz-0.6B-Base"
WORKER = PROJECT_ROOT / "providers" / "tts" / "qwen3_streaming_candidate" / "worker.py"


def main() -> int:
    p = argparse.ArgumentParser(description="A/B benchmark true-streaming Qwen voice cloning without changing Jarvis live TTS.")
    p.add_argument("--voice-profile", required=True)
    p.add_argument("--text", default="A day on Venus is longer than its year. Venus takes 243 Earth days to rotate once, but only 225 days to orbit the Sun.")
    p.add_argument("--emit-every-frames", type=int, default=4)
    p.add_argument("--decode-window-frames", type=int, default=80)
    args = p.parse_args()

    if not PYTHON.is_file():
        raise SystemExit("Streaming candidate runtime is not installed. Run: powershell -ExecutionPolicy Bypass -File scripts\\setup_qwen3_tts_streaming_candidate.ps1")
    if not MODEL_DIR.is_dir():
        raise SystemExit("Accepted Qwen model assets are missing; Repair22 intentionally reuses the Repair20 model instead of downloading another copy.")

    profile = VoiceReferenceLibrary(VOICE_ROOT).resolve_voice_profile(args.voice_profile, provider_hint="qwen3-streaming-candidate")
    reference_text = str(profile.settings.get("reference_text") or "")
    language = str(profile.settings.get("language") or "English")
    output = RUNTIME_ROOT / "outputs" / f"{args.voice_profile}_streaming_candidate.wav"

    cmd = [
        str(PYTHON), str(WORKER),
        "--model-dir", str(MODEL_DIR),
        "--reference", str(profile.reference_audio_path),
        "--reference-text", reference_text,
        "--text", args.text,
        "--language", language,
        "--emit-every-frames", str(args.emit_every_frames),
        "--decode-window-frames", str(args.decode_window_frames),
        "--output", str(output),
    ]
    print("Repair22 candidate only: accepted Repair20 provider is untouched.")
    print(f"Voice profile: {args.voice_profile} | language={language}")
    print(f"Text: {args.text}")
    return subprocess.call(cmd, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
