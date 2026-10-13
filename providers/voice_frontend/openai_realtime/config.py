"""OpenAI Realtime voice-frontend configuration for Jarvis A/B testing."""

from __future__ import annotations

from dataclasses import dataclass
import math
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


def _env_bool(value: str) -> bool:
    value = value.strip().lower()
    if value in _ALLOWED_TRUE:
        return True
    if value in _ALLOWED_FALSE:
        return False
    raise ValueError("JARVIS_PARALLEL_SHADOW_PROBE must be a boolean value")


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
    parallel_shadow_probe: bool = False
    direct_only_benchmark: bool = False
    tool_selection_probe: bool = False
    buffered_tool_probe: bool = False
    overlap_probe: bool = False
    decisions_shadow_probe: bool = False
    core_luna_probe: bool = False
    delegation_guidance_probe: bool = False  # 0.1.4.1 opt-in A/B only.
    luna_result_hold_seconds: float = 0.0  # Only explicit cancellation-test mode.

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
        hold_seconds = float(source.get("JARVIS_LUNA_RESULT_HOLD_SECONDS", "0"))
        if not math.isfinite(hold_seconds) or not 0 <= hold_seconds <= 20:
            raise ValueError("JARVIS_LUNA_RESULT_HOLD_SECONDS must be within 0..20")
        if hold_seconds and not _env_bool(source.get("JARVIS_CORE_LUNA_PROBE", "0")):
            raise ValueError("Luna test result hold requires JARVIS_CORE_LUNA_PROBE=1")
        return cls(
            api_key=key,
            model=model,
            voice=voice,
            reasoning_effort=effort,
            webrtc_url=url,
            open_timeout_seconds=timeout,
            input_transcription_model=transcription_model,
            desktop_conversation_trace=desktop_conversation_trace,
            parallel_shadow_probe=_env_bool(source.get("JARVIS_PARALLEL_SHADOW_PROBE", "0")),
            direct_only_benchmark=_env_bool(source.get("JARVIS_REALTIME_DIRECT_ONLY_BENCHMARK", "0")),
            tool_selection_probe=_env_bool(source.get("JARVIS_REALTIME_TOOL_SELECTION_PROBE", "0")),
            buffered_tool_probe=_env_bool(source.get("JARVIS_REALTIME_BUFFERED_TOOL_PROBE", "0")),
            overlap_probe=_env_bool(source.get("JARVIS_REALTIME_OVERLAP_PROBE", "0")),
            decisions_shadow_probe=_env_bool(source.get("JARVIS_DECISIONS_SHADOW_PROBE", "0")),
            core_luna_probe=_env_bool(source.get("JARVIS_CORE_LUNA_PROBE", "0")),
            delegation_guidance_probe=_env_bool(source.get("JARVIS_0141_DELEGATION_GUIDANCE", "0")),
            luna_result_hold_seconds=hold_seconds,
        )
