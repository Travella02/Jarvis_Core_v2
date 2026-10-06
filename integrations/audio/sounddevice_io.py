"""PortAudio-backed local microphone/speaker integration.

The import is lazy so Core/tests do not require an audio device or PortAudio.
0.0.4-repair7 deliberately opens microphones at their *native* device rate and
resamples into the provider-neutral Voice Core format. Many Windows headset
endpoints reject 16 kHz even though Whisper/WebRTC VAD require 16 kHz frames.
"""

from __future__ import annotations

import asyncio
import math
import sys
from array import array
from collections.abc import AsyncIterator
from dataclasses import dataclass
from time import monotonic_ns

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.voice import (
    AudioDeviceInfo,
    AudioFormat,
    AudioFrame,
    AudioInput,
    AudioOutput,
    AudioPlaybackResult,
    AudioSampleFormat,
)




@dataclass(frozen=True, slots=True)
class AudioDiagnosticCapture:
    device: AudioDeviceInfo
    native_sample_rate_hz: int
    raw_native_pcm16: bytes
    processed_frames: tuple[AudioFrame, ...]


def _sounddevice():
    try:
        import sounddevice as sd
    except ImportError as exc:  # pragma: no cover - live dependency path
        raise RuntimeError("sounddevice is not installed; run the 0.0.4 dependency install") from exc
    return sd


def _dtype(audio_format: AudioFormat) -> str:
    if audio_format.sample_format is AudioSampleFormat.PCM_S16LE:
        return "int16"
    if audio_format.sample_format is AudioSampleFormat.PCM_F32LE:
        return "float32"
    raise ValueError(f"unsupported sample format: {audio_format.sample_format}")


def _pcm16_samples(payload: bytes) -> array:
    if len(payload) % 2:
        raise ValueError("PCM16 payload must contain whole samples")
    values = array("h")
    values.frombytes(payload)
    if sys.byteorder != "little":  # pragma: no cover - Windows/x86 lab is little-endian
        values.byteswap()
    return values


def _pcm16_bytes(values: array) -> bytes:
    if sys.byteorder == "little":
        return values.tobytes()
    copy = array("h", values)
    copy.byteswap()
    return copy.tobytes()


def _resample_pcm16_mono(payload: bytes, output_samples: int) -> bytes:
    """Resample one fixed-duration mono PCM16 block with linear interpolation.

    Audio capture blocks already represent exactly frame_ms at the device's
    native rate. Producing exactly output_samples keeps WebRTC VAD frames at
    10/20/30 ms and avoids cumulative sample drift. The resampler is integration
    local, so it can later be replaced with a higher-quality/native implementation
    without changing Voice Core or STT providers.
    """

    if output_samples <= 0:
        raise ValueError("output_samples must be positive")
    source = _pcm16_samples(payload)
    if not source:
        return b"\x00\x00" * output_samples
    if len(source) == output_samples:
        return payload
    if len(source) == 1:
        return _pcm16_bytes(array("h", [source[0]]) * output_samples)
    if output_samples == 1:
        return _pcm16_bytes(array("h", [source[0]]))

    result = array("h")
    scale = (len(source) - 1) / (output_samples - 1)
    for index in range(output_samples):
        position = index * scale
        left = int(position)
        right = min(left + 1, len(source) - 1)
        fraction = position - left
        sample = round(source[left] + (source[right] - source[left]) * fraction)
        result.append(max(-32768, min(32767, sample)))
    return _pcm16_bytes(result)




