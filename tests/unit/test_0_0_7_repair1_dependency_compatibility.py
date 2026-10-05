import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class Repair1DependencyCompatibilityTests(unittest.TestCase):
    def test_realtime_sdk_and_runtime_websocket_pin_are_compatible(self) -> None:
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        self.assertIn("openai[realtime]==3.13.0", requirements)
        self.assertIn("websockets==15.0.1", requirements)
        self.assertNotIn("websockets==16.0", requirements)

    def test_pyproject_matches_requirements_websocket_pin(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"openai[realtime]==3.13.0"', pyproject)
        self.assertIn('"websockets==15.0.1"', pyproject)
        self.assertNotIn('"websockets==16.0"', pyproject)


if __name__ == "__main__":
    unittest.main()
