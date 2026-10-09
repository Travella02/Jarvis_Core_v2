"""OpenAI Realtime voice-frontend configuration for Jarvis A/B testing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from providers.intelligence.openai.config import merged_environment


DEFAULT_REALTIME_MODEL = "gpt-realtime-2.1-mini"
DEFAULT_REALTIME_VOICE = "cedar"
DEFAULT_REALTIME_WEBRTC_URL = "https://api.openai.com/v1/realtime/calls"
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_INPUT_TRANSCRIPTION_MODEL = "gpt-realtime-whisper"
DEFAULT_DESKTOP_CONVERSATION_TRACE = True
_ALLOWED_REASONING = {"minimal", "low", "medium", "high", "xhigh"}
_ALLOWED_TRUE = {"1", "true", "yes", "on"}
_ALLOWED_FALSE = {"0", "false", "no", "off"}


@dataclass(frozen=True, slots=True)
class OpenAIRealtimeConfig:
    api_key: str | None
    model: str = DEFAULT_REALTIME_MODEL
    voice: str = DEFAULT_REALTIME_VOICE
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    webrtc_url: str = DEFAULT_REALTIME_WEBRTC_URL
    open_timeout_seconds: float = 20.0
    input_transcription_model: str = DEFAULT_INPUT_TRANSCRIPTION_MODEL
    desktop_conversation_trace: bool = DEFAULT_DESKTOP_CONVERSATION_TRACE

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        env_file: str | Path | None = None,
    ) -> "OpenAIRealtimeConfig":
        source = dict(env) if env is not None else merged_environment(env_file)
        key = source.get("OPENAI_API_KEY") or None
        if key == "replace_me_in_local_env_only":
            key = None
        model = source.get("JARVIS_REALTIME_MODEL", DEFAULT_REALTIME_MODEL).strip() or DEFAULT_REALTIME_MODEL
        voice = source.get("JARVIS_REALTIME_VOICE", DEFAULT_REALTIME_VOICE).strip() or DEFAULT_REALTIME_VOICE
        effort = source.get("JARVIS_REALTIME_REASONING_EFFORT", DEFAULT_REASONING_EFFORT).strip().lower() or DEFAULT_REASONING_EFFORT
        if effort not in _ALLOWED_REASONING:
            raise ValueError("JARVIS_REALTIME_REASONING_EFFORT must be minimal, low, medium, high, or xhigh")
        url = source.get("JARVIS_REALTIME_WEBRTC_URL", DEFAULT_REALTIME_WEBRTC_URL).strip() or DEFAULT_REALTIME_WEBRTC_URL
        timeout = float(source.get("JARVIS_REALTIME_OPEN_TIMEOUT_SECONDS", "20"))
        if timeout <= 0:
            raise ValueError("JARVIS_REALTIME_OPEN_TIMEOUT_SECONDS must be positive")
        transcription_model = (
            source.get("JARVIS_REALTIME_INPUT_TRANSCRIPTION_MODEL", DEFAULT_INPUT_TRANSCRIPTION_MODEL).strip()
            or DEFAULT_INPUT_TRANSCRIPTION_MODEL
        )
        trace_raw = source.get(
            "JARVIS_DESKTOP_CONVERSATION_TRACE",
            "1" if DEFAULT_DESKTOP_CONVERSATION_TRACE else "0",
        ).strip().lower()
        if trace_raw in _ALLOWED_TRUE:
            desktop_conversation_trace = True
        elif trace_raw in _ALLOWED_FALSE:
            desktop_conversation_trace = False
        else:
            raise ValueError("JARVIS_DESKTOP_CONVERSATION_TRACE must be a boolean value")
        return cls(
            api_key=key,
            model=model,
            voice=voice,
            reasoning_effort=effort,
            webrtc_url=url,
            open_timeout_seconds=timeout,
            input_transcription_model=transcription_model,
            desktop_conversation_trace=desktop_conversation_trace,
        )
