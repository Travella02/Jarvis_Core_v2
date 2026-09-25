"""Configuration for the isolated local Qwen3-TTS 0.6B Base runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUNTIME = PROJECT_ROOT / ".runtime" / "voice" / "qwen3_tts"
DEFAULT_MODEL_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"


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
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
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
class Qwen3TTSConfig:
    python_executable: Path
    model_dir: Path = DEFAULT_RUNTIME / "models" / "Qwen3-TTS-12Hz-0.6B-Base"
    device: str = "cuda"
    dtype: str = "bfloat16"
    attention: str = "sdpa"
    frame_ms: int = 20
    startup_timeout_s: float = 240.0
    synthesis_timeout_s: float = 180.0

    def __post_init__(self) -> None:
        if self.device not in {"cuda", "cpu", "mps"}:
            raise ValueError("device must be cuda, cpu, or mps")
        if self.dtype not in {"float16", "bfloat16", "float32"}:
            raise ValueError("dtype must be float16, bfloat16, or float32")
        if self.attention not in {"sdpa", "eager", "flash_attention_2"}:
            raise ValueError("unsupported attention implementation")
        if self.frame_ms <= 0:
            raise ValueError("frame_ms must be positive")

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        env_file: str | Path | None = None,
    ) -> "Qwen3TTSConfig":
        source = _environment(env, env_file)
        if os.name == "nt":
            default_python = DEFAULT_RUNTIME / ".venv" / "Scripts" / "python.exe"
        else:
            default_python = DEFAULT_RUNTIME / ".venv" / "bin" / "python"
        default_model_dir = DEFAULT_RUNTIME / "models" / "Qwen3-TTS-12Hz-0.6B-Base"
        return cls(
            python_executable=_runtime_path(source.get("JARVIS_QWEN3_TTS_PYTHON", str(default_python))),
            model_dir=_runtime_path(source.get("JARVIS_QWEN3_TTS_MODEL_DIR", str(default_model_dir))),
            device=source.get("JARVIS_QWEN3_TTS_DEVICE", "cuda").strip().lower(),
            dtype=source.get("JARVIS_QWEN3_TTS_DTYPE", "bfloat16").strip().lower(),
            attention=source.get("JARVIS_QWEN3_TTS_ATTENTION", "sdpa").strip().lower(),
            frame_ms=int(source.get("JARVIS_QWEN3_TTS_FRAME_MS", "20")),
        )
