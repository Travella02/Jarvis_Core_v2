import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class FoundationStructureTests(unittest.TestCase):
    def test_python_runtime_is_supported(self) -> None:
        self.assertGreaterEqual(sys.version_info, (3, 11))
        self.assertLess(sys.version_info, (4, 0))

    def test_required_foundation_paths_exist(self) -> None:
        required = [
            "apps/desktop",
            "core/conversation",
            "core/state",
            "core/intelligence",
            "core/voice",
            "core/memory",
            "core/permissions",
            "core/tasks",
            "core/tools",
            "providers/intelligence/openai",
            "providers/intelligence/local",
            "providers/stt",
            "providers/tts",
            "integrations/gmail",
            "integrations/calendar",
            "integrations/browser",
            "integrations/computer",
            "backend",
            "prompts",
            "tests/unit",
            "tests/contract",
            "tests/behavioral",
            "tests/security",
            "tests/integration",
            "tests/performance",
            "issues",
            "scripts",
            "docs",
            "VERSION",
            "README.md",
            "pyproject.toml",
            ".env.example",
            ".gitignore",
        ]
        missing = [item for item in required if not (ROOT / item).exists()]
        self.assertEqual(missing, [])

    def test_release_manifest_matches_candidate(self) -> None:
        manifest = json.loads((ROOT / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.0.1")
        self.assertEqual(manifest["title"], "Foundation")
        self.assertEqual(manifest["status"], "live_acceptance_candidate")
        self.assertIsNone(manifest["required_previous_version"])


if __name__ == "__main__":
    unittest.main()