def _resample_output_frame_to_rate(frame: AudioFrame, target_rate_hz: int) -> tuple[bytes, AudioFormat]:
    """Convert provider PCM16 mono audio to the physical output's native rate.

    Provider sample rate is part of the model contract, not the speaker-device
    contract.  Some Windows host APIs accept a non-native rate but reproduce it
    incorrectly.  Keep that adaptation in the audio integration layer so Qwen,
    Chatterbox, and future providers never need device-specific logic.
    """

    if target_rate_hz <= 0:
        raise ValueError("target_rate_hz must be positive")
    if (
        frame.format.sample_format is not AudioSampleFormat.PCM_S16LE
        or frame.format.channels != 1
        or frame.format.sample_rate_hz == target_rate_hz
    ):
        return frame.payload, frame.format
    source_samples = len(frame.payload) // 2
    if source_samples <= 0:
        return frame.payload, AudioFormat(target_rate_hz, 1, AudioSampleFormat.PCM_S16LE)
    target_samples = max(1, round(source_samples * target_rate_hz / frame.format.sample_rate_hz))
    payload = _resample_pcm16_mono(frame.payload, target_samples)
    return payload, AudioFormat(target_rate_hz, 1, AudioSampleFormat.PCM_S16LE)


class _StreamingPCM16MonoResampler:
    """Stateful linear resampler for a continuous mono PCM16 stream.

    Network voice providers are free to split one continuous waveform across
    arbitrary packet boundaries. Resetting interpolation at every packet can
    create small discontinuities that sound like clicks or pops. This helper
    tracks interpolation in absolute source-sample coordinates, so splitting the
    same PCM stream into different packets produces the same device PCM bytes.
    """

    def __init__(self, source_rate_hz: int, target_rate_hz: int) -> None:
        if source_rate_hz <= 0 or target_rate_hz <= 0:
            raise ValueError("sample rates must be positive")
        self.source_rate_hz = source_rate_hz
        self.target_rate_hz = target_rate_hz
        self._step = source_rate_hz / target_rate_hz
        self._buffer = array("h")
        self._buffer_start_index = 0
        self._total_source_samples = 0
        self._next_output_position = 0.0
        self._last_source_sample: int | None = None

    def process(self, payload: bytes) -> bytes:
        if not payload:
            return b""
        incoming = _pcm16_samples(payload)
        if not incoming:
            return b""
        if not self._buffer:
            self._buffer_start_index = self._total_source_samples
        self._buffer.extend(incoming)
        self._total_source_samples += len(incoming)
        self._last_source_sample = incoming[-1]
        return self._drain_available()

    def _drain_available(self) -> bytes:
        if len(self._buffer) < 2:
            return b""
        result = array("h")
        last_index = self._buffer_start_index + len(self._buffer) - 1
        while self._next_output_position < last_index:
            left_index = int(self._next_output_position)
            right_index = left_index + 1
            left_offset = left_index - self._buffer_start_index
            right_offset = right_index - self._buffer_start_index
            if left_offset < 0 or right_offset >= len(self._buffer):
                break
            fraction = self._next_output_position - left_index
            sample = round(
                self._buffer[left_offset]
                + (self._buffer[right_offset] - self._buffer[left_offset]) * fraction
            )
            result.append(max(-32768, min(32767, sample)))
            self._next_output_position += self._step

        # Samples strictly before floor(next_output_position) can never be used
        # again. Keep the floor sample itself because it may be the left side of
        # the next interpolation when another network packet arrives.
        keep_from = int(self._next_output_position)
        drop = max(0, min(len(self._buffer), keep_from - self._buffer_start_index))
        if drop:
            del self._buffer[:drop]
            self._buffer_start_index += drop
        return _pcm16_bytes(result)

    def flush(self) -> bytes:
        """Finish the stream while preserving the same packet-independent phase."""
        if self._last_source_sample is None:
            return b""
        # Add one duplicate endpoint at the next absolute source index. This
        # supplies the right-hand interpolation sample that a continuing stream
        # would otherwise provide and makes finalization independent of how the
        # source bytes were packetized.
        if not self._buffer:
            self._buffer_start_index = self._total_source_samples
        self._buffer.append(self._last_source_sample)
        self._total_source_samples += 1
        result = self._drain_available()
        self._buffer = array("h")
        self._buffer_start_index = self._total_source_samples
        self._next_output_position = float(self._total_source_samples)
        self._last_source_sample = None
        return result


