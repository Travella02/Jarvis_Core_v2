"""Provider-neutral speech confidence for realtime turn validation.

0.0.5 Repair5e keeps the successful Repair5 architecture:
Silero answers "does this sound like human speech?" and Whisper answers
"what was said?". This module adds a third, semantic-free decision layer:
"are the combined speech/ASR signals trustworthy enough to become a user turn?"

No words receive special meaning here. One-word answers are scored exactly like
longer utterances from general acoustic/ASR evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from core.voice.lexical import TranscriptEvidenceTracker, has_lexical_speech


@dataclass(frozen=True, slots=True)
class SpeechConfidenceConfig:
    """Weights and thresholds for provider-neutral speech acceptance.

    `early_accept_threshold` is intentionally higher than the final threshold:
    barge-in should wait for stronger evidence before cancelling an active Jarvis
    response, while a completed endpoint may use the full utterance evidence.
    """

    vad_weight: float = 0.38
    asr_weight: float = 0.34
    stability_weight: float = 0.18
    duration_weight: float = 0.10
    final_accept_threshold: float = 0.58
    early_accept_threshold: float = 0.68
    duration_full_credit_ms: int = 700

    def __post_init__(self) -> None:
        weights = (
            self.vad_weight,
            self.asr_weight,
            self.stability_weight,
            self.duration_weight,
        )
        if any(weight < 0.0 for weight in weights):
            raise ValueError("speech confidence weights must be non-negative")
        if abs(sum(weights) - 1.0) > 1e-6:
            raise ValueError("speech confidence weights must sum to 1")
        for name in ("final_accept_threshold", "early_accept_threshold"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.early_accept_threshold < self.final_accept_threshold:
            raise ValueError("early_accept_threshold must be >= final_accept_threshold")
        if self.duration_full_credit_ms <= 0:
            raise ValueError("duration_full_credit_ms must be positive")


@dataclass(frozen=True, slots=True)
class SpeechConfidenceDecision:
    accepted: bool
    stage: str
    score: float
    vad_confidence: float
    asr_confidence: float | None
    stability_confidence: float
    duration_confidence: float
    transcript: str
    threshold: float

    def as_dict(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "stage": self.stage,
            "score": round(self.score, 4),
            "threshold": round(self.threshold, 4),
            "vad_confidence": round(self.vad_confidence, 4),
            "asr_confidence": (
                round(self.asr_confidence, 4)
                if self.asr_confidence is not None
                else None
            ),
            "stability_confidence": round(self.stability_confidence, 4),
            "duration_confidence": round(self.duration_confidence, 4),
            "transcript": self.transcript,
        }


class SpeechConfidenceValidator:
    """Fuse Silero, Whisper, stability, and duration without keyword rules."""

    def __init__(self, config: SpeechConfidenceConfig | None = None) -> None:
        self.config = config or SpeechConfidenceConfig()

    @staticmethod
    def _vad_confidence(probabilities: tuple[float, ...]) -> float:
        if not probabilities:
            return 0.0
        values = [min(1.0, max(0.0, float(value))) for value in probabilities]
        # A real utterance normally sustains probability across several VAD
        # windows. Blend the mean with the peak so one isolated spike cannot
        # dominate, but quiet valid speech is not punished by one weak frame.
        return min(1.0, max(0.0, 0.72 * mean(values) + 0.28 * max(values)))

    def evaluate(
        self,
        *,
        stage: str,
        transcript: str,
        vad_probabilities: tuple[float, ...],
        asr_confidence: float | None,
        tracker: TranscriptEvidenceTracker,
        duration_ms: int,
    ) -> SpeechConfidenceDecision:
        if stage not in {"partial", "final"}:
            raise ValueError("stage must be 'partial' or 'final'")

        vad = self._vad_confidence(vad_probabilities)
        stability = tracker.stability_score(transcript)
        # A provider running final-only STT may legitimately expose no rolling
        # partials. In that case, treat the completed final transcript as neutral
        # stability evidence rather than stability=0. This preserves natural
        # short/one-word replies without creating a semantic word allow-list.
        if stage == "final" and has_lexical_speech(transcript) and tracker.partial_count == 0:
            stability = max(stability, 0.50)
        duration = min(1.0, max(0.0, duration_ms / self.config.duration_full_credit_ms))
        asr = None if asr_confidence is None else min(1.0, max(0.0, asr_confidence))

        # If a provider cannot expose ASR confidence, redistribute that weight
        # proportionally over the remaining independent signals rather than
        # pretending confidence=1 or rejecting all one-word answers.
        if asr is None:
            available = (
                self.config.vad_weight
                + self.config.stability_weight
                + self.config.duration_weight
            )
            score = (
                self.config.vad_weight * vad
                + self.config.stability_weight * stability
                + self.config.duration_weight * duration
            ) / available
        else:
            score = (
                self.config.vad_weight * vad
                + self.config.asr_weight * asr
                + self.config.stability_weight * stability
                + self.config.duration_weight * duration
            )

        threshold = (
            self.config.early_accept_threshold
            if stage == "partial"
            else self.config.final_accept_threshold
        )
        accepted = bool(has_lexical_speech(transcript) and score >= threshold)
        return SpeechConfidenceDecision(
            accepted=accepted,
            stage=stage,
            score=score,
            vad_confidence=vad,
            asr_confidence=asr,
            stability_confidence=stability,
            duration_confidence=duration,
            transcript=transcript.strip(),
            threshold=threshold,
        )
