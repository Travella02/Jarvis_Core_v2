"""0.0.5 ORVEX realtime conversation voice orchestration.

The engine owns provider-neutral capture, endpointing, STT, TTS, playback,
cancellation, heard/unheard accounting, and low-level barge-in primitives.
Wake/sleep lifecycle and continuous-session policy live in conversation_control.py.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from collections.abc import AsyncIterator

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.conversation import ConversationCore
from core.intelligence import ReasoningPolicy
from core.voice.audio import AudioInput, AudioOutput
from core.voice.chunking import SpeechTextChunker
from core.voice.normalization import normalize_speech_text
from core.voice.contracts import (
    AudioFormat,
    AudioFrame,
    AudioSampleFormat,
    TranscriptionEventType,
    VoiceProfile,
)
from core.voice.endpointing import EndpointConfig, EndpointDetector, EndpointSignal
from core.voice.playback import PlaybackLedger
from core.voice.registry import VoiceProviderRegistry
from core.voice.telemetry import VoiceLatencyTrace
from core.voice.vad import VoiceActivityDetector
from core.voice.evidence import pcm16_rms
from core.voice.confidence import SpeechConfidenceDecision, SpeechConfidenceValidator
from core.voice.lexical import TranscriptEvidenceTracker, has_lexical_speech


@dataclass(frozen=True, slots=True)
class VoiceTurnResult:
    transcript: str
    response_text: str
    status: str
    latency_ms: dict[str, float]
    playback: PlaybackLedger
    turn_id: str | None
    speech_metrics: dict[str, int]
    heard_text: str = ""
    interruption_playback_ms: float | None = None
    interruption_phase: str | None = None


class VoiceLabEngine:
    """One-turn local voice lab on top of the authoritative Conversation Core."""

    INPUT_FORMAT = AudioFormat(
        sample_rate_hz=16_000,
        channels=1,
        sample_format=AudioSampleFormat.PCM_S16LE,
    )
    # Repair5e: Silero opens a provisional speech candidate, the same rolling
    # Whisper stream supplies words/ASR confidence, and a provider-neutral
    # confidence validator decides whether the candidate becomes a real user turn.
    # Loudness and keyword semantics never decide acceptance.
    TRANSCRIPT_HOLD_MS = 540

    def __init__(
        self,
        *,
        conversation: ConversationCore,
        providers: VoiceProviderRegistry,
        audio_input: AudioInput,
        audio_output: AudioOutput,
        vad: VoiceActivityDetector,
        endpoint_config: EndpointConfig | None = None,
        voice: VoiceProfile | None = None,
        tts_response_mode: str = "streaming",
        require_partial_confirmation: bool = False,
        speech_confidence: SpeechConfidenceValidator | None = None,
    ) -> None:
        self.conversation = conversation
        self.providers = providers
        self.audio_input = audio_input
        self.audio_output = audio_output
        self.vad = vad
        self.endpoint_config = endpoint_config or EndpointConfig()
        self.voice = voice or VoiceProfile("jarvis-default", "Jarvis Default")
        if tts_response_mode not in {"streaming", "whole"}:
            raise ValueError("tts_response_mode must be 'streaming' or 'whole'")
        self.tts_response_mode = tts_response_mode
        self.require_partial_confirmation = bool(require_partial_confirmation)
        self.speech_confidence = speech_confidence or SpeechConfidenceValidator()
        self._capture_token: CancellationToken | None = None
        self._capture_trace: CorrelationContext | None = None
        self._capture_candidate_active = False
        self._tts_token: CancellationToken | None = None
        self._tts_trace: CorrelationContext | None = None
        self._response_phase: str | None = None
        self._interruption_phase: str | None = None



    @property
    def capture_candidate_active(self) -> bool:
        return self._capture_candidate_active

    async def listen_once(
        self,
        *,
        lexical_interrupt_probe: bool = False,
    ) -> tuple[str, VoiceLatencyTrace, CorrelationContext]:
        """Capture one utterance using independent neural speech presence.

        Repair5e keeps the V1 ownership split but treats Silero speech presence
        as a provisional candidate, not an automatic user turn. The same rolling
        Whisper stream supplies lexical/ASR confidence, and a generic confidence
        validator combines VAD probability, ASR confidence, transcript stability,
        and duration. No words receive special interruption semantics.
        """

        preroll_frames = max(
            1,
            self.endpoint_config.preroll_ms // self.endpoint_config.frame_ms,
        )

        while True:
            trace = CorrelationContext.create()
            self._capture_trace = trace
            token = CancellationToken()
            self._capture_token = token
            latency = VoiceLatencyTrace()
            onset = EndpointDetector(self.endpoint_config)
            self.vad.reset()
            preroll: deque[AudioFrame] = deque(maxlen=preroll_frames)

            candidate_active = False
            candidate_silence_ms = 0
            candidate_elapsed_ms = 0
            transcript_hold_until = 0.0
            transcript = TranscriptEvidenceTracker()
            final_text = ""
            final_asr_confidence: float | None = None
            confidence_emitted = False
            first_partial_marked = False
            max_rms = 0.0
            vad_speech_ms = 0
            vad_probabilities: list[float] = []

            stt_audio: asyncio.Queue[AudioFrame | None] | None = None
            stt_events: asyncio.Queue[object | None] | None = None
            stt_task: asyncio.Task[None] | None = None

            def emit_confidence(
                decision: SpeechConfidenceDecision,
                *,
                source: str,
                audio_ms: float,
            ) -> None:
                nonlocal confidence_emitted
                if confidence_emitted:
                    return
                confidence_emitted = True
                payload = decision.as_dict()
                payload.update(
                    {
                        "source": source,
                        "audio_ms": round(audio_ms),
                        "speech_presence_authority": "silero-neural-vad",
                        "speech_turn_authority": "multi-signal-confidence",
                    }
                )
                self.conversation.event_bus.emit(
                    "voice.speech.confidence_confirmed",
                    origin="voice-engine",
                    trace=trace,
                    conversation_id=self.conversation.context.conversation_id,
                    payload=payload,
                )
                # Keep the established lexical event as compatibility telemetry.
                self.conversation.event_bus.emit(
                    "voice.speech.lexical_confirmed",
                    origin="voice-engine",
                    trace=trace,
                    conversation_id=self.conversation.context.conversation_id,
                    payload={
                        "text": decision.transcript,
                        "source": source,
                        "audio_ms": round(audio_ms),
                        "confidence": round(decision.score, 4),
                    },
                )

            async def start_stt(initial_frames: tuple[AudioFrame, ...]) -> None:
                nonlocal stt_audio, stt_events, stt_task
                stt_audio = asyncio.Queue()
                stt_events = asyncio.Queue()

                async def candidate_audio_stream() -> AsyncIterator[AudioFrame]:
                    assert stt_audio is not None
                    while True:
                        item = await stt_audio.get()
                        if item is None:
                            return
                        yield item

                async def worker() -> None:
                    assert stt_events is not None
                    try:
                        async for event in self.providers.stt.stream_transcription(
                            candidate_audio_stream(), token
                        ):
                            await stt_events.put(event)
                    finally:
                        await stt_events.put(None)

                stt_task = asyncio.create_task(worker(), name="jarvis-live-stt-turn")
                for item in initial_frames:
                    await stt_audio.put(item)

            async def stop_stt(*, cancel: bool = False, reason: str = "") -> None:
                """Cooperatively finish the one live STT pipeline.

                Normal endpointing sends EOF and lets the provider unwind. Session
                cancellation first sets the shared token. Hard task cancellation is
                a bounded last resort so async generators are not destroyed while
                still awaiting their queues.
                """
                nonlocal stt_task
                if stt_task is None:
                    return
                if cancel:
                    token.cancel(reason or "voice capture cancelled")
                if stt_audio is not None and not stt_task.done():
                    try:
                        stt_audio.put_nowait(None)
                    except asyncio.QueueFull:
                        await stt_audio.put(None)
                if stt_task.done():
                    await asyncio.gather(stt_task, return_exceptions=True)
                    return
                try:
                    await asyncio.wait_for(asyncio.shield(stt_task), timeout=1.5)
                except TimeoutError:
                    stt_task.cancel()
                    await asyncio.gather(stt_task, return_exceptions=True)

            async def drain_stt_events() -> None:
                nonlocal final_text, final_asr_confidence
                nonlocal transcript_hold_until, first_partial_marked
                if stt_events is None:
                    return
                loop = asyncio.get_running_loop()
                while not stt_events.empty():
                    event = stt_events.get_nowait()
                    if event is None:
                        continue
                    if event.event_type is TranscriptionEventType.PARTIAL:
                        partial = event.text.strip()
                        if partial:
                            if not first_partial_marked:
                                latency.mark("stt_first_partial")
                                first_partial_marked = True
                            self.conversation.event_bus.emit(
                                "voice.stt.partial",
                                origin="voice-engine",
                                trace=trace,
                                conversation_id=self.conversation.context.conversation_id,
                                payload={
                                    "text": partial,
                                    "confidence": event.confidence,
                                },
                            )

                            decision = self.speech_confidence.evaluate(
                                stage="partial",
                                transcript=partial,
                                vad_probabilities=tuple(vad_probabilities),
                                asr_confidence=event.confidence,
                                tracker=transcript,
                                duration_ms=candidate_elapsed_ms,
                            )
                            if transcript.observe_partial(partial):
                                transcript_hold_until = max(
                                    transcript_hold_until,
                                    loop.time() + (self.TRANSCRIPT_HOLD_MS / 1000.0),
                                )
                            self.conversation.event_bus.emit(
                                "voice.speech.confidence",
                                origin="voice-engine",
                                trace=trace,
                                conversation_id=self.conversation.context.conversation_id,
                                payload=decision.as_dict(),
                            )
                            if lexical_interrupt_probe and decision.accepted:
                                emit_confidence(
                                    decision,
                                    source="rolling-stt-confidence",
                                    audio_ms=candidate_elapsed_ms,
                                )
                    elif event.event_type is TranscriptionEventType.FINAL:
                        final_text = event.text.strip()
                        final_asr_confidence = event.confidence
                        latency.mark("stt_final")
                    elif event.event_type is TranscriptionEventType.ERROR:
                        raise RuntimeError(event.detail or "STT provider error")

            async def reset_false_candidate() -> None:
                nonlocal candidate_active, candidate_silence_ms
                nonlocal candidate_elapsed_ms, transcript_hold_until, transcript
                nonlocal final_text, final_asr_confidence, confidence_emitted
                nonlocal first_partial_marked, max_rms, vad_speech_ms
                nonlocal vad_probabilities, stt_audio, stt_events, stt_task
                nonlocal latency

                await stop_stt()
                candidate_active = False
                self._capture_candidate_active = False
                candidate_silence_ms = 0
                candidate_elapsed_ms = 0
                transcript_hold_until = 0.0
                transcript = TranscriptEvidenceTracker()
                final_text = ""
                final_asr_confidence = None
                confidence_emitted = False
                first_partial_marked = False
                max_rms = 0.0
                vad_speech_ms = 0
                vad_probabilities = []
                stt_audio = None
                stt_events = None
                stt_task = None
                latency = VoiceLatencyTrace()
                onset.reset()
                self.vad.reset()
                preroll.clear()

            async def finalize_candidate(endpoint_reason: str):
                if not candidate_active or stt_audio is None or stt_task is None:
                    return None

                await stop_stt()
                await drain_stt_events()
                latency.mark("speech_ended")

                if token.is_cancelled:
                    raise asyncio.CancelledError(token.reason or "voice capture cancelled")

                decision = self.speech_confidence.evaluate(
                    stage="final",
                    transcript=final_text,
                    vad_probabilities=tuple(vad_probabilities),
                    asr_confidence=final_asr_confidence,
                    tracker=transcript,
                    duration_ms=candidate_elapsed_ms,
                )
                self.conversation.event_bus.emit(
                    "voice.speech.confidence",
                    origin="voice-engine",
                    trace=trace,
                    conversation_id=self.conversation.context.conversation_id,
                    payload=decision.as_dict(),
                )

                if decision.accepted:
                    if not confidence_emitted:
                        emit_confidence(
                            decision,
                            source="final-stt-confidence",
                            audio_ms=candidate_elapsed_ms,
                        )
                    endpoint_payload = decision.as_dict()
                    endpoint_payload.update(
                        {
                            "reason": endpoint_reason,
                            "duration_ms": candidate_elapsed_ms,
                            "vad_speech_ms": vad_speech_ms,
                            "partial_count": transcript.partial_count,
                            "peak_rms": round(max_rms, 6),
                            "speech_presence_authority": "silero-neural-vad",
                            "speech_turn_authority": "multi-signal-confidence",
                        }
                    )
                    self.conversation.event_bus.emit(
                        "voice.speech.endpointed",
                        origin="voice-engine",
                        trace=trace,
                        conversation_id=self.conversation.context.conversation_id,
                        payload=endpoint_payload,
                    )
                    self._capture_trace = None
                    self._capture_token = None
                    self._capture_candidate_active = False
                    return final_text, latency, trace

                rejected_payload = decision.as_dict()
                rejected_payload.update(
                    {
                        "reason": (
                            "speech-confidence-below-threshold"
                            if has_lexical_speech(final_text)
                            else "speech-without-lexical-transcript"
                        ),
                        "endpoint_reason": endpoint_reason,
                        "duration_ms": candidate_elapsed_ms,
                        "vad_speech_ms": vad_speech_ms,
                        "partial_count": transcript.partial_count,
                        "peak_rms": round(max_rms, 6),
                        "speech_presence_authority": "silero-neural-vad",
                        "speech_turn_authority": "multi-signal-confidence",
                    }
                )
                self.conversation.event_bus.emit(
                    "voice.speech.rejected",
                    origin="voice-engine",
                    trace=trace,
                    conversation_id=self.conversation.context.conversation_id,
                    payload=rejected_payload,
                )
                await reset_false_candidate()
                return None

            try:
                async for frame in self.audio_input.stream(
                    trace=trace,
                    audio_format=self.INPUT_FORMAT,
                    frame_ms=self.endpoint_config.frame_ms,
                    cancellation_token=token,
                ):
                    if token.is_cancelled:
                        break

                    await drain_stt_events()
                    vad_speech = self.vad.is_speech(frame)
                    max_rms = max(max_rms, pcm16_rms(frame.payload))
                    probability = getattr(self.vad, "last_probability", None)
                    evaluated = getattr(self.vad, "last_evaluated", True)
                    if evaluated:
                        if isinstance(probability, (int, float)):
                            vad_score = min(1.0, max(0.0, float(probability)))
                        else:
                            # Provider-neutral fallback for VAD adapters that
                            # expose only a boolean decision.
                            vad_score = 1.0 if vad_speech else 0.0
                        vad_probabilities.append(vad_score)
                        if len(vad_probabilities) > 96:
                            vad_probabilities.pop(0)

                    if not candidate_active:
                        preroll.append(frame)
                        signal = onset.accept(vad_speech)
                        if signal is not EndpointSignal.SPEECH_STARTED:
                            continue

                        candidate_active = True
                        # Confidence is scoped to this candidate only. Long idle
                        # silence before speech must not dilute Silero evidence.
                        current_probability = (
                            min(1.0, max(0.0, float(probability)))
                            if isinstance(probability, (int, float))
                            else (1.0 if vad_speech else 0.0)
                        )
                        vad_probabilities.clear()
                        vad_probabilities.append(current_probability)
                        latency.mark("speech_started")
                        initial = tuple(preroll)
                        candidate_elapsed_ms = round(
                            sum(item.duration_ms for item in initial)
                        )
                        vad_speech_ms = max(
                            self.endpoint_config.start_trigger_ms,
                            self.endpoint_config.frame_ms if vad_speech else 0,
                        )
                        preroll.clear()
                        await start_stt(initial)
                        payload = {
                            "vad_speech": True,
                            "candidate_only": True,
                            "speech_presence_authority": "silero-neural-vad",
                            "speech_turn_authority": "multi-signal-confidence",
                        }
                        probability = getattr(self.vad, "last_probability", None)
                        if isinstance(probability, (int, float)):
                            payload["vad_probability"] = round(float(probability), 4)
                        self.conversation.event_bus.emit(
                            "voice.speech.started",
                            origin="voice-engine",
                            trace=trace,
                            conversation_id=self.conversation.context.conversation_id,
                            payload=payload,
                        )
                        continue

                    candidate_elapsed_ms += round(frame.duration_ms)
                    if vad_speech:
                        vad_speech_ms += round(frame.duration_ms)
                    assert stt_audio is not None
                    await stt_audio.put(frame)

                    semantic_active = (
                        vad_speech
                        or asyncio.get_running_loop().time() < transcript_hold_until
                    )
                    if semantic_active:
                        candidate_silence_ms = 0
                    else:
                        candidate_silence_ms += self.endpoint_config.frame_ms

                    await drain_stt_events()

                    ended = candidate_silence_ms >= self.endpoint_config.end_silence_ms
                    maxed = candidate_elapsed_ms >= self.endpoint_config.max_utterance_ms
                    if not ended and not maxed:
                        continue

                    endpoint_reason = "max-duration" if maxed else "neural-vad-silence"
                    completed = await finalize_candidate(endpoint_reason)
                    if completed is not None:
                        return completed

                if candidate_active:
                    completed = await finalize_candidate("input-stream-ended")
                    if completed is not None:
                        return completed

                if token.is_cancelled:
                    await stop_stt(cancel=True, reason=token.reason or "voice capture cancelled")
                    raise asyncio.CancelledError(token.reason or "voice capture cancelled")

                self._capture_trace = None
                self._capture_token = None
            finally:
                self._capture_candidate_active = False
                if stt_task is not None and not stt_task.done():
                    await stop_stt(cancel=True, reason=token.reason or "voice capture closing")

    @staticmethod
    def _estimate_heard_prefix(
        text: str,
        ledger: PlaybackLedger,
        *,
        tts_generation_complete: bool,
    ) -> tuple[str, str]:
        words = text.split()
        if not words or ledger.played_bytes <= 0:
            return "", "none-heard"
        if tts_generation_complete and ledger.queued_bytes > 0:
            ratio = ledger.heard_fraction
            method = "pcm-fraction"
        else:
            # 0.0.5 preserves exact PCM playback time but Qwen does not expose
            # word timestamps. Fall back to an explicitly approximate speaking
            # rate until a forced-alignment layer is added later.
            estimated_total_ms = max(330.0, len(words) * 330.0)
            ratio = min(1.0, ledger.played_duration_ms / estimated_total_ms)
            method = "speech-rate-estimate"
        count = max(1, min(len(words), round(len(words) * ratio)))
        return " ".join(words[:count]), method

    async def run_once(
        self,
        *,
        reasoning_policy: ReasoningPolicy | None = None,
    ) -> VoiceTurnResult:
        transcript, latency, capture_trace = await self.listen_once()
        return await self.respond_to_transcript(
            transcript,
            latency=latency,
            capture_trace=capture_trace,
            reasoning_policy=reasoning_policy,
        )

    async def respond_to_transcript(
        self,
        transcript: str,
        *,
        latency: VoiceLatencyTrace | None = None,
        capture_trace: CorrelationContext | None = None,
        reasoning_policy: ReasoningPolicy | None = None,
    ) -> VoiceTurnResult:
        """Route one already-captured utterance through Luna -> TTS -> playback.

        This split is what lets 0.0.5 start the next microphone capture while the
        current response is still being spoken.
        """

        clean_transcript = transcript.strip()
        if not clean_transcript:
            raise ValueError("voice transcript cannot be empty")
        latency = latency or VoiceLatencyTrace()
        capture_trace = capture_trace or CorrelationContext.create()
        self.conversation.event_bus.emit(
            "voice.transcript.committed",
            origin="voice-engine",
            trace=capture_trace,
            conversation_id=self.conversation.context.conversation_id,
            payload={"text": clean_transcript},
        )
        latency.mark("conversation_submit")

        delta_queue: asyncio.Queue[tuple[CorrelationContext, str] | None] = asyncio.Queue()
        speech_queue: asyncio.Queue[tuple[CorrelationContext, str] | None] = asyncio.Queue(maxsize=32)
        audio_queue: asyncio.Queue[AudioFrame | None] = asyncio.Queue(maxsize=1024)
        chunker = SpeechTextChunker()
        ledger = PlaybackLedger()
        tts_token = CancellationToken()
        self._tts_token = tts_token
        self._response_phase = "thinking"
        self._interruption_phase = None
        first_delta = True
        first_speech_chunk = True
        first_tts_request = True
        first_tts_audio = True
        tts_generation_complete = False
        speech_metrics: dict[str, int] = {}

        def on_delta(event) -> None:
            nonlocal first_delta
            text = str(event.payload.get("text_delta", ""))
            if event.trace is None or not text:
                return
            if self.tts_response_mode == "whole":
                if first_delta:
                    latency.mark("luna_first_text")
                    first_delta = False
                return
            delta_queue.put_nowait((event.trace, text))

        unsubscribe = self.conversation.event_bus.subscribe("response.text.delta", on_delta)

        async def queue_spoken_chunk(trace: CorrelationContext, raw_text: str) -> None:
            nonlocal first_speech_chunk
            spoken = normalize_speech_text(raw_text)
            if not spoken or tts_token.is_cancelled:
                return
            if first_speech_chunk:
                latency.mark("speech_first_chunk_ready")
                speech_metrics["first_chunk_chars"] = len(spoken)
                speech_metrics["first_chunk_words"] = len(spoken.split())
                first_speech_chunk = False
            await speech_queue.put((trace, spoken))

        async def speech_text_worker() -> None:
            nonlocal first_delta
            last_trace: CorrelationContext | None = None
            while True:
                item = await delta_queue.get()
                if item is None:
                    tail = chunker.flush()
                    if tail and last_trace is not None:
                        await queue_spoken_chunk(last_trace, tail)
                    await speech_queue.put(None)
                    return
                trace, delta = item
                last_trace = trace
                if first_delta:
                    latency.mark("luna_first_text")
                    first_delta = False
                for chunk in chunker.push(delta):
                    await queue_spoken_chunk(trace, chunk)

        async def tts_worker() -> None:
            nonlocal first_tts_request, first_tts_audio, tts_generation_complete
            while True:
                item = await speech_queue.get()
                if item is None:
                    if not tts_token.is_cancelled:
                        tts_generation_complete = True
                    await audio_queue.put(None)
                    return
                trace, text = item
                if tts_token.is_cancelled:
                    await audio_queue.put(None)
                    return
                self._tts_trace = trace
                if first_tts_request:
                    latency.mark("tts_first_request_started")
                    first_tts_request = False
                async for frame in self.providers.tts.stream_speech(
                    trace,
                    text,
                    self.voice,
                    tts_token,
                ):
                    if tts_token.is_cancelled:
                        break
                    ledger.queue(len(frame.payload), duration_ms=frame.duration_ms)
                    if first_tts_audio:
                        latency.mark("tts_first_waveform_ready")
                        latency.mark("tts_first_audio")
                        first_tts_audio = False
                    await audio_queue.put(frame)
                if tts_token.is_cancelled:
                    await audio_queue.put(None)
                    return

        async def audio_stream() -> AsyncIterator[AudioFrame]:
            startup_buffer_ms = int(self.providers.tts.metadata.extra.get("startup_buffer_ms", 0) or 0)
            buffered: list[AudioFrame] = []
            buffered_ms = 0.0
            released = startup_buffer_ms <= 0
            playback_start_emitted = False

            def before_first_yield(frame: AudioFrame) -> None:
                nonlocal playback_start_emitted
                if playback_start_emitted:
                    return
                playback_start_emitted = True
                self._response_phase = "speaking"
                self.conversation.event_bus.emit(
                    "voice.response.playback_starting",
                    origin="voice-engine",
                    trace=frame.trace,
                    conversation_id=self.conversation.context.conversation_id,
                    payload={"turn_id": frame.trace.turn_id},
                )

            while True:
                item = await audio_queue.get()
                if item is None:
                    if not released:
                        for frame in buffered:
                            before_first_yield(frame)
                            yield frame
                    return
                if not released:
                    buffered.append(item)
                    buffered_ms += item.duration_ms
                    if buffered_ms < startup_buffer_ms:
                        continue
                    latency.mark("audio_startup_buffer_ready")
                    released = True
                    for frame in buffered:
                        before_first_yield(frame)
                        yield frame
                    buffered.clear()
                    continue
                before_first_yield(item)
                yield item

        async def playback_worker():
            playback = await self.audio_output.play(audio_stream(), tts_token)
            ledger.played(
                playback.bytes_written,
                duration_ms=playback.source_duration_ms_written,
            )
            if playback.first_write_monotonic_ns is not None:
                latency.mark("audio_first_write_started", now_ns=playback.first_write_monotonic_ns)
            if playback.first_write_completed_monotonic_ns is not None:
                latency.mark(
                    "audio_first_write_completed",
                    now_ns=playback.first_write_completed_monotonic_ns,
                )
            audible_ns = playback.estimated_first_audible_monotonic_ns or playback.first_write_monotonic_ns
            if audible_ns is not None:
                latency.mark("audio_first_played", now_ns=audible_ns)
            return playback

        speech_task = (
            asyncio.create_task(speech_text_worker(), name="jarvis-voice-chunker")
            if self.tts_response_mode == "streaming"
            else None
        )
        tts_task = asyncio.create_task(tts_worker(), name="jarvis-voice-tts")
        playback_task = asyncio.create_task(playback_worker(), name="jarvis-voice-playback")
        tasks = tuple(task for task in (speech_task, tts_task, playback_task) if task is not None)

        result = None
        try:
            result = await self.conversation.submit_voice(
                clean_transcript,
                reasoning_policy=reasoning_policy or ReasoningPolicy(),
            )
            latency.mark("luna_response_complete")
            if self._response_phase == "thinking" and not tts_token.is_cancelled:
                self._response_phase = "synthesizing"

            if result.status == "completed" and not tts_token.is_cancelled:
                if self.tts_response_mode == "whole":
                    await queue_spoken_chunk(result.trace, result.text)
                    spoken = normalize_speech_text(result.text)
                    speech_metrics["whole_response_chars"] = len(spoken)
                    speech_metrics["whole_response_words"] = len(spoken.split())
                    await speech_queue.put(None)
                else:
                    await delta_queue.put(None)
                    assert speech_task is not None
                    await speech_task
            else:
                if speech_task is not None and not speech_task.done():
                    await delta_queue.put(None)
                    await speech_task
                else:
                    await speech_queue.put(None)

            await tts_task
            playback = await playback_task
            interrupted = tts_token.is_cancelled
            if interrupted:
                ledger.interrupt()
            latency.mark("turn_done")

            heard_text = result.text
            alignment_method = "complete"
            if interrupted:
                heard_text, alignment_method = self._estimate_heard_prefix(
                    result.text,
                    ledger,
                    tts_generation_complete=tts_generation_complete,
                )

            self.conversation.record_voice_playback(
                response_turn_id=result.trace.turn_id,
                generated_text=result.text,
                heard_text=heard_text,
                interrupted=interrupted,
                playback_ms=ledger.played_duration_ms,
                played_bytes=ledger.played_bytes,
                queued_bytes=ledger.queued_bytes,
                alignment_method=alignment_method,
                interruption_phase=(self._interruption_phase or self._response_phase or "unknown"),
            )

            return VoiceTurnResult(
                transcript=clean_transcript,
                response_text=result.text,
                status="interrupted" if interrupted else result.status,
                latency_ms=latency.as_milliseconds(),
                playback=ledger,
                turn_id=result.trace.turn_id,
                speech_metrics=speech_metrics,
                heard_text=heard_text,
                interruption_playback_ms=(ledger.played_duration_ms if interrupted else None),
                interruption_phase=(self._interruption_phase if interrupted else None),
            )
        finally:
            unsubscribe()
            if any(not task.done() for task in tasks):
                tts_token.cancel("voice turn ended")
                for queue in (delta_queue, speech_queue, audio_queue):
                    try:
                        queue.put_nowait(None)
                    except asyncio.QueueFull:
                        pass
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            self._tts_trace = None
            self._tts_token = None
            self._response_phase = None
            self._interruption_phase = None

    async def cancel_capture(self, reason: str = "capture cancelled") -> bool:
        token = self._capture_token
        if token is None or token.is_cancelled:
            return False
        token.cancel(reason)
        trace = self._capture_trace
        if trace is not None:
            await self.providers.stt.cancel(trace.request_id)
        return True

    async def interrupt_response(self, reason: str = "user interruption") -> bool:
        """Cancel the active Jarvis turn without cancelling the user's capture.

        The same path applies during thinking, local synthesis, or audible playback
        so future research/work states can reuse a single user-preemption contract.
        """

        did_anything = False
        if self._response_phase is not None:
            self._interruption_phase = self._response_phase
        token = self._tts_token
        if token is not None and not token.is_cancelled:
            token.cancel(reason)
            did_anything = True

        # Silence the user-facing output first. Provider cancellation can take
        # until Qwen reaches its next streaming chunk, but barge-in should sound
        # immediate even while the resident generator is winding down.
        await self.audio_output.stop()
        if self._tts_trace is not None:
            await self.providers.tts.cancel(self._tts_trace.request_id)
            did_anything = True
        # If Luna is still generating (possible in future streaming modes), cancel
        # that foreground turn too. Whole-response 0.0.5 normally reaches barge-in
        # only after Luna has completed and local speech is playing.
        if await self.conversation.cancel_active_turn(reason):
            did_anything = True
        self.conversation.event_bus.emit(
            "voice.response.stop.requested",
            origin="voice-engine",
            conversation_id=self.conversation.context.conversation_id,
            payload={"reason": reason, "phase": self._interruption_phase or "unknown"},
        )
        return did_anything

    async def interrupt(self, reason: str = "user interruption") -> bool:
        """Backward-compatible full voice interruption entry point."""
        did_response = await self.interrupt_response(reason)
        did_capture = await self.cancel_capture(reason)
        return did_response or did_capture