def _output_latency_seconds(stream) -> float:
    """Return the backend-reported output latency defensively."""
    try:
        value = getattr(stream, "latency", 0.0)
        if isinstance(value, (tuple, list)):
            value = value[-1] if value else 0.0
        return max(0.0, float(value or 0.0))
    except Exception:
        return 0.0


def _open_output_stream_low_latency_first(sd, **kwargs):
    """Prefer PortAudio's low-latency profile, with a safe fallback."""
    try:
        return sd.RawOutputStream(latency="low", **kwargs), True
    except Exception:
        return sd.RawOutputStream(**kwargs), False


def _host_api_names(sd) -> dict[int, str]:
    try:
        rows = sd.query_hostapis()
    except Exception:  # pragma: no cover - live backend variance
        return {}
    return {index: str(row.get("name", f"hostapi-{index}")) for index, row in enumerate(rows)}


def _default_device_index(sd, kind: str) -> int | None:
    try:
        defaults = sd.default.device
        value = defaults[0 if kind == "input" else 1]
        index = int(value)
        return index if index >= 0 else None
    except Exception:  # pragma: no cover - live backend variance
        return None


def _device_info_sync(sd, device_id: int | None, kind: str) -> AudioDeviceInfo:
    index = device_id if device_id is not None else _default_device_index(sd, kind)
    if index is None:
        raise RuntimeError(f"No default {kind} audio device is configured")
    row = sd.query_devices(index)
    host_api = _host_api_names(sd).get(int(row.get("hostapi", -1)))
    rate = row.get("default_samplerate")
    return AudioDeviceInfo(
        device_id=str(index),
        name=str(row.get("name", f"device-{index}")),
        max_input_channels=int(row.get("max_input_channels", 0)),
        max_output_channels=int(row.get("max_output_channels", 0)),
        default_sample_rate_hz=int(round(rate)) if rate else None,
        host_api=host_api,
    )


async def _devices() -> tuple[AudioDeviceInfo, ...]:
    sd = _sounddevice()
    rows = await asyncio.to_thread(sd.query_devices)
    host_apis = _host_api_names(sd)
    result: list[AudioDeviceInfo] = []
    for index, row in enumerate(rows):
        rate = row.get("default_samplerate")
        result.append(
            AudioDeviceInfo(
                device_id=str(index),
                name=str(row.get("name", f"device-{index}")),
                max_input_channels=int(row.get("max_input_channels", 0)),
                max_output_channels=int(row.get("max_output_channels", 0)),
                default_sample_rate_hz=int(round(rate)) if rate else None,
                host_api=host_apis.get(int(row.get("hostapi", -1))),
            )
        )
    return tuple(result)


