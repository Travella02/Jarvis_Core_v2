"""OpenAI GPT-Live provider configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from providers.intelligence.openai.config import merged_environment


DEFAULT_LIVE_MODEL = "gpt-live-1"
DEFAULT_LIVE_VOICE = "meridian"
DEFAULT_LIVE_URL = "wss://api.openai.com/v1/live/sessions"
DEFAULT_WEBRTC_URL = "https://api.openai.com/v1/live/sessions"
DEFAULT_AUDIO_RATE_HZ = 24_000


@dataclass(frozen=True, slots=True)
class OpenAIGPTLiveConfig:
    api_key: str | None
    model: str = DEFAULT_LIVE_MODEL
    voice: str = DEFAULT_LIVE_VOICE
    url: str = DEFAULT_LIVE_URL
    audio_rate_hz: int = DEFAULT_AUDIO_RATE_HZ
    webrtc_url: str = DEFAULT_WEBRTC_URL
    open_timeout_seconds: float = 20.0
    close_timeout_seconds: float = 15.0

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        env_file: str | Path | None = None,
    ) -> "OpenAIGPTLiveConfig":
        source = dict(env) if env is not None else merged_environment(env_file)
        key = source.get("OPENAI_API_KEY") or None
        if key == "replace_me_in_local_env_only":
            key = None
        model = source.get("JARVIS_GPT_LIVE_MODEL", DEFAULT_LIVE_MODEL).strip() or DEFAULT_LIVE_MODEL
        voice = source.get("JARVIS_GPT_LIVE_VOICE", DEFAULT_LIVE_VOICE).strip() or DEFAULT_LIVE_VOICE
        url = source.get("JARVIS_GPT_LIVE_URL", DEFAULT_LIVE_URL).strip() or DEFAULT_LIVE_URL
        rate = int(source.get("JARVIS_GPT_LIVE_AUDIO_RATE_HZ", str(DEFAULT_AUDIO_RATE_HZ)))
        webrtc_url = source.get("JARVIS_GPT_LIVE_WEBRTC_URL", DEFAULT_WEBRTC_URL).strip() or DEFAULT_WEBRTC_URL
        if rate not in {16_000, 24_000}:
            raise ValueError("JARVIS_GPT_LIVE_AUDIO_RATE_HZ must be 16000 or 24000")
        open_timeout = float(source.get("JARVIS_GPT_LIVE_OPEN_TIMEOUT_SECONDS", "20"))
        close_timeout = float(source.get("JARVIS_GPT_LIVE_CLOSE_TIMEOUT_SECONDS", "15"))
        if open_timeout <= 0 or close_timeout <= 0:
            raise ValueError("GPT-Live timeouts must be positive")
        return cls(
            api_key=key,
            model=model,
            voice=voice,
            url=url,
            audio_rate_hz=rate,
            webrtc_url=webrtc_url,
            open_timeout_seconds=open_timeout,
            close_timeout_seconds=close_timeout,
        )
