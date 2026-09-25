"""Provider-neutral speech-evidence gating for the ORVEX voice engine.

WebRTC VAD alone is intentionally not authoritative. A candidate utterance must
also contain enough duration and acoustic energy above the recent noise floor
before any audio is submitted to STT. This prevents tiny clicks / room noise
from becoming plausible Whisper hallucinations such as "Thank you.".
"""

from __future__ import annotations

import math
import statistics
import sys
from array import array
from dataclasses import dataclass

from core.voice.contracts import AudioFrame, AudioSampleFormat


def pcm16_rms(payload: bytes) -> float:
    """Return normalized RMS (0..1) for little-endian PCM16 mono bytes."""

    if len(payload) % 2:
        raise ValueError("PCM16 payload must contain whole samples")
    values = array("h")
    values.frombytes(payload)
    if sys.byteorder != "little":  # pragma: no cover - Windows/x86 lab is little-endian
        values.byteswap()
    if not values:
        return 0.0
    energy = sum(int(value) * int(value) for value in values) / len(values)
    return math.sqrt(energy) / 32768.0


@dataclass(frozen=True, slots=True)
class SpeechActivityConfig:
    """Fuse VAD with an adaptive acoustic fallback for speech onset/continuation.

    WebRTC VAD is fast but can miss a perfectly live microphone endpoint.  The
    acoustic path is intentionally conservative: quiet/noisy frames below a
    floor-derived threshold never start a turn, while sustained strong user
    speech can rescue the turn even if VAD is temporarily blind.
    """

    min_rms: float = 0.035
    noise_multiplier: float = 3.5
    hard_rescue_rms: float = 0.12
    bootstrap_frames: int = 6
    noise_window_frames: int = 50

    def __post_init__(self) -> None:
        for name in ("min_rms", "noise_multiplier", "hard_rescue_rms"):
            if getattr(self, name) < 0.0:
                raise ValueError(f"{name} must be non-negative")
        for name in ("bootstrap_frames", "noise_window_frames"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")


@dataclass(frozen=True, slots=True)
class SpeechActivityDecision:
    active: bool
    vad_speech: bool
    acoustic_speech: bool
    acoustic_rescue: bool
    rms: float
    noise_floor_rms: float
    acoustic_threshold_rms: float


class SpeechActivityFusion:
    """Provider-neutral redundant activity signal used before endpointing.

    Raw VAD remains observable and is still used by the evidence report.  This
    class only prevents VAD from being a single point of failure for *starting*
    and *continuing* an utterance.
    """

    def __init__(self, config: SpeechActivityConfig | None = None) -> None:
        from collections import deque

        self.config = config or SpeechActivityConfig()
        self._noise = deque(maxlen=self.config.noise_window_frames)
        self._seen_frames = 0

    def classify(self, frame: AudioFrame, *, vad_speech: bool) -> SpeechActivityDecision:
        rms = pcm16_rms(frame.payload)
        noise_floor = float(statistics.median(self._noise)) if self._noise else 0.0
        threshold = max(self.config.min_rms, noise_floor * self.config.noise_multiplier)
        bootstrapping = self._seen_frames < self.config.bootstrap_frames
        acoustic = rms >= (self.config.hard_rescue_rms if bootstrapping else threshold)
        rescue = bool(acoustic and not vad_speech)
        active = bool(vad_speech or acoustic)

        # Learn ambient level only from frames that are not currently considered
        # speech by either detector. This prevents real speech from teaching the
        # adaptive floor to become louder.
        if not active:
            self._noise.append(rms)
        self._seen_frames += 1
        return SpeechActivityDecision(
            active=active,
            vad_speech=bool(vad_speech),
            acoustic_speech=bool(acoustic),
            acoustic_rescue=rescue,
            rms=rms,
            noise_floor_rms=noise_floor,
            acoustic_threshold_rms=threshold,
        )


@dataclass(frozen=True, slots=True)
class SpeechEvidenceConfig:
    """Conservative defaults for accepting a user utterance.

    The thresholds intentionally combine independent evidence: WebRTC VAD,
    signal energy, duration, and an adaptive noise-floor comparison. They are
    ORVEX policy and can be tuned or replaced without changing STT providers.
    """

    min_speech_span_ms: int = 240
    min_vad_speech_ms: int = 180
    min_energy_active_ms: int = 120
    min_vad_ratio: float = 0.30
    min_active_rms: float = 0.015
    min_peak_rms: float = 0.030
    noise_multiplier: float = 2.0

    def __post_init__(self) -> None:
        for name in ("min_speech_span_ms", "min_vad_speech_ms", "min_energy_active_ms"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if not 0.0 <= self.min_vad_ratio <= 1.0:
            raise ValueError("min_vad_ratio must be between 0 and 1")
        for name in ("min_active_rms", "min_peak_rms", "noise_multiplier"):
            if getattr(self, name) < 0.0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True, slots=True)
class SpeechEvidenceReport:
    accepted: bool
    reason: str
    duration_ms: int
    speech_span_ms: int
    vad_speech_ms: int
    vad_ratio: float
    energy_active_ms: int
    noise_floor_rms: float
    active_rms_threshold: float
    mean_rms: float
    peak_rms: float

    def as_dict(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "duration_ms": self.duration_ms,
            "speech_span_ms": self.speech_span_ms,
            "vad_speech_ms": self.vad_speech_ms,
            "vad_ratio": round(self.vad_ratio, 4),
            "energy_active_ms": self.energy_active_ms,
            "noise_floor_rms": round(self.noise_floor_rms, 6),
            "active_rms_threshold": round(self.active_rms_threshold, 6),
            "mean_rms": round(self.mean_rms, 6),
            "peak_rms": round(self.peak_rms, 6),
        }


@dataclass(frozen=True, slots=True)
class SpeechCandidate:
    frames: tuple[AudioFrame, ...]
    report: SpeechEvidenceReport


class SpeechEvidenceGate:
    """Collect one endpointed candidate and decide whether it deserves STT.

    The gate keeps the same pre-roll behavior as the Voice Lab, but STT only
    receives frames *after* the candidate passes evidence checks. Rejected
    candidates can therefore be ignored without generating a model transcript.
    """

    def __init__(
        self,
        *,
        frame_ms: int,
        preroll_frames: int,
        config: SpeechEvidenceConfig | None = None,
    ) -> None:
        from collections import deque

        if frame_ms <= 0:
            raise ValueError("frame_ms must be positive")
        if preroll_frames <= 0:
            raise ValueError("preroll_frames must be positive")
        self.frame_ms = frame_ms
        self.config = config or SpeechEvidenceConfig()
        self._preroll = deque(maxlen=preroll_frames)
        self._active = False
        self._frames: list[AudioFrame] = []
        self._flags: list[bool] = []

    def reset(self) -> None:
        self._preroll.clear()
        self._active = False
        self._frames.clear()
        self._flags.clear()

    def push(self, frame: AudioFrame, is_speech: bool, signal: object) -> SpeechCandidate | None:
        # Import locally to avoid an endpointing -> evidence import cycle.
        from core.voice.endpointing import EndpointSignal

        if not self._active:
            self._preroll.append((frame, is_speech))
            if signal is EndpointSignal.SPEECH_STARTED:
                self._active = True
                self._frames = [item[0] for item in self._preroll]
                self._flags = [item[1] for item in self._preroll]
                self._preroll.clear()
            return None

        self._frames.append(frame)
        self._flags.append(is_speech)
        if signal not in {EndpointSignal.SPEECH_ENDED, EndpointSignal.MAX_DURATION}:
            return None

        frames = tuple(self._frames)
        flags = tuple(self._flags)
        report = self._evaluate(frames, flags)
        self._active = False
        self._frames.clear()
        self._flags.clear()
        self._preroll.clear()
        return SpeechCandidate(frames=frames, report=report)

    def _evaluate(self, frames: tuple[AudioFrame, ...], flags: tuple[bool, ...]) -> SpeechEvidenceReport:
        if len(frames) != len(flags):
            raise ValueError("frames/flags length mismatch")
        if not frames:
            return SpeechEvidenceReport(False, "empty-candidate", 0, 0, 0, 0.0, 0, 0.0, self.config.min_active_rms, 0.0, 0.0)

        for frame in frames:
            if frame.format.sample_format is not AudioSampleFormat.PCM_S16LE or frame.format.channels != 1:
                raise ValueError("speech evidence requires mono PCM_S16LE audio")

        rms_values = [pcm16_rms(frame.payload) for frame in frames]
        speech_indexes = [index for index, flag in enumerate(flags) if flag]
        duration_ms = len(frames) * self.frame_ms
        vad_speech_ms = len(speech_indexes) * self.frame_ms

        # Estimate background from low-energy frames first, independent of VAD.
        # This is important for the rescue path: if WebRTC VAD misses a real
        # utterance, raw VAD flags cannot define the only valid speech span.
        ordered = sorted(rms_values)
        keep = max(1, len(ordered) // 3)
        background = ordered[:keep]
        noise_floor = float(statistics.median(background)) if background else 0.0
        active_threshold = max(self.config.min_active_rms, noise_floor * self.config.noise_multiplier)
        energy_indexes = [index for index, rms in enumerate(rms_values) if rms >= active_threshold]

        combined_indexes = sorted(set(speech_indexes) | set(energy_indexes))
        if combined_indexes:
            first, last = combined_indexes[0], combined_indexes[-1]
            span_values = rms_values[first : last + 1]
            span_flags = flags[first : last + 1]
            speech_span_ms = (last - first + 1) * self.frame_ms
        else:
            span_values = rms_values
            span_flags = flags
            speech_span_ms = 0

        energy_active_ms = sum(1 for rms in span_values if rms >= active_threshold) * self.frame_ms
        peak_rms = max(rms_values, default=0.0)
        mean_rms = sum(span_values) / len(span_values) if span_values else 0.0
        vad_ratio = (sum(1 for flag in span_flags if flag) / len(span_flags)) if span_flags else 0.0

        vad_supported = (
            vad_speech_ms >= self.config.min_vad_speech_ms
            and vad_ratio >= self.config.min_vad_ratio
        )
        acoustic_rescue_supported = (
            energy_active_ms >= max(self.config.min_energy_active_ms, 180)
            and peak_rms >= 0.08
            and mean_rms >= 0.025
        )
        checks = (
            (speech_span_ms >= self.config.min_speech_span_ms, "speech-span-too-short"),
            (energy_active_ms >= self.config.min_energy_active_ms, "insufficient-energy"),
            (peak_rms >= max(self.config.min_peak_rms, active_threshold), "peak-below-threshold"),
            (vad_supported or acoustic_rescue_supported, "insufficient-speech-evidence"),
        )
        reason = "accepted"
        accepted = True
        for passed, failure in checks:
            if not passed:
                accepted = False
                reason = failure
                break

        return SpeechEvidenceReport(
            accepted=accepted,
            reason=reason,
            duration_ms=duration_ms,
            speech_span_ms=speech_span_ms,
            vad_speech_ms=vad_speech_ms,
            vad_ratio=vad_ratio,
            energy_active_ms=energy_active_ms,
            noise_floor_rms=noise_floor,
            active_rms_threshold=active_threshold,
            mean_rms=mean_rms,
            peak_rms=peak_rms,
        )