class SoundDeviceAudioInput(AudioInput):
    def __init__(self, device_id: int | None = None) -> None:
        self.device_id = device_id

    async def devices(self) -> tuple[AudioDeviceInfo, ...]:
        return await _devices()

    async def selected_device(self) -> AudioDeviceInfo:
        sd = _sounddevice()
        return await asyncio.to_thread(_device_info_sync, sd, self.device_id, "input")

    async def capture_diagnostic(
        self,
        *,
        duration_s: float,
        audio_format: AudioFormat,
        frame_ms: int,
    ) -> AudioDiagnosticCapture:
        """Capture raw device PCM and the exact resampled frames Jarvis would consume."""

        if duration_s <= 0:
            raise ValueError("duration_s must be positive")
        sd = _sounddevice()
        info = await self.selected_device()
        if info.max_input_channels < 1:
            raise RuntimeError(f"Selected device [{info.device_id}] {info.name!r} has no input channels")
        if audio_format.channels != 1 or audio_format.sample_format is not AudioSampleFormat.PCM_S16LE:
            raise ValueError("diagnostic capture currently requires mono PCM_S16LE")
        native_rate = info.default_sample_rate_hz or audio_format.sample_rate_hz
        native_frames = int(round(native_rate * frame_ms / 1000))
        target_frames = int(round(audio_format.sample_rate_hz * frame_ms / 1000))
        block_count = max(1, math.ceil(duration_s * 1000 / frame_ms))

        check = getattr(sd, "check_input_settings", None)
        if callable(check):
            await asyncio.to_thread(
                check,
                device=int(info.device_id),
                channels=1,
                dtype="int16",
                samplerate=native_rate,
            )

        stream = sd.RawInputStream(
            samplerate=native_rate,
            channels=1,
            dtype="int16",
            blocksize=native_frames,
            device=int(info.device_id),
        )
        trace = CorrelationContext.create()
        raw_parts: list[bytes] = []
        processed: list[AudioFrame] = []
        stream.start()
        try:
            for sequence in range(block_count):
                data, _overflowed = await asyncio.to_thread(stream.read, native_frames)
                raw_payload = bytes(data)
                raw_parts.append(raw_payload)
                payload = raw_payload
                if native_rate != audio_format.sample_rate_hz or len(payload) != target_frames * 2:
                    payload = _resample_pcm16_mono(payload, target_frames)
                processed.append(
                    AudioFrame(
                        trace=trace,
                        sequence=sequence,
                        format=audio_format,
                        payload=payload,
                        captured_at_monotonic_ns=monotonic_ns(),
                    )
                )
        finally:
            await asyncio.to_thread(stream.stop)
            await asyncio.to_thread(stream.close)

        return AudioDiagnosticCapture(
            device=info,
            native_sample_rate_hz=native_rate,
            raw_native_pcm16=b"".join(raw_parts),
            processed_frames=tuple(processed),
        )

    async def stream(
        self,
        *,
        trace: CorrelationContext,
        audio_format: AudioFormat,
        frame_ms: int,
        cancellation_token: CancellationToken,
    ) -> AsyncIterator[AudioFrame]:
        sd = _sounddevice()
        if frame_ms <= 0:
            raise ValueError("frame_ms must be positive")
        if audio_format.channels != 1 or audio_format.sample_format is not AudioSampleFormat.PCM_S16LE:
            raise ValueError("SoundDevice Voice Lab input currently requires mono PCM_S16LE")

        info = await self.selected_device()
        if info.max_input_channels < 1:
            raise RuntimeError(f"Selected device [{info.device_id}] {info.name!r} has no input channels")
        native_rate = info.default_sample_rate_hz or audio_format.sample_rate_hz
        native_frames = int(round(native_rate * frame_ms / 1000))
        target_frames = int(round(audio_format.sample_rate_hz * frame_ms / 1000))
        if native_frames <= 0 or target_frames <= 0:
            raise ValueError("frame_ms produces an empty audio block")

        check = getattr(sd, "check_input_settings", None)
        if callable(check):
            await asyncio.to_thread(
                check,
                device=int(info.device_id),
                channels=1,
                dtype="int16",
                samplerate=native_rate,
            )

        stream = sd.RawInputStream(
            samplerate=native_rate,
            channels=1,
            dtype="int16",
            blocksize=native_frames,
            device=int(info.device_id),
        )
        sequence = 0
        stream.start()
        try:
            while not cancellation_token.is_cancelled:
                data, overflowed = await asyncio.to_thread(stream.read, native_frames)
                if overflowed:
                    # Preserve received bytes; telemetry can surface overflow later.
                    pass
                payload = bytes(data)
                if native_rate != audio_format.sample_rate_hz or len(payload) != target_frames * 2:
                    payload = _resample_pcm16_mono(payload, target_frames)
                yield AudioFrame(
                    trace=trace,
                    sequence=sequence,
                    format=audio_format,
                    payload=payload,
                    captured_at_monotonic_ns=monotonic_ns(),
                )
                sequence += 1
        finally:
            await asyncio.to_thread(stream.stop)
            await asyncio.to_thread(stream.close)


