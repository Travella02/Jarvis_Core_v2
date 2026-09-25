import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "core"


class VoiceProviderIndependenceTests(unittest.TestCase):
    def test_core_never_imports_concrete_voice_providers_or_audio_sdks(self):
        banned = ("whisper", "chatterbox", "qwen", "sounddevice", "webrtcvad")
        offenders = []
        for path in CORE.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module)
                for name in names:
                    if any(token in name.lower() for token in banned):
                        offenders.append(f"{path.relative_to(ROOT)} -> {name}")
        self.assertEqual(offenders, [])

    def test_provider_runtime_assets_are_git_ignored(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".runtime/", gitignore)
