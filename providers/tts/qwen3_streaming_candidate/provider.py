"""Resident true-streaming Qwen3-TTS candidate for Voice Lab.

Repair24 keeps the experimental Qwen streaming runtime isolated from Jarvis's
main Python environment. One child process loads Qwen once, prepares the active
voice once, warms compilation before listening, then serves many synthesis
requests as PCM16 chunks over a small framed stdio protocol.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

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

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class Qwen3StreamingConfig:
    python_executable: Path = PROJECT_ROOT / ".runtime" / "voice" / "qwen3_tts_streaming_candidate" / ".venv" / "Scripts" / "python.exe"
    model_dir: Path = PROJECT_ROOT / ".runtime" / "voice" / "qwen3_tts" / "models" / "Qwen3-TTS-12Hz-0.6B-Base"
    sidecar: Path = Path(__file__).with_name("live_sidecar.py")
    startup_timeout_s: float = 120.0
    command_timeout_s: float = 240.0
    startup_buffer_ms: int = 250
    emit_every_frames: int = 4
    decode_window_frames: int = 80
    # Repair31 A/B only. None preserves Repair27's original stochastic behavior.
    # When set, the resident sidecar resets the same RNG seed immediately before
    # each separate synthesis request so sentence 1/2/3 begin from the same
    # sampling state without changing Qwen's generation parameters.
    fixed_seed: int | None = None

    def __post_init__(self) -> None:
        if self.fixed_seed is not None and not 0 <= self.fixed_seed <= 0xFFFFFFFF:
            raise ValueError("fixed_seed must be between 0 and 4294967295")


class Qwen3StreamingProvider(TextToSpeechProvider):
    """Experimental resident Qwen fork with real incremental PCM output."""

    def __init__(self, config: Qwen3StreamingConfig | None = None) -> None:
        self.config = config or Qwen3StreamingConfig()
        self._process: asyncio.subprocess.Process | None = None
        self._io_lock = asyncio.Lock()
        self._startup_lock = asyncio.Lock()
        self._prepared_voice_key: tuple[str, str, bool] | None = None
        self._active_request_ids: set[str] = set()
        self._runtime_dir = PROJECT_ROOT / ".runtime" / "voice" / "qwen3_tts_streaming_candidate"
        self._cancel_dir = self._runtime_dir / "cancel"
        self._log_dir = self._runtime_dir / "logs"
        self._stderr_path = self._log_dir / "live-sidecar-stderr.log"
        self._stderr_handle: BinaryIO | None = None

    @property
    def metadata(self) -> SpeechProviderMetadata:
        return SpeechProviderMetadata(
            provider="qwen3-tts-streaming-candidate",
            model="12hz-0.6b-base-streaming",
            local=True,
            streaming_input=False,
            streaming_output=True,
            voice_cloning=True,
            extra={
                "transport": "resident-binary-sidecar",
                "native_streaming": True,
                "startup_buffer_ms": self.config.startup_buffer_ms,
                "startup_buffer_strategy": "single-frame-fast-start",
                "fixed_seed": self.config.fixed_seed,
                "seed_strategy": "per-request-reset" if self.config.fixed_seed is not None else "upstream-random",
                "license": "Apache-2.0",
                "experimental": True,
            },
        )

    async def health(self) -> SpeechProviderHealth:
        if not self.config.python_executable.is_file():
            return SpeechProviderHealth("unavailable", f"candidate runtime missing: {self.config.python_executable}")
        if not self.config.sidecar.is_file():
            return SpeechProviderHealth("unavailable", f"candidate sidecar missing: {self.config.sidecar}")
        if not (self.config.model_dir / "config.json").is_file():
            return SpeechProviderHealth("unavailable", f"Qwen model missing: {self.config.model_dir}")
        try:
            await self._ensure_process()
        except Exception as exc:
            detail = self._stderr_tail()
            suffix = f" | stderr: {detail}" if detail else ""
            return SpeechProviderHealth("error", f"{type(exc).__name__}: {exc}{suffix}")
        return SpeechProviderHealth("ready", "resident streaming worker loaded")

    async def warmup(self, voice: VoiceProfile) -> None:
        """Prepare clone conditioning and compile the hot streaming path once."""
        await self._ensure_process()
        await self._prepare_voice(voice)
        request_id = "repair24-warmup"
        async with self._io_lock:
            await self._send({
                "op": "warmup",
                "id": request_id,
                "text": "A day on Venus is longer than its year. Venus takes 243 Earth days to rotate once, but only 225 days to orbit the Sun.",
            })
            message = await self._read_message(timeout=self.config.command_timeout_s)
            self._check_response(message, request_id)
            if message.get("event") != "warmup_complete":
                raise RuntimeError(f"unexpected streaming warmup response: {message}")

    async def stream_speech(
        self,
        trace: CorrelationContext,
        text: str,
        voice: VoiceProfile,
        cancellation_token: CancellationToken,
    ):
        if not text.strip():
            return
        await self._ensure_process()
        await self._prepare_voice(voice)
        request_id = trace.request_id
        self._active_request_ids.add(request_id)
        sequence = 0
        cancel_flag = self._cancel_flag_path(request_id)
        cancel_flag.parent.mkdir(parents=True, exist_ok=True)
        cancel_flag.unlink(missing_ok=True)
        try:
            async with self._io_lock:
                await self._send({
                    "op": "synthesize",
                    "id": request_id,
                    "text": text,
                })
                while True:
                    # Once synthesis starts, cancellation is cooperative. The
                    # sidecar emits a terminal `cancelled` event after it stops
                    # its generator. We must keep draining framed PCM until that
                    # event so the resident protocol remains synchronized.
                    read_timeout = 5.0 if cancellation_token.is_cancelled else self.config.command_timeout_s
                    try:
                        message = await self._read_message(timeout=read_timeout)
                    except (RuntimeError, TimeoutError, asyncio.IncompleteReadError):
                        if cancellation_token.is_cancelled:
                            await self._kill_process()
                            return
                        raise
                    self._check_response(message, request_id)
                    event = message.get("event")
                    if event == "audio_chunk":
                        byte_count = int(message.get("bytes", 0))
                        sample_rate = int(message.get("sample_rate", 0))
                        if byte_count <= 0 or sample_rate <= 0:
                            raise RuntimeError(f"invalid streaming audio header: {message}")
                        process = self._process
                        if process is None or process.stdout is None:
                            if cancellation_token.is_cancelled:
                                return
                            raise RuntimeError("streaming sidecar disappeared while reading PCM")
                        try:
                            payload = await asyncio.wait_for(
                                process.stdout.readexactly(byte_count),
                                timeout=read_timeout,
                            )
                        except (asyncio.IncompleteReadError, TimeoutError):
                            if cancellation_token.is_cancelled:
                                await self._kill_process()
                                return
                            raise
                        if not cancellation_token.is_cancelled:
                            yield AudioFrame(
                                trace=trace,
                                sequence=sequence,
                                format=AudioFormat(sample_rate, 1, AudioSampleFormat.PCM_S16LE),
                                payload=payload,
                            )
                            sequence += 1
                        continue
                    if event in {"complete", "cancelled"}:
                        return
                    raise RuntimeError(f"unexpected streaming synthesis event: {message}")
        finally:
            self._active_request_ids.discard(request_id)
            cancel_flag.unlink(missing_ok=True)

    async def cancel(self, request_id: str) -> None:
        # 0.0.5 repair1: do not destroy the resident Qwen process on normal
        # barge-in. The sidecar checks this flag between streaming chunks, stops
        # the active generator, emits `cancelled`, and stays hot for the next turn.
        if request_id not in self._active_request_ids:
            return
        flag = self._cancel_flag_path(request_id)
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text("cancel", encoding="utf-8")

    def _cancel_flag_path(self, request_id: str) -> Path:
        digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
        return self._cancel_dir / f"{digest}.cancel"

    async def close(self) -> None:
        process = self._process
        if process is not None and process.returncode is None and process.stdin is not None:
            try:
                process.stdin.write(b'{"op":"shutdown","id":"shutdown"}\n')
                await process.stdin.drain()
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except Exception:
                await self._kill_process()
        self._process = None
        self._prepared_voice_key = None
        self._close_stderr_handle()

    async def _prepare_voice(self, voice: VoiceProfile) -> None:
        reference = str(voice.reference_audio_path or "").strip()
        if not reference:
            raise ValueError("Qwen streaming candidate requires a voice reference")
        language = str(voice.settings.get("language") or "English")
        # Preserve Repair20's accepted behavior: x-vector-only cloning is the
        # live default even when a transcript exists.
        x_vector_only = True
        key = (str(Path(reference).resolve()), language, x_vector_only)
        if self._prepared_voice_key == key:
            return
        request_id = "prepare-voice"
        async with self._io_lock:
            await self._send({
                "op": "prepare_voice",
                "id": request_id,
                "reference": key[0],
                "language": language,
                "x_vector_only": x_vector_only,
            })
            message = await self._read_message(timeout=self.config.command_timeout_s)
            self._check_response(message, request_id)
            if message.get("event") != "voice_ready":
                raise RuntimeError(f"unexpected voice preparation response: {message}")
            self._prepared_voice_key = key

    async def _ensure_process(self) -> None:
        process = self._process
        if process is not None and process.returncode is None:
            return
        async with self._startup_lock:
            process = self._process
            if process is not None and process.returncode is None:
                return
            self._log_dir.mkdir(parents=True, exist_ok=True)
            self._stderr_handle = self._stderr_path.open("ab", buffering=0)
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0)
            self._cancel_dir.mkdir(parents=True, exist_ok=True)
            sidecar_args = [
                str(self.config.python_executable),
                str(self.config.sidecar),
                "--model-dir", str(self.config.model_dir),
                "--emit-every-frames", str(self.config.emit_every_frames),
                "--decode-window-frames", str(self.config.decode_window_frames),
                "--cancel-dir", str(self._cancel_dir),
            ]
            if self.config.fixed_seed is not None:
                sidecar_args.extend(["--fixed-seed", str(self.config.fixed_seed)])
            self._process = await asyncio.create_subprocess_exec(
                *sidecar_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=self._stderr_handle,
                cwd=str(PROJECT_ROOT),
                creationflags=creationflags,
            )
            try:
                message = await self._read_message(timeout=self.config.startup_timeout_s)
            except Exception:
                await self._kill_process()
                raise
            if message.get("event") == "startup_error":
                error = str(message.get("error") or "unknown streaming sidecar startup error")
                await self._kill_process()
                raise RuntimeError(error)
            if message.get("event") != "ready":
                await self._kill_process()
                raise RuntimeError(f"unexpected streaming sidecar startup message: {message}")
            self._prepared_voice_key = None

    async def _send(self, payload: dict) -> None:
        process = self._process
        if process is None or process.stdin is None or process.returncode is not None:
            raise RuntimeError("streaming sidecar is not running")
        process.stdin.write((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))
        await process.stdin.drain()

    async def _read_message(self, *, timeout: float) -> dict:
        process = self._process
        if process is None or process.stdout is None:
            raise RuntimeError("streaming sidecar is not running")
        line = await asyncio.wait_for(process.stdout.readline(), timeout=timeout)
        if not line:
            code = await process.wait()
            self._process = None
            detail = self._stderr_tail()
            suffix = f" | stderr: {detail}" if detail else ""
            raise RuntimeError(f"streaming sidecar exited unexpectedly ({code}){suffix}")
        try:
            return json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid streaming sidecar protocol: {line[:200]!r}") from exc

    @staticmethod
    def _check_response(message: dict, request_id: str) -> None:
        if message.get("id") != request_id:
            raise RuntimeError(f"streaming sidecar response ID mismatch: {message}")
        if message.get("event") == "error" or message.get("ok") is False:
            raise RuntimeError(str(message.get("error") or "streaming sidecar error"))

    async def _kill_process(self) -> None:
        process = self._process
        self._process = None
        self._prepared_voice_key = None
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
