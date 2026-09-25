"""Thin replaceable adapter around the local WebRTC VAD algorithm."""

from __future__ import annotations

from core.voice import AudioSampleFormat, VoiceActivityDetector
from core.voice.contracts import AudioFrame


class WebRtcVadDetector(VoiceActivityDetector):
    def __init__(self, aggressiveness: int = 2) -> None:
        if aggressiveness not in {0, 1, 2, 3}:
            raise ValueError("aggressiveness must be 0..3")
        try:
            import webrtcvad
        except ImportError as exc:  # pragma: no cover - live dependency path
            raise RuntimeError(
                "webrtcvad-wheels is not installed; run the 0.0.4 dependency install"
            ) from exc
        self._vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, frame: AudioFrame) -> bool:
        fmt = frame.format
        if fmt.sample_format is not AudioSampleFormat.PCM_S16LE:
            raise ValueError("WebRTC VAD requires PCM_S16LE")
        if fmt.channels != 1:
            raise ValueError("WebRTC VAD requires mono audio")
        if fmt.sample_rate_hz not in {8000, 16000, 32000, 48000}:
            raise ValueError("WebRTC VAD requires 8/16/32/48 kHz audio")
        duration_ms = round(frame.duration_ms)
        if duration_ms not in {10, 20, 30}:
            raise ValueError("WebRTC VAD requires 10, 20, or 30 ms frames")
        return bool(self._vad.is_speech(frame.payload, fmt.sample_rate_hz))
