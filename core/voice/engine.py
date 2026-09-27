"""0.0.4 ORVEX Voice Lab orchestration.

The engine owns audio flow, VAD/endpointing, provider routing, response chunking,
playback, interruption plumbing, and latency marks. Concrete STT/TTS model names
remain adapter details and can be replaced through VoiceProviderRegistry.

0.0.4 is intentionally half-duplex at the microphone/output device boundary:
we endpoint one user utterance, then speak the response. The interruption API and
cancellation plumbing are real, but always-listening full-duplex/AEC arrives in
0.0.5 as required by the master roadmap.
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
from core.voice.evidence import SpeechActivityFusion


@dataclass(frozen=True, slots=True)
class VoiceTurnResult:
    transcript: str
    response_text: str
    status: str
    latency_ms: dict[str, float]
    playback: PlaybackLedger
    turn_id: str | None
    speech_metrics: dict[str, int]


class VoiceLabEngine:
    """One-turn local voice lab on top of the authoritative Conversation Core."""

    INPUT_FORMAT = AudioFormat(
        sample_rate_hz=16_000,
        channels=1,
        sample_format=AudioSampleFormat.PCM_S16LE,
    )

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
        self._voice_token: CancellationToken | None = None
        self._active_trace: CorrelationContext | None = None
        self._tts_trace: CorrelationContext | None = None

    async def listen_once(self) -> tuple[str, VoiceLatencyTrace, CorrelationContext]:
        """Capture one evidence-approved utterance and only then submit it to STT.

        WebRTC VAD remains a fast signal, not final authority. Endpointed noise
        candidates are rejected locally and listening continues without ever
        asking the speech model to invent text for them.
        """

        from core.voice.evidence import SpeechEvidenceConfig, SpeechEvidenceGate

        trace = CorrelationContext.create()
        self._active_trace = trace
        token = CancellationToken()
        self._voice_token = token
        latency = VoiceLatencyTrace()
        endpoint = EndpointDetector(self.endpoint_config)
        evidence = SpeechEvidenceGate(
            frame_ms=self.endpoint_config.frame_ms,
            preroll_frames=max(1, self.endpoint_config.preroll_ms // self.endpoint_config.frame_ms),
            config=SpeechEvidenceConfig(),
        )
        activity = SpeechActivityFusion()
        accepted_frames: tuple[AudioFrame, ...] | None = None

        async for frame in self.audio_input.stream(
            trace=trace,
            audio_format=self.INPUT_FORMAT,
            frame_ms=self.endpoint_config.frame_ms,
            cancellation_token=token,
        ):
            if token.is_cancelled:
                break
            vad_speech = self.vad.is_speech(frame)
            activity_decision = activity.classify(frame, vad_speech=vad_speech)
            signal = endpoint.accept(activity_decision.active)
            if signal is EndpointSignal.SPEECH_STARTED:
                latency.mark("speech_started")
                self.conversation.event_bus.emit(
                    "voice.speech.started",
                    origin="voice-engine",
                    trace=trace,
                    conversation_id=self.conversation.context.conversation_id,
                    payload={
                        "vad_speech": vad_speech,
                        "acoustic_rescue": activity_decision.acoustic_rescue,
                        "rms": round(activity_decision.rms, 6),
                        "acoustic_threshold_rms": round(activity_decision.acoustic_threshold_rms, 6),
                    },
                )
                if activity_decision.acoustic_rescue:
                    self.conversation.event_bus.emit(
                        "voice.speech.acoustic_rescue",
                        origin="voice-engine",
                        trace=trace,
                        conversation_id=self.conversation.context.conversation_id,
                        payload={
                            "rms": round(activity_decision.rms, 6),
                            "threshold": round(activity_decision.acoustic_threshold_rms, 6),
                            "noise_floor": round(activity_decision.noise_floor_rms, 6),
                        },
                    )

            # Evidence keeps the *raw* VAD flag so telemetry remains honest even
            # when acoustic redundancy rescued endpointing.
            candidate = evidence.push(frame, vad_speech, signal)
            if candidate is None:
                continue

            report = candidate.report
            if not report.accepted:
                self.conversation.event_bus.emit(
                    "voice.speech.rejected",
                    origin="voice-engine",
                    trace=trace,
                    conversation_id=self.conversation.context.conversation_id,
                    payload=report.as_dict(),
                )
                # A false VAD trigger is not a user turn. Reset timing/endpoint
                # state and continue listening in the same microphone session.
                endpoint.reset()
                latency = VoiceLatencyTrace()
                continue

            accepted_frames = candidate.frames
            latency.mark("speech_ended")
            self.conversation.event_bus.emit(
                "voice.speech.endpointed",
                origin="voice-engine",
                trace=trace,
                conversation_id=self.conversation.context.conversation_id,
                payload={"signal": signal.value, "evidence": report.as_dict()},
            )
            break

        if token.is_cancelled:
            raise asyncio.CancelledError(token.reason or "voice capture cancelled")
        if not accepted_frames:
            raise RuntimeError("microphone stream ended before an evidence-approved utterance")

        async def accepted_audio() -> AsyncIterator[AudioFrame]:
            for item in accepted_frames:
                yield item

        final_text = ""
        async for event in self.providers.stt.stream_transcription(accepted_audio(), token):
            if event.event_type is TranscriptionEventType.PARTIAL:
                if "stt_first_partial" not in latency.as_milliseconds():
                    latency.mark("stt_first_partial")
                self.conversation.event_bus.emit(
                    "voice.stt.partial",
                    origin="voice-engine",
                    trace=trace,
                    conversation_id=self.conversation.context.conversation_id,
                    payload={"text": event.text},
                )
            elif event.event_type is TranscriptionEventType.FINAL:
                latency.mark("stt_final")
                final_text = event.text.strip()
            elif event.event_type is TranscriptionEventType.ERROR:
                raise RuntimeError(event.detail or "STT provider error")

        if not final_text:
            raise RuntimeError("STT produced no final transcript")
        return final_text, latency, trace

    async def run_once(
        self,
        *,
        reasoning_policy: ReasoningPolicy | None = None,
    ) -> VoiceTurnResult:
        transcript, latency, capture_trace = await self.listen_once()
        self.conversation.event_bus.emit(
            "voice.transcript.committed",
            origin="voice-engine",
            trace=capture_trace,
            conversation_id=self.conversation.context.conversation_id,
            payload={"text": transcript},
        )
        latency.mark("conversation_submit")

        # Repair33 supports two controlled TTS scheduling modes:
        # - streaming: committed Repair31 behavior; Luna deltas become separate
        #   natural speech chunks and TTS overlaps intelligence generation.
        # - whole: Luna remains fully expressive, but TTS waits for the complete
        #   response and sends it to Qwen as one request for maximum continuity.
        # Physical playback still streams PCM immediately once Qwen starts.
        delta_queue: asyncio.Queue[tuple[CorrelationContext, str] | None] = asyncio.Queue()
        speech_queue: asyncio.Queue[tuple[CorrelationContext, str] | None] = asyncio.Queue(maxsize=32)
        audio_queue: asyncio.Queue[AudioFrame | None] = asyncio.Queue(maxsize=1024)
        chunker = SpeechTextChunker()
        ledger = PlaybackLedger()
        tts_token = CancellationToken()
        self._voice_token = tts_token
        first_delta = True
        first_speech_chunk = True
        first_tts_request = True
        first_tts_audio = True
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
            nonlocal first_tts_request, first_tts_audio
            while True:
                item = await speech_queue.get()
                if item is None:
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
                    ledger.queue(len(frame.payload))
                    if first_tts_audio:
                        # Chatterbox currently yields after a waveform is ready,
                        # so this isolates real synthesis time from chunking time.
                        latency.mark("tts_first_waveform_ready")
                        latency.mark("tts_first_audio")
                        first_tts_audio = False
                    await audio_queue.put(frame)

        async def audio_stream() -> AsyncIterator[AudioFrame]:
            # Native streaming TTS can benefit from a tiny provider-recommended
            # startup runway. We buffer only PCM that has already been generated;
            # text synthesis itself starts immediately. This absorbs early GPU
            # jitter without reintroducing Repair21's larger-text latency.
            startup_buffer_ms = int(self.providers.tts.metadata.extra.get("startup_buffer_ms", 0) or 0)
            buffered: list[AudioFrame] = []
            buffered_ms = 0.0
            released = startup_buffer_ms <= 0
            while True:
                item = await audio_queue.get()
                if item is None:
                    if not released:
                        for frame in buffered:
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
                        yield frame
                    buffered.clear()
                    continue
                yield item

        async def playback_worker():
            playback = await self.audio_output.play(audio_stream(), tts_token)
            ledger.played(playback.bytes_written)
            if playback.first_write_monotonic_ns is not None:
                latency.mark("audio_first_write_started", now_ns=playback.first_write_monotonic_ns)
            if playback.first_write_completed_monotonic_ns is not None:
                latency.mark(
                    "audio_first_write_completed",
                    now_ns=playback.first_write_completed_monotonic_ns,
                )
            audible_ns = (
                playback.estimated_first_audible_monotonic_ns
                or playback.first_write_monotonic_ns
            )
            if audible_ns is not None:
                latency.mark("audio_first_played", now_ns=audible_ns)
            if playback.bytes_written < 0:
                raise RuntimeError("audio output reported invalid playback bytes")
            return playback

        speech_task = (
            asyncio.create_task(speech_text_worker(), name="jarvis-voice-chunker")
            if self.tts_response_mode == "streaming"
            else None
        )
        tts_task = asyncio.create_task(tts_worker(), name="jarvis-voice-tts")
        playback_task = asyncio.create_task(playback_worker(), name="jarvis-voice-playback")
        tasks = tuple(task for task in (speech_task, tts_task, playback_task) if task is not None)
        try:
            result = await self.conversation.submit_voice(
                transcript,
                reasoning_policy=reasoning_policy or ReasoningPolicy(),
            )
            latency.mark("luna_response_complete")

            if self.tts_response_mode == "whole":
                # Do not change Jarvis's intelligence/personality policy. We wait
                # for whatever complete response Luna naturally chose to say,
                # normalize it once for speech, and give the whole thought to Qwen.
                await queue_spoken_chunk(result.trace, result.text)
                speech_metrics["whole_response_chars"] = len(normalize_speech_text(result.text))
                speech_metrics["whole_response_words"] = len(normalize_speech_text(result.text).split())
                await speech_queue.put(None)
            else:
                await delta_queue.put(None)
                assert speech_task is not None
                await speech_task

            await tts_task
            await playback_task
            latency.mark("turn_done")
            return VoiceTurnResult(
                transcript=transcript,
                response_text=result.text,
                status=result.status,
                latency_ms=latency.as_milliseconds(),
                playback=ledger,
                turn_id=result.trace.turn_id,
                speech_metrics=speech_metrics,
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
            self._active_trace = None
            self._tts_trace = None
            self._voice_token = None

    async def interrupt(self, reason: str = "user interruption") -> bool:
        """Cancellation skeleton used by 0.0.5 barge-in detection later."""

        did_anything = False
        token = self._voice_token
        if token is not None and not token.is_cancelled:
            token.cancel(reason)
            did_anything = True
        if self._active_trace is not None:
            await self.providers.stt.cancel(self._active_trace.request_id)
            did_anything = True
        if self._tts_trace is not None:
            await self.providers.tts.cancel(self._tts_trace.request_id)
            did_anything = True
        await self.audio_output.stop()
        if await self.conversation.cancel_active_turn(reason):
            did_anything = True
        return did_anything
