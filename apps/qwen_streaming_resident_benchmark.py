"""Repair23 resident Qwen streaming warm-request benchmark.

This benchmark keeps the experimental Qwen streaming model in one child
process, performs one warmup synthesis, then measures multiple hot requests
without reloading the model or restarting Python.
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
WORKER = PROJECT_ROOT / "providers" / "tts" / "qwen3_streaming_candidate" / "resident_benchmark.py"

DEFAULT_TEXT = (
    "A day on Venus is longer than its year. Venus takes 243 Earth days to "
    "rotate once, but only 225 days to orbit the Sun."
)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Measure hot first-chunk latency from one resident Qwen streaming process."
    )
    p.add_argument("--voice-profile", required=True)
    p.add_argument("--text", default=DEFAULT_TEXT)
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--emit-every-frames", type=int, default=4)
    p.add_argument("--decode-window-frames", type=int, default=80)
    p.add_argument("--no-playback", action="store_true")
    args = p.parse_args()

    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if not PYTHON.is_file():
        raise SystemExit(
            "Streaming candidate runtime is not installed. Run: "
            "powershell -ExecutionPolicy Bypass -File "
            "scripts/setup_qwen3_tts_streaming_candidate.ps1"
        )
    if not MODEL_DIR.is_dir():
        raise SystemExit(
            "Accepted Qwen model assets are missing; Repair23 reuses the existing Repair20 model."
        )

    profile = VoiceReferenceLibrary(VOICE_ROOT).resolve_voice_profile(
        args.voice_profile,
        provider_hint="qwen3-streaming-candidate",
    )
    reference_text = str(profile.settings.get("reference_text") or "")
    language = str(profile.settings.get("language") or "English")
    output_dir = RUNTIME_ROOT / "outputs" / "resident_benchmark"

    cmd = [
        str(PYTHON),
        str(WORKER),
        "--model-dir", str(MODEL_DIR),
        "--reference", str(profile.reference_audio_path),
        "--reference-text", reference_text,
        "--text", args.text,
        "--language", language,
        "--runs", str(args.runs),
        "--emit-every-frames", str(args.emit_every_frames),
        "--decode-window-frames", str(args.decode_window_frames),
        "--output-dir", str(output_dir),
    ]
    if args.no_playback:
        cmd.append("--no-playback")

    print("Repair23 resident benchmark only: accepted Repair20 provider is untouched.")
    print(f"Voice profile: {args.voice_profile} | language={language} | measured runs={args.runs}")
    print("Warmup: 1 full synthesis in the SAME worker process; audio discarded.")
    print(f"Measured text: {args.text}")
    return subprocess.call(cmd, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
