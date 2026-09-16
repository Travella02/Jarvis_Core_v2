import tempfile
import unittest
from pathlib import Path

from providers.intelligence.openai.config import (
    DEFAULT_MODEL,
    OpenAIProviderConfig,
    load_env_file,
)


class OpenAIConfigTests(unittest.TestCase):
    def test_defaults_to_luna_and_safe_limits(self) -> None:
        config = OpenAIProviderConfig.from_env({"OPENAI_API_KEY": "test-key"})
        self.assertEqual(config.model, DEFAULT_MODEL)
        self.assertEqual(config.model, "gpt-5.6-luna")
        self.assertEqual(config.reasoning_effort, "medium")
        self.assertEqual(config.max_output_tokens, 4096)
        self.assertFalse(config.store_responses)

    def test_environment_overrides_provider_owned_values(self) -> None:
        config = OpenAIProviderConfig.from_env(
            {
                "OPENAI_API_KEY": "test-key",
                "JARVIS_OPENAI_MODEL": "future-model",
                "JARVIS_OPENAI_REASONING_EFFORT": "high",
                "JARVIS_OPENAI_MAX_OUTPUT_TOKENS": "2048",
                "JARVIS_OPENAI_TIMEOUT_SECONDS": "12.5",
                "OPENAI_BASE_URL": "https://example.invalid/v1",
            }
        )
        self.assertEqual(config.model, "future-model")
        self.assertEqual(config.reasoning_effort, "high")
        self.assertEqual(config.max_output_tokens, 2048)
        self.assertEqual(config.timeout_seconds, 12.5)
        self.assertEqual(config.base_url, "https://example.invalid/v1")

    def test_env_file_parser_is_non_executing_and_handles_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(
                "# comment\nOPENAI_API_KEY='abc123'\nJARVIS_OPENAI_MODEL=\"gpt-5.6-luna\"\n",
                encoding="utf-8",
            )
            values = load_env_file(path)
        self.assertEqual(values["OPENAI_API_KEY"], "abc123")
        self.assertEqual(values["JARVIS_OPENAI_MODEL"], "gpt-5.6-luna")

    def test_invalid_reasoning_effort_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OpenAIProviderConfig.from_env(
                {
                    "OPENAI_API_KEY": "test-key",
                    "JARVIS_OPENAI_REASONING_EFFORT": "turbo-magic",
                }
            )


if __name__ == "__main__":
    unittest.main()
