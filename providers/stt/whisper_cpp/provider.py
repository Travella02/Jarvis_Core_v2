"""Local whisper.cpp STT adapter using a persistent localhost whisper-server.

The server transport is intentionally adapter-local. Voice Core only sees the
SpeechToTextProvider contract, so a future native binding, Moonshine, cloud STT,
or another engine can replace this class without changing Conversation Core.

0.0.4 partials are produced by bounded rolling re-inference while audio is still
arriving. This is a lab-quality streaming strategy, not a promise that repeated
window inference is the final production transport.
"""

from __future__ import annotations

import asyncio
import io
import json
import math
import os
import subprocess
import urllib.error
import urllib.request
import uuid
import wave
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.voice import (
    AudioFormat,
    AudioFrame,
    AudioSampleFormat,
    SpeechProviderHealth,
    SpeechProviderMetadata,
    SpeechToTextProvider,
    TranscriptionEvent,
    TranscriptionEventType,
)
from providers.stt.whisper_cpp.config import WhisperCppConfig




@dataclass(frozen=True, slots=True)
class _WhisperInference:
    text: str
    confidence: float | None = None
    no_speech_probability: float | None = None


class WhisperCppProvider(SpeechToTextProvider):
    def __init__(self, config: WhisperCppConfig | None = None) -> None:
        self.config = config or WhisperCppConfig.from_env()
        self._process: subprocess.Popen[bytes] | None = None
        self._process_lock = asyncio.Lock()
        self._active_requests: dict[str, CancellationToken] = {}
        self._last_inference: _WhisperInference | None = None

    @property
    def metadata(self) -> SpeechProviderMetadata:
        return SpeechProviderMetadata(
            provider="whisper.cpp",
            model="large-v3-turbo-q5_0",
            local=True,
            streaming_input=True,
            streaming_output=True,
            voice_cloning=False,
            extra={
                "transport": "localhost-server",
                "quantization": "q5_0",
                "partials": bool(self.config.emit_partials),
                "endpointed_final_only": not bool(self.config.emit_partials),
                "suppress_non_speech": bool(self.config.suppress_non_speech),
                "no_speech_threshold": self.config.no_speech_threshold,
            },
        )

    async def health(self) -> SpeechProviderHealth:
        if not self.config.server_executable.is_file():
            return SpeechProviderHealth("not-configured", f"missing whisper-server: {self.config.server_executable}")
        if not self.config.model_path.is_file():
            return SpeechProviderHealth("not-configured", f"missing model: {self.config.model_path}")
        try:
            await self._ensure_server()
            return SpeechProviderHealth("ready", "local whisper.cpp server ready")
        except Exception as exc:  # pragma: no cover - live runtime path
            return SpeechProviderHealth("error", f"whisper.cpp startup failed: {type(exc).__name__}: {exc}")

    async def warmup(self) -> None:
        """Run one hidden local inference so the first user turn stays warm.

        whisper-server startup proves the model is loaded, but CUDA kernels can
        still be cold until the first inference. Feed a short silent PCM clip
        directly through the adapter and discard the transcript.
        """

        await self._ensure_server()
        trace = CorrelationContext.create()
        fmt = AudioFormat(16_000, 1, AudioSampleFormat.PCM_S16LE)
        frame = AudioFrame(
            trace=trace,
            sequence=0,
            format=fmt,
            payload=b"\x00\x00" * 16_000,
        )
        await self._transcribe((frame,))

    async def cancel(self, request_id: str) -> None:
        token = self._active_requests.get(request_id)
        if token is not None:
            token.cancel("STT request cancelled")
        # urllib requests cannot be force-aborted portably from another coroutine.
        # Results are discarded immediately via the token. 0.0.5 may replace this
        # transport with a native streaming binding for harder cancellation.

    async def close(self) -> None:
        process = self._process
        self._process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=4.0)
            except TimeoutError:
                process.kill()

    async def stream_transcription(
        self,
        audio: AsyncIterator[AudioFrame],
        cancellation_token: CancellationToken,
    ) -> AsyncIterator[TranscriptionEvent]:
        await self._ensure_server()
        frames: list[AudioFrame] = []
        event_queue: asyncio.Queue[TranscriptionEvent | None] = asyncio.Queue()
        partial_task: asyncio.Task[None] | None = None
        request_id: str | None = None
        last_partial_text = ""
        elapsed_ms = 0.0
        last_partial_started_ms = 0.0

        async def run_partial(snapshot: tuple[AudioFrame, ...]) -> None:
            nonlocal last_partial_text
            try:
                inference = await self._transcribe_with_metadata(snapshot)
                if cancellation_token.is_cancelled:
                    return
                normalized = inference.text.strip()
                if normalized and normalized != last_partial_text:
                    last_partial_text = normalized
                    await event_queue.put(
                        TranscriptionEvent(
                            trace=snapshot[0].trace,
                            event_type=TranscriptionEventType.PARTIAL,
                            text=normalized,
                            confidence=inference.confidence,
                            audio_end_ms=round(sum(item.duration_ms for item in snapshot)),
                        )
                    )
            except Exception as exc:
                await event_queue.put(
                    TranscriptionEvent(
                        trace=snapshot[0].trace,
                        event_type=TranscriptionEventType.ERROR,
                        detail=f"partial transcription failed: {type(exc).__name__}: {exc}",
                    )
                )

        async def ingest() -> None:
            nonlocal partial_task, request_id, elapsed_ms, last_partial_started_ms
            try:
                async for frame in audio:
                    if request_id is None:
                        request_id = frame.trace.request_id
                        self._active_requests[request_id] = cancellation_token
                    if cancellation_token.is_cancelled:
                        await event_queue.put(
                            TranscriptionEvent(
                                trace=frame.trace,
                                event_type=TranscriptionEventType.CANCELLED,
                                detail=cancellation_token.reason,
                            )
                        )
                        return
                    self._validate_frame(frame)
                    frames.append(frame)
                    elapsed_ms += frame.duration_ms
                    due = (
                        self.config.emit_partials
                        and elapsed_ms >= self.config.min_partial_audio_ms
                        and elapsed_ms - last_partial_started_ms >= self.config.partial_interval_ms
                    )
                    if due and (partial_task is None or partial_task.done()):
                        last_partial_started_ms = elapsed_ms
                        partial_task = asyncio.create_task(run_partial(tuple(frames)))

                if not frames:
                    return
                if partial_task is not None:
                    await partial_task
                if cancellation_token.is_cancelled:
                    await event_queue.put(
                        TranscriptionEvent(
                            trace=frames[0].trace,
                            event_type=TranscriptionEventType.CANCELLED,
                            detail=cancellation_token.reason,
                        )
                    )
                    return
                inference = await self._transcribe_with_metadata(tuple(frames))
                text = inference.text.strip()
                await event_queue.put(
                    TranscriptionEvent(
                        trace=frames[0].trace,
                        event_type=TranscriptionEventType.FINAL,
                        text=text,
                        confidence=inference.confidence,
                        detail=(
                            f"no_speech_probability={inference.no_speech_probability:.4f}"
                            if inference.no_speech_probability is not None
                            else None
                        ),
                        audio_end_ms=round(sum(item.duration_ms for item in frames)),
                    )
                )
            except Exception as exc:
                trace = frames[0].trace if frames else None
                if trace is not None:
                    await event_queue.put(
                        TranscriptionEvent(
                            trace=trace,
                            event_type=TranscriptionEventType.ERROR,
                            detail=f"transcription failed: {type(exc).__name__}: {exc}",
                        )
                    )
                else:
                    raise
            finally:
                if request_id is not None:
                    self._active_requests.pop(request_id, None)
                await event_queue.put(None)

        ingest_task = asyncio.create_task(ingest())
        try:
            while True:
                item = await event_queue.get()
                if item is None:
                    break
                yield item
        finally:
            if not ingest_task.done():
                cancellation_token.cancel("STT consumer closed")
            await ingest_task

    @staticmethod
    def _validate_frame(frame: AudioFrame) -> None:
        if frame.format.sample_rate_hz != 16000:
            raise ValueError("whisper.cpp Voice Lab adapter expects 16 kHz audio")
        if frame.format.channels != 1:
            raise ValueError("whisper.cpp Voice Lab adapter expects mono audio")
        if frame.format.sample_format is not AudioSampleFormat.PCM_S16LE:
            raise ValueError("whisper.cpp Voice Lab adapter expects PCM_S16LE")

    async def _ensure_server(self) -> None:
        if self._process is not None and self._process.poll() is None:
            if await asyncio.to_thread(self._probe_server):
                return
        async with self._process_lock:
            if self._process is not None and self._process.poll() is None:
                if await asyncio.to_thread(self._probe_server):
                    return
            exe = self.config.server_executable
            model = self.config.model_path
            if not exe.is_file():
                raise FileNotFoundError(exe)
            if not model.is_file():
                raise FileNotFoundError(model)
            creationflags = 0
            if os.name == "nt":  # keep the lab server from opening a second console window
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            command = [
                str(exe),
                "-m",
                str(model),
                "--host",
                self.config.host,
                "--port",
                str(self.config.port),
                "-t",
                str(self.config.threads),
                "--language",
                self.config.language,
            ]
            if not self.config.use_gpu:
                command.append("--no-gpu")
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            deadline = asyncio.get_running_loop().time() + self.config.startup_timeout_s
            while asyncio.get_running_loop().time() < deadline:
                if self._process.poll() is not None:
                    raise RuntimeError(f"whisper-server exited with code {self._process.returncode}")
                if await asyncio.to_thread(self._probe_server):
                    return
                await asyncio.sleep(0.2)
            raise TimeoutError("timed out waiting for local whisper-server")

    def _probe_server(self) -> bool:
        try:
            with urllib.request.urlopen(
                f"http://{self.config.host}:{self.config.port}/",
                timeout=0.4,
            ) as response:
                return 200 <= response.status < 500
        except (OSError, urllib.error.URLError):
            return False

    async def _transcribe(self, frames: tuple[AudioFrame, ...]) -> str:
        """Compatibility text API used by existing tests and warmup paths."""

        wav = self._wav_bytes(frames)
        inference = await asyncio.to_thread(self._post_wav_inference, wav)
        self._last_inference = inference
        return inference.text

    async def _transcribe_with_metadata(
        self,
        frames: tuple[AudioFrame, ...],
    ) -> _WhisperInference:
        # Keep `_transcribe()` as the override point used by existing provider
        # tests/adapters. The default implementation records metadata from the
        # same inference, so confidence does not require a second Whisper pass.
        self._last_inference = None
        text = await self._transcribe(frames)
        cached = self._last_inference
        if cached is not None and cached.text.strip() == text.strip():
            return cached
        return _WhisperInference(text=text)

    @staticmethod
    def _wav_bytes(frames: tuple[AudioFrame, ...]) -> bytes:
        if not frames:
            raise ValueError("cannot encode empty audio")
        fmt = frames[0].format
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as handle:
            handle.setnchannels(fmt.channels)
            handle.setsampwidth(fmt.bytes_per_sample)
            handle.setframerate(fmt.sample_rate_hz)
            handle.writeframes(b"".join(frame.payload for frame in frames))
        return buffer.getvalue()

    @staticmethod
    def _confidence_from_verbose_json(payload: object) -> tuple[float | None, float | None]:
        """Extract generic ASR confidence/no-speech evidence from whisper.cpp.

        whisper.cpp verbose_json exposes token/word probabilities and, in current
        builds, segment no-speech probabilities. The parser is deliberately
        tolerant so older/newer compatible server builds can omit fields without
        breaking transcription.
        """

        if not isinstance(payload, dict):
            return None, None

        word_probabilities: list[float] = []
        token_probabilities: list[float] = []
        no_speech: list[float] = []
        avg_logprobs: list[float] = []

        def collect_items(items: object, target: list[float]) -> None:
            if not isinstance(items, list):
                return
            for item in items:
                if not isinstance(item, dict):
                    continue
                prob = item.get("probability")
                if isinstance(prob, (int, float)) and 0.0 <= float(prob) <= 1.0:
                    target.append(float(prob))

        segments = payload.get("segments")
        if isinstance(segments, list):
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                collect_items(segment.get("words"), word_probabilities)
                collect_items(segment.get("tokens"), token_probabilities)
                nsp = segment.get("no_speech_prob")
                if isinstance(nsp, (int, float)) and 0.0 <= float(nsp) <= 1.0:
                    no_speech.append(float(nsp))
                avg_lp = segment.get("avg_logprob")
                if isinstance(avg_lp, (int, float)):
                    avg_logprobs.append(float(avg_lp))

        # Some compatible server versions expose word/token arrays at top level.
        collect_items(payload.get("words"), word_probabilities)
        collect_items(payload.get("tokens"), token_probabilities)

        probabilities = word_probabilities or token_probabilities
        if probabilities:
            lexical_confidence = sum(probabilities) / len(probabilities)
        elif avg_logprobs:
            # avg_logprob is natural-log token probability in Whisper-family
            # output. Convert it into a bounded 0..1 score when token
            # probabilities are unavailable.
            lexical_confidence = sum(math.exp(value) for value in avg_logprobs) / len(avg_logprobs)
        else:
            lexical_confidence = None

        no_speech_probability = max(no_speech) if no_speech else None
        if lexical_confidence is not None and no_speech_probability is not None:
            # Keep no-speech evidence independent but let it modestly reduce the
            # ASR confidence from noise-like segments. Do not zero it outright:
            # short valid one-word replies can legitimately carry some no-speech
            # probability.
            lexical_confidence *= 0.75 + 0.25 * (1.0 - no_speech_probability)

        if lexical_confidence is not None:
            lexical_confidence = min(1.0, max(0.0, lexical_confidence))
        return lexical_confidence, no_speech_probability

    def _post_wav_inference(self, wav_bytes: bytes) -> _WhisperInference:
        boundary = f"----jarvis-{uuid.uuid4().hex}"
        parts: list[bytes] = []

        def field(name: str, value: str) -> None:
            parts.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                    value.encode(),
                    b"\r\n",
                ]
            )

        parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                b'Content-Disposition: form-data; name="file"; filename="jarvis.wav"\r\n',
                b"Content-Type: audio/wav\r\n\r\n",
                wav_bytes,
                b"\r\n",
            ]
        )
        # verbose_json gives Jarvis token/word probabilities from the SAME
        # inference. This adds response metadata, not a second model pass.
        field("response_format", "verbose_json")
        field("language", self.config.language)
        field("temperature", "0.0")
        field("no_timestamps", "true")
        field("suppress_nst", "true" if self.config.suppress_non_speech else "false")
        field("no_speech_thold", str(self.config.no_speech_threshold))
        parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(parts)
        request = urllib.request.Request(
            f"http://{self.config.host}:{self.config.port}/inference",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120.0) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"whisper-server HTTP {exc.code}: {detail}") from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            # Compatibility fallback for an older server unexpectedly returning
            # plain text. Speech confidence will transparently redistribute the
            # missing ASR-confidence weight over the other signals.
            return _WhisperInference(text=raw)

        if isinstance(payload, dict):
            text = str(payload.get("text") or "")
        else:
            text = raw
        confidence, no_speech_probability = self._confidence_from_verbose_json(payload)
        return _WhisperInference(
            text=text,
            confidence=confidence,
            no_speech_probability=no_speech_probability,
        )
