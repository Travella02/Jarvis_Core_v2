"""Deterministic provider-neutral Voice Lab architecture benchmark (no live devices/models)."""

from __future__ import annotations

from core.common.ids import CorrelationContext
from core.voice import (
    AudioFormat,
    AudioFrame,
    EndpointConfig,
    EndpointDetector,
    EndpointSignal,
    SpeechTextChunker,
    VoiceLatencyTrace,
    normalize_speech_text,
)


def main() -> int:
    checks: list[tuple[str, bool]] = []
    trace = CorrelationContext.create()
    frame = AudioFrame(trace, 0, AudioFormat(16000), b"\x00\x00" * 480)
    checks.append(("30ms_audio_frame_math", round(frame.duration_ms) == 30))

    detector = EndpointDetector(EndpointConfig(start_trigger_ms=60, end_silence_ms=90))
    signals = [detector.accept(x) for x in [True, True, True, False, False, False]]
    checks.append(
        (
            "orvex_endpointing",
            EndpointSignal.SPEECH_STARTED in signals and EndpointSignal.SPEECH_ENDED in signals,
        )
    )

    chunker = SpeechTextChunker(min_chars=8, soft_max_chars=40, hard_max_chars=100)
    chunks = chunker.push("Hello there. This is Jarvis speaking.")
    checks.append(("provider_neutral_tts_chunking", bool(chunks) and chunks[0] == "Hello there."))

    prosody = SpeechTextChunker()
    premature = prosody.push("A day on Venus is longer than its")
    completed = prosody.push(" year.")
    checks.append(
        (
            "prosody_safe_sentence_chunking",
            not premature and completed == ("A day on Venus is longer than its year.",),
        )
    )

    spoken = normalize_speech_text("**243 Earth days** and [Venus](https://example.com).")
    checks.append(("speech_display_normalization", spoken == "243 Earth days and Venus."))

    latency = VoiceLatencyTrace()
    latency.mark("a", now_ns=1_000_000)
    latency.mark("b", now_ns=3_500_000)
    checks.append(("monotonic_latency_telemetry", latency.elapsed_ms("a", "b") == 2.5))

    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    passed = sum(ok for _, ok in checks)
    print(f"Result: {passed}/{len(checks)} passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
