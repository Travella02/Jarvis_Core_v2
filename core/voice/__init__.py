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
from .lexical import has_lexical_speech, lexical_words
from .confidence import SpeechConfidenceConfig, SpeechConfidenceDecision, SpeechConfidenceValidator
from .conversation_control import (
    ContinuousVoiceSession,
    SleepPhraseDetector,
    VoicePresenceState,
    VoiceSessionResult,
    WakeMatch,
    WakePhraseDetector,
    WakeSleepConfig,
)
from .playback import PlaybackLedger
from .wake_listener import LocalWakeListener, WakeListenerResult, WAKE_AUDIO_FORMAT, WAKE_FRAME_BYTES, WAKE_FRAME_MS
from .frontend import (
    VoiceFrontendEvent,
    VoiceFrontendEventType,
    VoiceFrontendHealth,
    VoiceFrontendMetadata,
    VoiceFrontendProvider,
    VoiceFrontendSession,
    VoiceFrontendSessionConfig,
)
from .live_bridge import LiveConversationBridge, LiveTranscriptBuffer, TranscriptFragment
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
    "ContinuousVoiceSession",
    "SleepPhraseDetector",
    "VoicePresenceState",
    "VoiceSessionResult",
    "WakeMatch",
    "WakePhraseDetector",
    "WakeSleepConfig",
    "LocalWakeListener",
    "WakeListenerResult",
    "WAKE_AUDIO_FORMAT",
    "WAKE_FRAME_BYTES",
    "WAKE_FRAME_MS",
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
    "SpeechConfidenceConfig",
    "SpeechConfidenceDecision",
    "SpeechConfidenceValidator",
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
    "has_lexical_speech",
    "lexical_words",
    "VoiceLatencyTrace",
    "VoiceTurnResult",
    "VoiceProfile",
    "VoiceProviderRegistry",
    "VoiceFrontendEvent",
    "VoiceFrontendEventType",
    "VoiceFrontendHealth",
    "VoiceFrontendMetadata",
    "VoiceFrontendProvider",
    "VoiceFrontendSession",
    "VoiceFrontendSessionConfig",
    "LiveConversationBridge",
    "LiveTranscriptBuffer",
    "TranscriptFragment",
    "pcm16_rms",
]
