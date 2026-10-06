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
            "core/runtime",
            "core/state",
            "core/intelligence",
            "core/voice",
            "core/memory",
            "core/permissions",
            "core/tasks",
            "core/tools",
            "providers/intelligence/openai",
            "providers/intelligence/local",
            "providers/voice_frontend",
            "providers/voice_frontend/openai_live",
            "providers/voice_frontend/openai_realtime",
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
            "requirements.txt",
        ]
        missing = [item for item in required if not (ROOT / item).exists()]
        self.assertEqual(missing, [])

    def test_release_manifest_matches_candidate(self) -> None:
        manifest = json.loads((ROOT / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.0.9")
        self.assertEqual(manifest["title"], "Swappable Realtime Voice Frontend + Core Delegation")
        self.assertEqual(manifest["status"], "live_acceptance_candidate")
        self.assertEqual(manifest["required_previous_version"], "0.0.8")
        self.assertNotIn("repair", manifest)

    def test_openai_sdk_dependency_is_pinned_for_candidate(self) -> None:
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        self.assertIn("openai[realtime]==3.13.0", requirements)
        self.assertIn("sounddevice==0.5.6", requirements)
        self.assertIn("webrtcvad-wheels==2.0.14", requirements)
        self.assertIn("fastapi==0.128.2", requirements)
        self.assertIn("uvicorn[standard]==0.48.0", requirements)
        self.assertIn("httpx==0.28.1", requirements)
        self.assertIn("websockets==15.0.1", requirements)
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"openai[realtime]==3.13.0"', pyproject)
        self.assertIn('"fastapi==0.128.2"', pyproject)


if __name__ == "__main__":
    unittest.main()
