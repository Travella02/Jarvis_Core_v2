"""No-audio regression tests for verified app route retries and persistent history."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.common.ids import CorrelationContext
from core.tools import ToolRequest, ToolResultStatus
from core.tools.app_discovery import InstalledApp, InstalledAppInventory
from core.tools.app_launch_history import AppLaunchHistory
from core.tools.desktop_apps import CoreDesktopAppGateway
from core.tools.gateway import ConfirmedUserAction


def inventory(*routes: InstalledApp) -> InstalledAppInventory:
    found = InstalledAppInventory(discover=lambda: list(routes), auto_start=False)
    found._refresh()
    return found


def discord_routes():
    return (
        InstalledApp('Discord', 'shortcut', 'C:/Start/Discord.lnk', 'start_menu'),
        InstalledApp('Discord', 'aumid', 'DiscordPkg.123!Discord', 'start_apps'),
        InstalledApp('Discord', 'executable', 'C:/Apps/Discord.exe', 'app_paths'),
    )


class FallbackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.history = AppLaunchHistory(Path(self.temp.name) / 'app_launch_history.json')
        self.routes = discord_routes()
        self.inv = inventory(*self.routes)
        self.attempts = []

    async def asyncTearDown(self):
        self.temp.cleanup()

    async def ask(self, gateway, utterance='Please open Discord.', target='Discord', trace=None):
        trace = trace or CorrelationContext.create()
        req = ToolRequest(trace, 'desktop_app', 'launch', {'app': target}, idempotency_key='r2')
        proof = ConfirmedUserAction(trace.turn_id, utterance, True, True)
        return await gateway.execute(req, evidence=proof)

    async def test_fallback_to_second_verified_route_and_persist_preference(self):
        def try_route(route):
            self.attempts.append(route.target)
            return route.kind == 'aumid'
        gateway = CoreDesktopAppGateway(inventory=self.inv, dynamic=True, history=self.history)
        with patch('core.tools.desktop_apps.launch_windows_installed_app', try_route):
            result = await self.ask(gateway)
        self.assertEqual(result.status, ToolResultStatus.SUCCEEDED)
        self.assertFalse(result.output['window_visible_verified'])
        self.assertEqual(self.attempts, [self.routes[0].target, self.routes[1].target])
        saved = json.loads(self.history.path.read_text(encoding='utf-8'))
        self.assertEqual([r['result'] for r in saved['recent']], ['handoff_failed', 'handoff_accepted'])
        self.assertEqual(saved['preferred']['discord']['target'], self.routes[1].target)
        self.assertNotIn('Please open Discord', str(saved))
        # Fresh gateway/session still prefers the previously accepted registration.
        self.attempts.clear()
        gateway = CoreDesktopAppGateway(inventory=self.inv, dynamic=True, history=AppLaunchHistory(self.history.path))
        with patch('core.tools.desktop_apps.launch_windows_installed_app', try_route):
            result = await self.ask(gateway)
        self.assertEqual(result.status, ToolResultStatus.SUCCEEDED)
        self.assertEqual(self.attempts, [self.routes[1].target])

    async def test_failed_preferred_route_is_invalidated_and_falls_back(self):
        self.history.record(self.routes[1], accepted=True)
        seen=[]
        def try_route(app):
            seen.append(app.target)
            return app.kind == 'executable'
        gateway = CoreDesktopAppGateway(inventory=self.inv, dynamic=True, history=self.history)
        with patch('core.tools.desktop_apps.launch_windows_installed_app', try_route):
            result = await self.ask(gateway)
        self.assertEqual(result.status, ToolResultStatus.SUCCEEDED)
        self.assertEqual(seen, [self.routes[1].target, self.routes[0].target, self.routes[2].target])
        self.assertEqual(self.history.preferred('Discord', self.routes), self.routes[2])

    async def test_never_retry_after_windows_accepts_handoff(self):
        gateway = CoreDesktopAppGateway(inventory=self.inv, dynamic=True, history=self.history)
        with patch('core.tools.desktop_apps.launch_windows_installed_app', side_effect=lambda route: self.attempts.append(route.target) or True):
            result = await self.ask(gateway)
        self.assertEqual(result.status, ToolResultStatus.SUCCEEDED)
        self.assertEqual(len(self.attempts), 1)

    async def test_no_retry_or_record_on_non_request_or_wrong_app(self):
        gateway = CoreDesktopAppGateway(inventory=self.inv, dynamic=True, history=self.history)
        with patch('core.tools.desktop_apps.launch_windows_installed_app') as launch:
            for text in ('Do not open Discord.', 'How do I open Discord?', 'Open Discord and delete my files.', 'Open Spotify.'):
                result = await self.ask(gateway, utterance=text)
                self.assertEqual(result.status, ToolResultStatus.DENIED)
            launch.assert_not_called()
        self.assertFalse(self.history.path.exists())

    async def test_retry_only_same_app_identity_not_branded_variant(self):
        canary=InstalledApp('Discord Canary', 'shortcut', 'C:/Start/Canary.lnk', 'start_menu')
        inv=inventory(*self.routes,canary)
        seen=[]
        gateway = CoreDesktopAppGateway(inventory=inv, dynamic=True, history=self.history)
        with patch('core.tools.desktop_apps.launch_windows_installed_app', side_effect=lambda route: seen.append(route.name) or False):
            result = await self.ask(gateway)
        self.assertEqual(result.status, ToolResultStatus.FAILED)
        self.assertEqual(seen, ['Discord']*3)

    async def test_same_turn_replay_no_second_launch(self):
        gateway=CoreDesktopAppGateway(inventory=self.inv, dynamic=True, history=self.history)
        trace=CorrelationContext.create()
        with patch('core.tools.desktop_apps.launch_windows_installed_app', side_effect=lambda route: self.attempts.append(route) or True):
            one=await self.ask(gateway, trace=trace)
            two=await self.ask(gateway, trace=trace)
        self.assertIs(one, two)
        self.assertEqual(len(self.attempts), 1)
        self.assertEqual(len(json.loads(self.history.path.read_text())['recent']),1)

    async def test_permission_failed_never_uses_cached_route(self):
        self.history.record(self.routes[0], accepted=True)
        gateway=CoreDesktopAppGateway(inventory=self.inv,dynamic=True,history=self.history)
        with patch('core.tools.desktop_apps.launch_windows_installed_app') as launch:
            result=await self.ask(gateway,utterance='Imagine Jarvis opening Discord.')
            launch.assert_not_called()
        self.assertEqual(result.status, ToolResultStatus.DENIED)

    async def test_uncertain_failure_speaks_failure_no_false_success(self):
        gateway=CoreDesktopAppGateway(inventory=self.inv,dynamic=True,history=self.history)
        with patch('core.tools.desktop_apps.launch_windows_installed_app', return_value=False):
            result=await self.ask(gateway)
        self.assertEqual(result.status, ToolResultStatus.FAILED)
        self.assertEqual(result.error_code,'app_launch_unavailable')
        self.assertIn('didn',result.error_message.lower())

    async def test_jarvis_and_jervis_spoken_prefixes_are_valid_requests(self):
        for text in ('Jarvis, open Discord.', 'Jervis, please open Discord.'):
            gateway=CoreDesktopAppGateway(inventory=self.inv,dynamic=True,history=self.history)
            with patch('core.tools.desktop_apps.launch_windows_installed_app',return_value=True):
                result=await self.ask(gateway,utterance=text)
            self.assertEqual(result.status,ToolResultStatus.SUCCEEDED,text)


class HistoryTests(unittest.TestCase):
    def test_tampered_cached_path_cannot_become_launch_capability(self):
        with tempfile.TemporaryDirectory() as temp:
            hist=AppLaunchHistory(Path(temp)/'history.json')
            legit=discord_routes()[0]
            hist.record(legit,accepted=True)
            raw=json.loads(hist.path.read_text())
            raw['preferred']['discord']['target']='C:/untrusted/malware.exe'
            hist.path.write_text(json.dumps(raw))
            loaded=AppLaunchHistory(hist.path)
            self.assertIsNone(loaded.preferred('Discord',[legit]))

    def test_history_is_bounded_and_corrupt_json_does_not_crash(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'history.json'
            path.write_text('not-json')
            hist=AppLaunchHistory(path)
            for _ in range(180):hist.record(discord_routes()[0],accepted=False)
            self.assertEqual(len(json.loads(path.read_text())['recent']),120)
