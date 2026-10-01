"""Configuration for the local whisper.cpp Voice Lab adapter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUNTIME = PROJECT_ROOT / ".runtime" / "voice" / "whisper_cpp"


def _environment(env: Mapping[str, str] | None = None, env_file: str | Path | None = None) -> dict[str, str]:
    values: dict[str, str] = {}
    if env_file is not None:
        path = Path(env_file)
        if path.is_file():
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key, value = key.strip(), value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
                    value = value[1:-1]
                if key:
                    values[key] = value
    if env is not None:
        values.update(env)
    else:
        values.update(os.environ)
    return values


def _runtime_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


@dataclass(frozen=True, slots=True)
class WhisperCppConfig:
    server_executable: Path
    model_path: Path
    host: str = "127.0.0.1"
    port: int = 18080
    language: str = "en"
    partial_interval_ms: int = 900
    min_partial_audio_ms: int = 900
    # Repair34 A/B. True preserves the existing rolling-partial behavior.
    # Voice Lab may disable it because Core already endpoints and evidence-gates
    # the entire utterance before this adapter sees any audio.
    emit_partials: bool = True
    # Repair4: let Whisper's own no-speech token suppress silence hallucinations
    # before transcript text can become a realtime user turn.
    suppress_non_speech: bool = True
    no_speech_threshold: float = 0.60
    threads: int = 8
    use_gpu: bool = True
    startup_timeout_s: float = 45.0

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise ValueError("host must be non-empty")
        if not 1 <= self.port <= 65535:
            raise ValueError("port must be 1..65535")
        if self.partial_interval_ms <= 0 or self.min_partial_audio_ms <= 0:
            raise ValueError("partial timing must be positive")
        if not 0.0 <= self.no_speech_threshold <= 1.0:
            raise ValueError("no_speech_threshold must be between 0 and 1")
        if self.threads <= 0:
            raise ValueError("threads must be positive")

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        env_file: str | Path | None = None,
    ) -> "WhisperCppConfig":
        source = _environment(env, env_file)
        exe_default = DEFAULT_RUNTIME / "bin" / ("whisper-server.exe" if os.name == "nt" else "whisper-server")
        model_default = DEFAULT_RUNTIME / "models" / "ggml-large-v3-turbo-q5_0.bin"
        return cls(
            server_executable=_runtime_path(source.get("JARVIS_WHISPER_SERVER_EXE", str(exe_default))),
            model_path=_runtime_path(source.get("JARVIS_WHISPER_MODEL", str(model_default))),
            host=source.get("JARVIS_WHISPER_HOST", "127.0.0.1"),
            port=int(source.get("JARVIS_WHISPER_PORT", "18080")),
            language=source.get("JARVIS_WHISPER_LANGUAGE", "en"),
            partial_interval_ms=int(source.get("JARVIS_WHISPER_PARTIAL_MS", "900")),
            min_partial_audio_ms=int(source.get("JARVIS_WHISPER_MIN_PARTIAL_MS", "900")),
            emit_partials=source.get("JARVIS_WHISPER_EMIT_PARTIALS", "1").strip().lower()
            not in {"0", "false", "no"},
            suppress_non_speech=source.get("JARVIS_WHISPER_SUPPRESS_NON_SPEECH", "1").strip().lower()
            not in {"0", "false", "no"},
            no_speech_threshold=float(source.get("JARVIS_WHISPER_NO_SPEECH_THRESHOLD", "0.60")),
            threads=int(source.get("JARVIS_WHISPER_THREADS", "8")),
            use_gpu=source.get("JARVIS_WHISPER_USE_GPU", "1").strip().lower() not in {"0", "false", "no"},
        )
