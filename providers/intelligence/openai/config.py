"""OpenAI-specific configuration. Core code must never import this module."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_TIMEOUT_SECONDS = 60.0


def load_env_file(path: str | Path) -> dict[str, str]:
    """Read a small dotenv-compatible subset without adding a runtime dependency.

    Existing process environment values always win. This helper intentionally
    supports only KEY=VALUE, optional single/double quotes, comments, and blank
    lines; it never expands commands or variables.
    """

    values: dict[str, str] = {}
    file_path = Path(path)
    if not file_path.is_file():
        return values
    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def merged_environment(env_file: str | Path | None = None) -> dict[str, str]:
    merged: dict[str, str] = {}
    if env_file is not None:
        merged.update(load_env_file(env_file))
    merged.update(os.environ)
    return merged


@dataclass(frozen=True, slots=True)
class OpenAIProviderConfig:
    api_key: str | None
    model: str = DEFAULT_MODEL
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    base_url: str | None = None
    organization: str | None = None
    project: str | None = None
    store_responses: bool = False

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        env_file: str | Path | None = None,
    ) -> "OpenAIProviderConfig":
        source = dict(env) if env is not None else merged_environment(env_file)
        api_key = source.get("OPENAI_API_KEY") or None
        if api_key == "replace_me_in_local_env_only":
            api_key = None
        model = source.get("JARVIS_OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        reasoning = source.get("JARVIS_OPENAI_REASONING_EFFORT", DEFAULT_REASONING_EFFORT).strip().lower()
        if reasoning not in {"none", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError(f"Unsupported JARVIS_OPENAI_REASONING_EFFORT={reasoning!r}")
        max_output = int(source.get("JARVIS_OPENAI_MAX_OUTPUT_TOKENS", str(DEFAULT_MAX_OUTPUT_TOKENS)))
        if max_output <= 0:
            raise ValueError("JARVIS_OPENAI_MAX_OUTPUT_TOKENS must be positive")
        timeout = float(source.get("JARVIS_OPENAI_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
        if timeout <= 0:
            raise ValueError("JARVIS_OPENAI_TIMEOUT_SECONDS must be positive")
        return cls(
            api_key=api_key,
            model=model,
            reasoning_effort=reasoning,
            max_output_tokens=max_output,
            timeout_seconds=timeout,
            base_url=source.get("OPENAI_BASE_URL") or None,
            organization=source.get("OPENAI_ORG_ID") or None,
            project=source.get("OPENAI_PROJECT_ID") or None,
            store_responses=False,
        )
