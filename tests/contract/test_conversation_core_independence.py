import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ConversationCoreIndependenceTests(unittest.TestCase):
    def test_conversation_core_has_no_provider_specific_imports(self) -> None:
        provider_pattern = re.compile(
            r"^\s*(?:from|import)\s+(?:openai|providers\.intelligence\.openai)\b",
            re.MULTILINE,
        )
        offenders = []
        for path in (ROOT / "core" / "conversation").rglob("*.py"):
            if provider_pattern.search(path.read_text(encoding="utf-8")):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_conversation_core_has_no_tool_executor_or_os_action_imports(self) -> None:
        blocked = ("subprocess", "os.system", "pyautogui", "selenium", "playwright")
        offenders = []
        for path in (ROOT / "core" / "conversation").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if any(token in text for token in blocked):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
