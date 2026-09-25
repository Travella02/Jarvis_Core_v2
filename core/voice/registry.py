"""Replaceable provider registry for speech engines."""

from __future__ import annotations

from dataclasses import dataclass

from core.voice.contracts import SpeechToTextProvider, TextToSpeechProvider


@dataclass(slots=True)
class VoiceProviderRegistry:
    stt: SpeechToTextProvider
    tts: TextToSpeechProvider

    def replace_stt(self, provider: SpeechToTextProvider) -> SpeechToTextProvider:
        previous = self.stt
        self.stt = provider
        return previous

    def replace_tts(self, provider: TextToSpeechProvider) -> TextToSpeechProvider:
        previous = self.tts
        self.tts = provider
        return previous
