"""Provider-neutral contracts and orchestration owned by the ORVEX Voice Engine."""

from .audio import AudioDeviceInfo, AudioInput, AudioOutput, AudioPlaybackResult
from .chunking import SpeechTextChunker
from .normalization import normalize_speech_text
from .contracts import (
    AudioFormat,
    AudioFrame,
    AudioSampleFormat,
    SpeechProviderHealth,
    SpeechProviderMetadata,
    SpeechToTextProvider,
    TextToSpeechProvider,
    TranscriptionEvent,
    TranscriptionEventType,
    VoiceProfile,
)
from .endpointing import EndpointConfig, EndpointDetector, EndpointSignal, UtteranceBuffer
from .evidence import SpeechCandidate, SpeechEvidenceConfig, SpeechActivityConfig, SpeechActivityDecision, SpeechActivityFusion, SpeechEvidenceGate, SpeechEvidenceReport, pcm16_rms
from .engine import VoiceLabEngine, VoiceTurnResult
from .playback import PlaybackLedger
from .profiles import StoredVoiceProfile, StoredVoiceReference, VoiceReferenceLibrary
from .registry import VoiceProviderRegistry
from .telemetry import VoiceLatencyTrace
from .vad import VoiceActivityDetector

__all__ = [
    "AudioDeviceInfo",
    "AudioFormat",
    "AudioFrame",
    "AudioInput",
    "AudioOutput",
    "AudioPlaybackResult",
    "AudioSampleFormat",
    "EndpointConfig",
    "EndpointDetector",
    "EndpointSignal",
    "PlaybackLedger",
    "SpeechActivityConfig",
    "SpeechActivityDecision",
    "SpeechActivityFusion",
    "SpeechCandidate",
    "SpeechEvidenceConfig",
    "SpeechEvidenceGate",
    "SpeechEvidenceReport",
    "SpeechProviderHealth",
    "SpeechProviderMetadata",
    "SpeechTextChunker",
    "VoiceReferenceLibrary",
    "StoredVoiceReference",
    "StoredVoiceProfile",
    "normalize_speech_text",
    "SpeechToTextProvider",
    "TextToSpeechProvider",
    "TranscriptionEvent",
    "TranscriptionEventType",
    "UtteranceBuffer",
    "VoiceActivityDetector",
    "VoiceLabEngine",
    "VoiceLatencyTrace",
    "VoiceTurnResult",
    "VoiceProfile",
    "VoiceProviderRegistry",
    "pcm16_rms",
]
