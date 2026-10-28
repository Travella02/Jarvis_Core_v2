"""0.1.5.9 Repair2: the extension must advertise the snapshot it implements.

Core requires both snapshot and guarded navigation to select a YouTube result.
This contract catches a worker that implements snapshot but leaves it out of its
hello capability list, which previously caused result_bridge_outdated failures.
"""
import re
import unittest
from pathlib import Path

from core.tools.browser_bridge import _BRIDGE_ALLOWED
from core.tools.default_browser_bridge import DefaultBrowserBridgeAdapter


ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "extensions" / "jarvis_browser_bridge" / "service_worker.js"


class SnapshotCapabilityTests(unittest.TestCase):
    def test_worker_advertises_implemented_snapshot(self):
        code = WORKER.read_text(encoding="utf-8")
        match = re.search(r"const BRIDGE_CAPABILITIES\s*=\s*Object\.freeze\(\[([\s\S]*?)\]\);", code)
        self.assertIsNotNone(match, "Couldn't find declared extension capabilities")
        advertised = re.findall(r'"([a-z_]+)"', match.group(1))
        self.assertEqual(len(advertised), len(set(advertised)), "Duplicate bridge capabilities")
        self.assertIn("snapshot", advertised)
        self.assertIn("navigate_target_guarded", advertised)
        self.assertIn("tabs_list", advertised)
        self.assertRegex(code, r'if \(operation === "snapshot"\) return await snapshotCommand\(\)\;')
        self.assertIn('capabilities: BRIDGE_CAPABILITIES,', code)
        self.assertIn("snapshot", _BRIDGE_ALLOWED)


class SnapshotSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_snapshot_advertisement_blocks_before_browser_commands(self):
        from tests.unit.test_0_1_5_9_browser_result_selection import FakeBrowserBridge
        bridge = FakeBrowserBridge()
        bridge.status = lambda: {
            "connected": True,
            "instance_id": "test_browser",
            "capabilities": ["navigate_target_guarded"],
        }
        adapter = DefaultBrowserBridgeAdapter(bridge)
        self.assertFalse(await adapter.select_result(1))
        self.assertEqual(adapter.last_navigation_route, "result_bridge_outdated")
        self.assertFalse(bridge.ops)

    async def test_snapshot_advertised_allows_existing_verified_selection(self):
        from tests.unit.test_0_1_5_9_browser_result_selection import FakeBrowserBridge
        bridge = FakeBrowserBridge()
        adapter = DefaultBrowserBridgeAdapter(bridge)
        self.assertTrue(await adapter.select_result(1))
        self.assertEqual(adapter.last_navigation_route, "selected_video_same_tab")
        self.assertEqual(bridge.tabs[0]["url"], "https://www.youtube.com/watch?v=abcdefghijk")


if __name__ == "__main__":
    unittest.main()
