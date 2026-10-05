import tempfile
import unittest
from pathlib import Path

from core.runtime import RuntimeSettings, RuntimeSettingsError


class RuntimeSettingsTests(unittest.TestCase):
    def test_explicit_environment_is_deterministic_and_overrides_file(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            env_file = Path(root) / ".env"
            env_file.write_text(
                "JARVIS_RUNTIME_EVENT_HISTORY=777\n"
                "JARVIS_DEFAULT_INTELLIGENCE_ROUTE=file-route\n",
                encoding="utf-8",
            )
            settings = RuntimeSettings.from_env(
                {
                    "JARVIS_RUNTIME_EVENT_HISTORY": "888",
                    "JARVIS_DEFAULT_INTELLIGENCE_ROUTE": "test-route",
                },
                env_file=env_file,
            )
        self.assertEqual(settings.event_history_limit, 888)
        self.assertEqual(settings.default_intelligence_route, "test-route")

    def test_explicit_mapping_does_not_implicitly_read_project_env(self) -> None:
        settings = RuntimeSettings.from_env({})
        self.assertEqual(settings.event_history_limit, 1024)
        self.assertEqual(settings.default_intelligence_route, "primary")

    def test_public_settings_contain_no_provider_credentials(self) -> None:
        settings = RuntimeSettings.from_env(
            {
                "OPENAI_API_KEY": "super-secret",
                "JARVIS_DEFAULT_INTELLIGENCE_ROUTE": "primary",
            }
        )
        public = dict(settings.public_dict())
        self.assertNotIn("OPENAI_API_KEY", public)
        self.assertNotIn("super-secret", repr(public))

    def test_invalid_history_limit_is_rejected(self) -> None:
        with self.assertRaises(RuntimeSettingsError):
            RuntimeSettings.from_env({"JARVIS_RUNTIME_EVENT_HISTORY": "1"})


if __name__ == "__main__":
    unittest.main()
