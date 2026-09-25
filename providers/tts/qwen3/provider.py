"""Replaceable local Qwen3-TTS 0.6B Base voice-cloning adapter."""

from __future__ import annotations

import asyncio
import json
import os
import wave
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.voice import (
    AudioFormat,
    AudioFrame,
    AudioSampleFormat,
    SpeechProviderHealth,
    SpeechProviderMetadata,
    TextToSpeechProvider,
    VoiceProfile,
)
from providers.tts.qwen3.config import PROJECT_ROOT, Qwen3TTSConfig


class Qwen3TTSProvider(TextToSpeechProvider):
    """Official Qwen3-TTS Python runtime isolated behind a JSON-line sidecar.

    This provider intentionally keeps Qwen/PyTorch out of Jarvis Core's main
    environment. It is an A/B candidate beside Chatterbox, not a hard dependency.
    """

    def __init__(self, config: Qwen3TTSConfig | None = None) -> None:
        self.config = config or Qwen3TTSConfig.from_env()
        self._process: asyncio.subprocess.Process | None = None
        self._io_lock = asyncio.Lock()
        self._startup_lock = asyncio.Lock()
        self._active_request_ids: set[str] = set()
        self._runtime_dir = PROJECT_ROOT / ".runtime" / "voice" / "qwen3_tts"
        self._output_dir = self._runtime_dir / "output"
        self._log_dir = self._runtime_dir / "logs"
        self._stderr_path = self._log_dir / "sidecar-stderr.log"
        self._stderr_handle: BinaryIO | None = None

    @property
    def metadata(self) -> SpeechProviderMetadata:
        return SpeechProviderMetadata(
            provider="qwen3-tts",
            model="12hz-0.6b-base",
            local=True,
            streaming_input=False,
            streaming_output=True,
            voice_cloning=True,
            extra={
                "transport": "isolated-sidecar",
                "native_streaming": False,
                "license": "Apache-2.0",
                "clone_reference": "required",
            },
        )

    async def health(self) -> SpeechProviderHealth:
        if not self.config.python_executable.is_file():
            return SpeechProviderHealth(
                "not-configured",
                f"missing Qwen3-TTS runtime Python: {self.config.python_executable}",
            )
        if not self.config.model_dir.is_dir():
            return SpeechProviderHealth(
                "not-configured",
                f"missing Qwen3-TTS model directory: {self.config.model_dir}",
            )
        try:
            await self._ensure_process()
            response = await self._request({"op": "health"})
            if response.get("ok"):
                return SpeechProviderHealth(
                    "ready",
                    f"Qwen3-TTS 0.6B Base ready on {self.config.device}",
                )
            return SpeechProviderHealth("error", str(response.get("error", "unknown sidecar error")))
        except Exception as exc:  # pragma: no cover - live runtime path
            detail = f"Qwen3-TTS startup failed: {type(exc).__name__}: {exc}"
            tail = self._stderr_tail()
            if tail:
                detail += f" | sidecar log tail: {tail}"
            return SpeechProviderHealth("error", detail)

    async def diagnose_reference(
        self,
        *,
        reference_audio_path: str,
        reference_text: str | None,
    ) -> dict:
        response = await self._request(
            {
                "op": "diagnose_reference",
                "reference_audio_path": reference_audio_path,
                "reference_text": reference_text,
            }
        )
        if not response.get("ok"):
            raise RuntimeError(str(response.get("error", "Qwen reference diagnostic failed")))
        return dict(response["reference"])

    async def upstream_smoke(
        self,
        *,
        text: str,
        reference_audio_path: str,
        reference_text: str | None,
        language: str = "English",
        x_vector_only: bool = False,
    ) -> dict:
        response = await asyncio.wait_for(
            self._request(
                {
                    "op": "upstream_smoke",
                    "text": text,
                    "reference_audio_path": reference_audio_path,
                    "reference_text": reference_text,
                    "language": language,
                    "x_vector_only": x_vector_only,
                }
            ),
            timeout=self.config.synthesis_timeout_s,
        )
        if not response.get("ok"):
            raise RuntimeError(str(response.get("error", "Qwen upstream smoke failed")))
        return response

    async def cancel(self, request_id: str) -> None:
        if request_id in self._active_request_ids:
            # The current official Python API does not expose cooperative
            # generation cancellation. Keep cancellation bounded to this adapter
            # by killing/restarting only the Qwen worker.
            await self._kill_process()

    async def close(self) -> None:
        process = self._process
        if process is None:
            self._close_stderr_handle()
            return
        try:
            await asyncio.wait_for(self._request({"op": "shutdown"}), timeout=2.0)
        except Exception:
            pass
        await self._kill_process()

    async def stream_speech(
        self,
        trace: CorrelationContext,
        text: str,
        voice: VoiceProfile,
        cancellation_token: CancellationToken,
    ) -> AsyncIterator[AudioFrame]:
        prompt = text.strip()
        if not prompt:
            return
        if not voice.reference_audio_path:
            raise RuntimeError(
                "Qwen3-TTS Base requires VoiceProfile.reference_audio_path for voice cloning"
            )
        await self._ensure_process()
        request_id = trace.request_id
        self._active_request_ids.add(request_id)
        path: Path | None = None
        try:
            settings = dict(voice.settings)
            payload = {
                "op": "synthesize",
                "text": prompt,
                "reference_audio_path": voice.reference_audio_path,
                "reference_text": settings.get("reference_text"),
                "language": settings.get("language", "English"),
                "settings": settings,
            }
            response = await asyncio.wait_for(
                self._request(payload),
                timeout=self.config.synthesis_timeout_s,
            )
            if cancellation_token.is_cancelled:
                return
            if not response.get("ok"):
                raise RuntimeError(str(response.get("error", "Qwen3-TTS synthesis failed")))
            path = Path(str(response["path"]))
            sequence = 0
            with wave.open(str(path), "rb") as handle:
                if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
                    raise RuntimeError("Qwen3-TTS sidecar returned unsupported WAV format")
                sample_rate = int(handle.getframerate())
                audio_format = AudioFormat(
                    sample_rate_hz=sample_rate,
                    channels=1,
                    sample_format=AudioSampleFormat.PCM_S16LE,
                )
                frames_per_chunk = max(1, int(sample_rate * self.config.frame_ms / 1000))
                while not cancellation_token.is_cancelled:
                    chunk = handle.readframes(frames_per_chunk)
                    if not chunk:
                        break
                    yield AudioFrame(
                        trace=trace,
                        sequence=sequence,
                        format=audio_format,
                        payload=chunk,
                    )
                    sequence += 1
        finally:
            self._active_request_ids.discard(request_id)
            if path is not None:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass

    async def _ensure_process(self) -> None:
        if self._process is not None and self._process.returncode is None:
            return
        async with self._startup_lock:
            if self._process is not None and self._process.returncode is None:
                return
            python = self.config.python_executable
            if not python.is_file():
                raise FileNotFoundError(python)
            sidecar = Path(__file__).with_name("sidecar.py")
            self._output_dir.mkdir(parents=True, exist_ok=True)
            self._log_dir.mkdir(parents=True, exist_ok=True)
            self._close_stderr_handle()
            self._stderr_handle = self._stderr_path.open("wb")
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0)
            self._process = await asyncio.create_subprocess_exec(
                str(python),
                str(sidecar),
                "--device",
                self.config.device,
                "--dtype",
                self.config.dtype,
                "--attention",
                self.config.attention,
                "--model-dir",
                str(self.config.model_dir),
                "--output-dir",
                str(self._output_dir),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=self._stderr_handle,
                creationflags=creationflags,
            )
            assert self._process.stdout is not None
            try:
                line = await asyncio.wait_for(
                    self._process.stdout.readline(), timeout=self.config.startup_timeout_s
                )
            except TimeoutError as exc:
                await self._kill_process()
                raise RuntimeError(
                    f"Qwen3-TTS sidecar startup timed out after {self.config.startup_timeout_s:.0f}s"
                ) from exc
            if not line:
                code = await self._process.wait()
                self._process = None
                self._close_stderr_handle()
                raise RuntimeError(f"Qwen3-TTS sidecar exited during startup ({code})")
            try:
                message = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError as exc:
                await self._kill_process()
                raise RuntimeError(f"invalid Qwen3-TTS startup protocol: {line[:200]!r}") from exc
            if message.get("event") == "startup_error":
                error = str(message.get("error", "unknown Qwen3-TTS startup error"))
                await self._kill_process()
                raise RuntimeError(error)
            if message.get("event") != "ready":
                await self._kill_process()
                raise RuntimeError(f"unexpected Qwen3-TTS startup message: {message}")

    async def _request(self, payload: dict) -> dict:
        await self._ensure_process()
        process = self._process
        assert process is not None and process.stdin is not None and process.stdout is not None
        request_id = str(payload.get("id") or uuid4().hex)
        payload = dict(payload, id=request_id)
        async with self._io_lock:
            process.stdin.write((json.dumps(payload, separators=(",", ":")) + "\n").encode())
            await process.stdin.drain()
            line = await process.stdout.readline()
            if not line:
                raise RuntimeError("Qwen3-TTS sidecar closed unexpectedly")
            response = json.loads(line.decode("utf-8"))
            if response.get("id") != request_id:
                raise RuntimeError("Qwen3-TTS sidecar response ID mismatch")
            return response

    async def _kill_process(self) -> None:
        process = self._process
        self._process = None
        if process is not None and process.returncode is None:
            process.kill()
            try:
                await asyncio.wait_for(process.wait(), timeout=4.0)
            except TimeoutError:
                pass
        self._close_stderr_handle()

    def _close_stderr_handle(self) -> None:
        handle = self._stderr_handle
        self._stderr_handle = None
        if handle is not None:
            try:
                handle.flush()
            except OSError:
                pass
            try:
                handle.close()
            except OSError:
                pass

    def _stderr_tail(self, *, max_chars: int = 4000) -> str:
        try:
            if self._stderr_handle is not None:
                self._stderr_handle.flush()
            if not self._stderr_path.is_file():
                return ""
            text = self._stderr_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        compact = " | ".join(line.strip() for line in text.splitlines() if line.strip())
        return compact[-max_chars:]