class SoundDeviceAudioOutput(AudioOutput):
    def __init__(self, device_id: int | None = None) -> None:
        self.device_id = device_id
        self._stream = None
        self._lock = asyncio.Lock()

    async def devices(self) -> tuple[AudioDeviceInfo, ...]:
        return await _devices()

    async def selected_device(self) -> AudioDeviceInfo:
        sd = _sounddevice()
        return await asyncio.to_thread(_device_info_sync, sd, self.device_id, "output")

    async def play(
        self,
        audio: AsyncIterator[AudioFrame],
        cancellation_token: CancellationToken,
    ) -> AudioPlaybackResult:
        sd = _sounddevice()
        # PlaybackLedger is expressed in provider/source bytes.  Device-rate
        # resampling may change the number of bytes physically written, so keep
        # source consumption separate from the output buffer size.
        source_bytes_consumed = 0
        source_duration_ms_written = 0.0
        first_write_ns = None
        first_write_completed_ns = None
        estimated_first_audible_ns = None
        output_latency_ms = None
        low_latency_active = False
        output_info = await self.selected_device()
        target_rate = output_info.default_sample_rate_hz
        async with self._lock:
            stream = None
            stream_resampler: _StreamingPCM16MonoResampler | None = None
            stream_resampler_key: tuple[int, int] | None = None
            try:
                async for frame in audio:
                    if cancellation_token.is_cancelled:
                        break
                    play_payload = frame.payload
                    play_format = frame.format
                    if (
                        target_rate
                        and frame.format.sample_format is AudioSampleFormat.PCM_S16LE
                        and frame.format.channels == 1
                        and frame.format.sample_rate_hz != target_rate
                    ):
                        key = (frame.format.sample_rate_hz, target_rate)
                        if stream_resampler is None or stream_resampler_key != key:
                            stream_resampler = _StreamingPCM16MonoResampler(*key)
                            stream_resampler_key = key
                        play_payload = stream_resampler.process(frame.payload)
                        play_format = AudioFormat(target_rate, 1, AudioSampleFormat.PCM_S16LE)
                    else:
                        stream_resampler = None
                        stream_resampler_key = None
                        if target_rate:
                            play_payload, play_format = _resample_output_frame_to_rate(frame, target_rate)

                    source_bytes_consumed += len(frame.payload)
                    source_duration_ms_written += frame.duration_ms
                    if not play_payload:
                        continue
                    if stream is None:
                        stream, low_latency_active = _open_output_stream_low_latency_first(
                            sd,
                            samplerate=play_format.sample_rate_hz,
                            channels=play_format.channels,
                            dtype=_dtype(play_format),
                            device=self.device_id,
                        )
                        stream.start()
                        self._stream = stream
                        output_latency_ms = _output_latency_seconds(stream) * 1000.0
                    if first_write_ns is None:
                        first_write_ns = monotonic_ns()
                        estimated_first_audible_ns = first_write_ns + int(
                            (output_latency_ms or 0.0) * 1_000_000
                        )
                    await asyncio.to_thread(stream.write, play_payload)
                    if first_write_completed_ns is None:
                        first_write_completed_ns = monotonic_ns()

                # Flush only on a natural stream ending. On cancellation/barge-in,
                # stale tail audio must not be forced through the speaker.
                if (
                    stream is not None
                    and stream_resampler is not None
                    and not cancellation_token.is_cancelled
                ):
                    tail = stream_resampler.flush()
                    if tail:
                        await asyncio.to_thread(stream.write, tail)
            finally:
                if stream is not None:
                    await asyncio.to_thread(stream.stop)
                    await asyncio.to_thread(stream.close)
                self._stream = None
        return AudioPlaybackResult(
            source_bytes_consumed,
            first_write_monotonic_ns=first_write_ns,
            first_write_completed_monotonic_ns=first_write_completed_ns,
            estimated_first_audible_monotonic_ns=estimated_first_audible_ns,
            output_latency_ms=output_latency_ms,
            low_latency_requested=True,
            low_latency_active=low_latency_active,
            source_duration_ms_written=source_duration_ms_written,
        )

    async def stop(self) -> None:
        stream = self._stream
        if stream is not None:
            await asyncio.to_thread(stream.abort)
