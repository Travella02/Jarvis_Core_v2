import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPENAI_PROVIDER_ROOT = ROOT / "providers" / "intelligence" / "openai"


class ProviderIndependenceTests(unittest.TestCase):
    def test_core_does_not_import_openai_sdk(self) -> None:
        import_pattern = re.compile(r"^\s*(?:from\s+openai\b|import\s+openai\b)", re.MULTILINE)
        offenders = []
        for path in (ROOT / "core").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if import_pattern.search(text):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_only_openai_provider_package_may_import_openai_sdk(self) -> None:
        import_pattern = re.compile(r"^\s*(?:from\s+openai\b|import\s+openai\b)", re.MULTILINE)
        offenders = []
        for base in ("apps", "backend", "core", "integrations", "providers"):
            for path in (ROOT / base).rglob("*.py"):
                if OPENAI_PROVIDER_ROOT in path.parents or path.parent == OPENAI_PROVIDER_ROOT:
                    continue
                if import_pattern.search(path.read_text(encoding="utf-8")):
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_v2_runtime_does_not_import_v1_reference(self) -> None:
        offenders = []
        for base in ("core", "providers", "integrations", "backend", "apps"):
            for path in (ROOT / base).rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                if "Reference_jarvis_corev1" in text or "Jarvis_Real_Time" in text:
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
