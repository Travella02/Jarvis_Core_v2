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
import os
import subprocess
import urllib.error
import urllib.request
import uuid
import wave
from collections.abc import AsyncIterator
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


class WhisperCppProvider(SpeechToTextProvider):
    def __init__(self, config: WhisperCppConfig | None = None) -> None:
        self.config = config or WhisperCppConfig.from_env()
        self._process: subprocess.Popen[bytes] | None = None
        self._process_lock = asyncio.Lock()
        self._active_requests: dict[str, CancellationToken] = {}

    @property
    def metadata(self) -> SpeechProviderMetadata:
        return SpeechProviderMetadata(
            provider="whisper.cpp",
            model="large-v3-turbo-q5_0",
            local=True,
            streaming_input=True,
            streaming_output=True,
            voice_cloning=False,
            extra={"transport": "localhost-server", "quantization": "q5_0"},
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
                text = await self._transcribe(snapshot)
                if cancellation_token.is_cancelled:
                    return
                normalized = text.strip()
                if normalized and normalized != last_partial_text:
                    last_partial_text = normalized
                    await event_queue.put(
                        TranscriptionEvent(
                            trace=snapshot[0].trace,
                            event_type=TranscriptionEventType.PARTIAL,
                            text=normalized,
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
                        elapsed_ms >= self.config.min_partial_audio_ms
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
                text = (await self._transcribe(tuple(frames))).strip()
                await event_queue.put(
                    TranscriptionEvent(
                        trace=frames[0].trace,
                        event_type=TranscriptionEventType.FINAL,
                        text=text,
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
        wav = self._wav_bytes(frames)
        return await asyncio.to_thread(self._post_wav, wav)

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

    def _post_wav(self, wav_bytes: bytes) -> str:
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
        field("response_format", "text")
        field("language", self.config.language)
        field("temperature", "0.0")
        field("no_timestamps", "true")
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
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"whisper-server HTTP {exc.code}: {detail}") from exc
