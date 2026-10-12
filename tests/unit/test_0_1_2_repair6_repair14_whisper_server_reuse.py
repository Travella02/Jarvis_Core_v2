"""Regression: never launch a second whisper-server onto an occupied wake port."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from providers.stt.whisper_cpp.config import WhisperCppConfig
from providers.stt.whisper_cpp.provider import WhisperCppProvider


class WhisperReuseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        exe = Path(self.temp.name) / "whisper-server.exe"
        model = Path(self.temp.name) / "model.bin"
        exe.write_bytes(b"test-executable")
        model.write_bytes(b"test-model")
        self.provider = WhisperCppProvider(WhisperCppConfig(server_executable=exe, model_path=model))

    async def test_attach_to_existing_healthy_server_without_spawning(self) -> None:
        with patch.object(self.provider, "_probe_server", return_value=True) as probe, patch(
            "providers.stt.whisper_cpp.provider.subprocess.Popen", side_effect=AssertionError("duplicate server spawn")
        ):
            health = await self.provider.health()
            self.assertTrue(health.ready)
            self.assertIsNone(self.provider._process)
            await self.provider._ensure_server()
            self.assertGreaterEqual(probe.call_count, 2)
            await self.provider.close()  # cannot terminate a server it doesn't own

    async def test_unoccupied_port_still_starts_managed_server(self) -> None:
        child = Mock()
        child.poll.return_value = None
        with patch.object(self.provider, "_probe_server", side_effect=[False, False, True]), patch(
            "providers.stt.whisper_cpp.provider.subprocess.Popen", return_value=child
        ) as launch:
            await self.provider._ensure_server()
            launch.assert_called_once()
            self.assertIs(self.provider._process, child)

    async def test_live_child_waits_for_readiness_without_second_spawn(self) -> None:
        child = Mock()
        child.poll.return_value = None
        self.provider._process = child
        with patch.object(self.provider, "_probe_server", side_effect=[False, False, True]), patch(
            "providers.stt.whisper_cpp.provider.subprocess.Popen", side_effect=AssertionError("duplicate launch")
        ):
            await self.provider._ensure_server()
        self.assertIs(self.provider._process, child)

    async def test_warmup_reuses_existing_service(self) -> None:
        with patch.object(self.provider, "_probe_server", return_value=True), patch.object(
            self.provider, "_transcribe", new_callable=AsyncMock
        ) as transcribe, patch(
            "providers.stt.whisper_cpp.provider.subprocess.Popen", side_effect=AssertionError("duplicate server spawn")
        ):
            await self.provider.warmup()
            transcribe.assert_awaited_once()
            self.assertIsNone(self.provider._process)


if __name__ == "__main__":
    unittest.main()
