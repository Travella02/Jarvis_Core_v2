"""Streaming Silero VAD adapter backed by whisper.cpp's native VAD API.

0.0.5 Repair5 restores the separation that made V1 turn-taking stable:
"someone is speaking" is decided by an independent speech-presence detector;
Whisper is responsible only for "what did they say?".

The implementation deliberately reuses the already-built whisper.cpp runtime.
No Torch/ONNX Python dependency is added. Silero v6.2.0 is a tiny GGML model and
whisper.cpp exposes a dedicated streaming VAD C API for it.
"""

from __future__ import annotations

import ctypes
import os
import sys
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Protocol

from core.voice.contracts import AudioFrame, AudioSampleFormat
from core.voice.vad import VoiceActivityDetector


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME = PROJECT_ROOT / ".runtime" / "voice" / "whisper_cpp"
DEFAULT_VAD_MODEL = DEFAULT_RUNTIME / "models" / "ggml-silero-v6.2.0.bin"


def _default_library_path() -> Path:
    bin_dir = DEFAULT_RUNTIME / "bin"
    if os.name == "nt":
        return bin_dir / "whisper.dll"
    if sys.platform == "darwin":
        return bin_dir / "libwhisper.dylib"
    return bin_dir / "libwhisper.so"


def _unique_existing_directories(paths: Iterable[Path]) -> tuple[Path, ...]:
    """Return existing directories once, preserving discovery order."""
    result: list[Path] = []
    seen: set[str] = set()
    for raw in paths:
        try:
            path = raw.expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        if not path.is_dir():
            continue
        key = os.path.normcase(str(path))
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return tuple(result)


