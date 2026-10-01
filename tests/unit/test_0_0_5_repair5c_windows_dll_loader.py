
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.vad import silero_whisper_cpp as native


class FakeDirectoryHandle:
    def __init__(self, path):
        self.path = path
        self.closed = False

    def close(self):
        self.closed = True


class Repair5cWindowsDllLoaderTests(unittest.TestCase):
    def test_dependency_discovery_includes_whisper_bin_and_cuda_bin(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            whisper_bin = root / "runtime" / "bin"
            cuda_root = root / "cuda" / "v12.8"
            whisper_bin.mkdir(parents=True)
            (cuda_root / "bin").mkdir(parents=True)
            library = whisper_bin / "whisper.dll"
            library.write_bytes(b"x")

            dirs = native._windows_dependency_directories(
                library,
                environ={"CUDA_PATH": str(cuda_root)},
            )

            self.assertIn(whisper_bin.resolve(), dirs)
            self.assertIn((cuda_root / "bin").resolve(), dirs)

    def test_dependency_discovery_deduplicates_cuda_aliases(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            whisper_bin = root / "bin"
            cuda_root = root / "cuda"
            whisper_bin.mkdir(parents=True)
            (cuda_root / "bin").mkdir(parents=True)
            library = whisper_bin / "whisper.dll"
            library.write_bytes(b"x")

            dirs = native._windows_dependency_directories(
                library,
                environ={
                    "CUDA_PATH": str(cuda_root),
                    "CUDA_PATH_V12_8": str(cuda_root),
                },
            )

            self.assertEqual(dirs.count((cuda_root / "bin").resolve()), 1)

    def test_windows_loader_retries_with_winmode_zero(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            whisper_bin = root / "bin"
            whisper_bin.mkdir(parents=True)
            library = whisper_bin / "whisper.dll"
            library.write_bytes(b"x")
            handle = FakeDirectoryHandle(whisper_bin)
            fake_lib = object()

            # Isolate loader fallback behavior from the host machine's real
            # CUDA installation. Dependency discovery is tested separately
            # above; this test should always exercise exactly one controlled
            # search directory regardless of CUDA_PATH/Program Files on the
            # developer machine.
            with patch.object(
                native,
                "_windows_dependency_directories",
                return_value=(whisper_bin.resolve(),),
            ), patch.object(
                native.os,
                "add_dll_directory",
                return_value=handle,
                create=True,
            ), patch.object(
                native.ctypes,
                "CDLL",
                side_effect=[OSError("secure fail"), fake_lib],
            ) as cdll:
                loaded, handles = native._load_windows_whisper_library(library)

            self.assertIs(loaded, fake_lib)
            self.assertEqual(handles, [handle])
            self.assertEqual(cdll.call_count, 2)
            self.assertEqual(cdll.call_args_list[0].kwargs, {})
            self.assertEqual(cdll.call_args_list[1].kwargs, {"winmode": 0})

    def test_native_source_closes_all_added_search_directories(self):
        text = (Path(__file__).resolve().parents[2] / "providers/vad/silero_whisper_cpp.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("reversed(directories)", text)
        self.assertIn("directory.close()", text)


if __name__ == "__main__":
    unittest.main()
