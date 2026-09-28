import inspect
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from apps.voice_lab import (
    _whisper_config_from_args,
    build_engine,
    doctor,
    provider_health,
)
from providers.stt.whisper_cpp import WhisperCppConfig


class Repair34aWhisperFlagWiringTests(unittest.TestCase):
    def _base(self):
        return WhisperCppConfig(
            server_executable=Path(__file__),
            model_path=Path(__file__),
            emit_partials=True,
        )

    def test_final_only_flag_disables_partials_in_selected_config(self):
        with patch(
            "apps.voice_lab.WhisperCppConfig.from_env",
            return_value=self._base(),
        ):
            config = _whisper_config_from_args(
                Namespace(stt_endpoint_final_only=True)
            )
        self.assertFalse(config.emit_partials)

    def test_default_preserves_repair34_control_behavior(self):
        with patch(
            "apps.voice_lab.WhisperCppConfig.from_env",
            return_value=self._base(),
        ):
            config = _whisper_config_from_args(
                Namespace(stt_endpoint_final_only=False)
            )
        self.assertTrue(config.emit_partials)

    def test_live_build_engine_uses_selected_whisper_config(self):
        source = inspect.getsource(build_engine)
        self.assertIn(
            "WhisperCppProvider(_whisper_config_from_args(args))",
            source,
        )

    def test_provider_health_uses_same_selected_whisper_config(self):
        source = inspect.getsource(provider_health)
        self.assertIn(
            "WhisperCppProvider(_whisper_config_from_args(args))",
            source,
        )

    def test_doctor_no_longer_references_missing_args(self):
        source = inspect.getsource(doctor)
        self.assertIn(
            "WhisperCppProvider(_whisper_config_from_args())",
            source,
        )
        self.assertNotIn("args.stt_endpoint_final_only", source)


if __name__ == "__main__":
    unittest.main()