def _windows_dependency_directories(
    library_path: Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> tuple[Path, ...]:
    """Discover controlled Windows DLL search directories for whisper.cpp.

    Python 3.8+ intentionally uses a restricted dependency search for ctypes.
    Jarvis's CUDA whisper.cpp build can therefore run fine as whisper-server.exe
    while ctypes cannot resolve whisper.dll's CUDA dependencies inside Python.
    We explicitly add only known runtime locations instead of blindly adding the
    process PATH.
    """
    env = dict(os.environ if environ is None else environ)
    candidates: list[Path] = [library_path.parent]

    cuda_roots: list[Path] = []
    for key, value in env.items():
        upper = key.upper()
        if (upper == "CUDA_PATH" or upper.startswith("CUDA_PATH_V")) and value:
            cuda_roots.append(Path(value))

    program_files = env.get("ProgramFiles")
    if program_files:
        cuda_parent = Path(program_files) / "NVIDIA GPU Computing Toolkit" / "CUDA"
        if cuda_parent.is_dir():
            try:
                cuda_roots.extend(
                    child for child in cuda_parent.iterdir()
                    if child.is_dir() and child.name.lower().startswith("v")
                )
            except OSError:
                pass

    for root in cuda_roots:
        candidates.append(root / "bin")

    # Some development environments expose native redistributables here.
    conda_prefix = env.get("CONDA_PREFIX")
    if conda_prefix:
        candidates.append(Path(conda_prefix) / "Library" / "bin")

    return _unique_existing_directories(candidates)


def _load_windows_whisper_library(
    library_path: Path,
) -> tuple[ctypes.CDLL, list[object]]:
    """Load whisper.dll with explicit dependency directories.

    The primary path keeps Python's secure LoadLibraryEx behavior. If Windows
    still cannot resolve a transitive dependency, a full-path winmode=0 retry is
    used as a development compatibility fallback. The root DLL path remains
    absolute and controlled by Jarvis.
    """
    handles: list[object] = []
    search_dirs = _windows_dependency_directories(library_path)

    if hasattr(os, "add_dll_directory"):
        for directory in search_dirs:
            try:
                handles.append(os.add_dll_directory(str(directory)))
            except OSError:
                continue

    try:
        return ctypes.CDLL(str(library_path)), handles
    except OSError as secure_error:
        try:
            # Python 3.8+ changed ctypes' default DLL dependency search. A full
            # path with winmode=0 restores the legacy Windows dependency search
            # as a fallback, which includes configured CUDA runtime locations.
            return ctypes.CDLL(str(library_path), winmode=0), handles
        except OSError as fallback_error:
            sibling_dlls = sorted(path.name for path in library_path.parent.glob("*.dll"))
            search_text = ", ".join(str(path) for path in search_dirs) or "<none>"
            sibling_text = ", ".join(sibling_dlls) or "<none>"
            raise OSError(
                "whisper.cpp native DLL exists but Windows could not resolve one "
                "of its dependent DLLs. "
                f"library={library_path}; dependency_search=[{search_text}]; "
                f"sibling_dlls=[{sibling_text}]; "
                f"secure_load_error={secure_error}; fallback_load_error={fallback_error}. "
                "If this is a CUDA build, make sure the CUDA Toolkit used to build "
                "whisper.cpp is still installed. You can also rerun "
                "scripts/setup_whisper_cpp.ps1 -Backend cuda."
            ) from fallback_error


@dataclass(frozen=True, slots=True)
class SileroVadConfig:
    library_path: Path = _default_library_path()
    model_path: Path = DEFAULT_VAD_MODEL
    threshold: float = 0.50
    threads: int = 2
    gpu_device: int = 0
    # Silero v6.2.0's native window at 16 kHz is 512 samples / 32 ms.
    window_samples: int = 512

    def __post_init__(self) -> None:
        if not 0.0 < self.threshold < 1.0:
            raise ValueError("Silero VAD threshold must be between 0 and 1")
        if self.threads <= 0:
            raise ValueError("Silero VAD threads must be positive")
        if self.window_samples <= 0:
            raise ValueError("Silero VAD window_samples must be positive")


class _ProbabilitySource(Protocol):
    def probability(self, samples: tuple[float, ...]) -> float:
        ...

    def reset(self) -> None:
        ...

    def close(self) -> None:
        ...


class _VadContextParams(ctypes.Structure):
    _fields_ = [
        ("n_threads", ctypes.c_int),
        ("use_gpu", ctypes.c_bool),
        ("gpu_device", ctypes.c_int),
    ]


class _NativeWhisperVad:
    """Minimal ctypes binding to the public whisper.cpp VAD-only API."""

    _LOG_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p)

    def __init__(self, config: SileroVadConfig) -> None:
        if not config.library_path.is_file():
            raise FileNotFoundError(
                f"whisper.cpp native library not found: {config.library_path}. "
                "Run scripts/setup_whisper_cpp.ps1 first."
            )
        if not config.model_path.is_file():
            raise FileNotFoundError(
                f"Silero VAD model not found: {config.model_path}. "
                "Run: powershell -ExecutionPolicy Bypass -File .\\scripts\\setup_whisper_vad.ps1"
            )

        self._dll_directories: list[object] = []
        if os.name == "nt":
            self._lib, self._dll_directories = _load_windows_whisper_library(
                config.library_path
            )
        else:
            self._lib = ctypes.CDLL(str(config.library_path))
        self._configure_api()
        # whisper.cpp logs VAD inference at INFO for every streaming call. Silence
        # that native chatter in the application process; whisper-server runs in
        # its own process and is unaffected. Keep the callback alive for the DLL.
        self._log_callback = self._LOG_CALLBACK(lambda _level, _text, _user: None)
        self._lib.whisper_log_set(self._log_callback, None)

        params = self._lib.whisper_vad_default_context_params()
        params.n_threads = config.threads
        # whisper.cpp currently executes this tiny VAD on CPU even when the field
        # is true; keep it false to avoid unnecessary backend assumptions.
        params.use_gpu = False
        params.gpu_device = config.gpu_device
        model_bytes = os.fsencode(str(config.model_path))
        self._ctx = self._lib.whisper_vad_init_from_file_with_params(model_bytes, params)
        if not self._ctx:
            raise RuntimeError(f"failed to initialize Silero VAD model: {config.model_path}")

    def _configure_api(self) -> None:
        lib = self._lib
        lib.whisper_vad_default_context_params.restype = _VadContextParams
        lib.whisper_vad_init_from_file_with_params.argtypes = [
            ctypes.c_char_p,
            _VadContextParams,
        ]
        lib.whisper_vad_init_from_file_with_params.restype = ctypes.c_void_p
        lib.whisper_vad_detect_speech_no_reset.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_int,
        ]
        lib.whisper_vad_detect_speech_no_reset.restype = ctypes.c_bool
        lib.whisper_vad_reset_state.argtypes = [ctypes.c_void_p]
        lib.whisper_vad_reset_state.restype = None
        lib.whisper_vad_n_probs.argtypes = [ctypes.c_void_p]
        lib.whisper_vad_n_probs.restype = ctypes.c_int
        lib.whisper_vad_probs.argtypes = [ctypes.c_void_p]
        lib.whisper_vad_probs.restype = ctypes.POINTER(ctypes.c_float)
        lib.whisper_vad_free.argtypes = [ctypes.c_void_p]
        lib.whisper_vad_free.restype = None
        lib.whisper_log_set.argtypes = [self._LOG_CALLBACK, ctypes.c_void_p]
        lib.whisper_log_set.restype = None

    def probability(self, samples: tuple[float, ...]) -> float:
        if not samples:
            return 0.0
        payload = (ctypes.c_float * len(samples))(*samples)
        ok = self._lib.whisper_vad_detect_speech_no_reset(
            self._ctx,
            payload,
            len(samples),
        )
        if not ok:
            raise RuntimeError("whisper.cpp Silero VAD inference failed")
        count = self._lib.whisper_vad_n_probs(self._ctx)
        if count <= 0:
            return 0.0
        probs = self._lib.whisper_vad_probs(self._ctx)
        if not probs:
            return 0.0
        return float(probs[count - 1])

    def reset(self) -> None:
        if self._ctx:
            self._lib.whisper_vad_reset_state(self._ctx)

    def close(self) -> None:
        if getattr(self, "_ctx", None):
            self._lib.whisper_vad_free(self._ctx)
            self._ctx = None
        directories = getattr(self, "_dll_directories", None)
        if directories:
            for directory in reversed(directories):
                try:
                    directory.close()
                except Exception:
                    pass
            self._dll_directories = []


