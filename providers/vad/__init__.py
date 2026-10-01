"""Replaceable local voice-activity providers."""

from providers.vad.silero_whisper_cpp import SileroVadConfig, WhisperCppSileroVadDetector

__all__ = ["SileroVadConfig", "WhisperCppSileroVadDetector"]