class WhisperCppSileroVadDetector(VoiceActivityDetector):
    """Streaming neural speech-presence authority for 16 kHz mono PCM16.

    `is_speech()` returns a neural speech decision, never an RMS/loudness
    decision. The audio buffering only adapts Jarvis's 30 ms capture frames to
    Silero's 512-sample streaming window.
    """

    def __init__(
        self,
        config: SileroVadConfig | None = None,
        *,
        source: _ProbabilitySource | None = None,
    ) -> None:
        self.config = config or SileroVadConfig()
        self._source = source or _NativeWhisperVad(self.config)
        self._pcm = bytearray()
        self.last_probability = 0.0
        self.last_evaluated = False
        self._closed = False

    @property
    def description(self) -> str:
        return (
            "silero-v6.2.0 via whisper.cpp "
            f"(threshold={self.config.threshold:.2f}, candidate=neural-speech-presence)"
        )

    def reset(self) -> None:
        self._pcm.clear()
        self.last_probability = 0.0
        self.last_evaluated = False
        self._source.reset()

    def is_speech(self, frame: AudioFrame) -> bool:
        if self._closed:
            raise RuntimeError("Silero VAD detector is closed")
        fmt = frame.format
        if fmt.sample_format is not AudioSampleFormat.PCM_S16LE:
            raise ValueError("Silero VAD requires PCM_S16LE")
        if fmt.channels != 1:
            raise ValueError("Silero VAD requires mono audio")
        if fmt.sample_rate_hz != 16_000:
            raise ValueError("Silero VAD requires 16 kHz audio")

        self._pcm.extend(frame.payload)
        window_bytes = self.config.window_samples * 2
        decision = False
        evaluated = False
        self.last_evaluated = False
        while len(self._pcm) >= window_bytes:
            raw = bytes(self._pcm[:window_bytes])
            del self._pcm[:window_bytes]
            values = array("h")
            values.frombytes(raw)
            if sys.byteorder != "little":
                values.byteswap()
            samples = tuple(float(value) / 32768.0 for value in values)
            self.last_probability = self._source.probability(samples)
            evaluated = True
            if self.last_probability >= self.config.threshold:
                decision = True

        self.last_evaluated = evaluated
        # If this 30 ms frame did not complete Silero's 32 ms window, do not
        # invent a decision. The next frame supplies the missing samples.
        return bool(evaluated and decision)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._source.close()

    def __del__(self) -> None:  # pragma: no cover - best-effort interpreter cleanup
        try:
            self.close()
        except Exception:
            pass
