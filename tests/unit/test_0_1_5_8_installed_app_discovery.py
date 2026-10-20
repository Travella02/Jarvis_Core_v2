"""Inert 0.1.5.8 discovery and Core authorization regression coverage."""
from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
import threading
import unittest

from apps.desktop_unified_actions import UnifiedDesktopActionSession
from core.common.ids import CorrelationContext
from core.tools import ToolRequest, ToolResultStatus
from core.tools.app_discovery import (InstalledApp, InstalledAppInventory,
                                      discover_windows_apps, valid_aumid)
from core.tools.desktop_apps import CoreDesktopAppGateway
from core.tools.gateway import ConfirmedUserAction

ROOT = Path(__file__).resolve().parents[2]


def sample_inventory():
    return InstalledAppInventory(discover=lambda: [
        InstalledApp('Notepad', 'system', 'notepad.exe', 'system'),
        InstalledApp('File Explorer', 'system', 'explorer.exe', 'system'),
        InstalledApp('Discord', 'shortcut', 'C:/Start/Discord.lnk', 'start_menu'),
        InstalledApp('Spotify', 'shortcut', 'C:/Start/Spotify.lnk', 'start_menu'),
        InstalledApp('Google Chrome', 'executable', 'C:/apps/chrome.exe', 'app_paths'),
    ], auto_start=False)


class DiscoveryTests(unittest.TestCase):
    def test_bounded_start_menu_and_registry_discovery(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'Productivity').mkdir()
            (root/'Productivity'/'Discord.lnk').write_text('stub')
            (root/'Calculator.appref-ms').write_text('stub')
            (root/'Uninstall Discord.lnk').write_text('stub')
            (root/'Fake.url').write_text('stub')
            installed = discover_windows_apps(roots=[root], registry=lambda: [
                InstalledApp('Spotify', 'executable', 'C:/Apps/spotify.exe', 'app_paths'),
            ], include_system=False)
            self.assertEqual({i.name for i in installed}, {'Discord', 'Calculator', 'Spotify'})
            self.assertNotIn('Fake', {i.name for i in installed})

    def test_exact_vendor_name_and_typo_resolution(self):
        inv = sample_inventory()
        inv._refresh()
        for name, expected in [('discord', 'Discord'), ('Discrd', 'Discord'),
                               ('Chrome', 'Google Chrome'), ('file explorer', 'File Explorer')]:
            app, reason = inv.resolve(name)
            self.assertEqual(reason, 'resolved')
            self.assertEqual(app.name, expected)
        for name in ('https://discord.com','../discord','browser','Powershell','dis'):
            app, _ = inv.resolve(name)
            self.assertIsNone(app)

    def test_same_app_multiple_discovery_routes_is_not_ambiguous(self):
        inventory = InstalledAppInventory(discover=lambda: [
            InstalledApp('Discord', 'shortcut','C:/User/Discord.lnk','start_menu'),
            InstalledApp('Discord', 'shortcut','C:/Common/Discord.lnk','start_menu'),
            InstalledApp('Discord', 'aumid', 'DiscordCompany.Discord_x1!App','start_apps'),
        ], auto_start=False)
        inventory._refresh()
        app, reason = inventory.resolve('discord')
        self.assertEqual(reason, 'resolved')
        self.assertEqual(app.source, 'start_menu')

    def test_distinct_discord_variants_keep_distinct_names(self):
        inventory = InstalledAppInventory(discover=lambda: [
            InstalledApp('Discord Canary', 'shortcut','C:/User/Canary.lnk','start_menu'),
            InstalledApp('Discord', 'shortcut','C:/User/Discord.lnk','start_menu'),
        ], auto_start=False)
        inventory._refresh()
        self.assertEqual(inventory.resolve('Discord')[0].name, 'Discord')
        self.assertEqual(inventory.resolve('Discord Canary')[0].name, 'Discord Canary')

    def test_start_app_inventory_supports_store_music_names(self):
        discovered = discover_windows_apps(roots=[], registry=lambda: [], start_apps=lambda: [
            InstalledApp('Spotify Music','aumid','SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify','start_apps'),
            InstalledApp('Uninstall Dangerous','aumid','Dangerous.Blah!A','start_apps'),
            InstalledApp('Malicious', 'aumid','../../evil.exe','start_apps'),
        ], include_system=False)
        self.assertEqual([item.name for item in discovered], ['Spotify Music'])
        inventory = InstalledAppInventory(discover=lambda: discovered, auto_start=False)
        inventory._refresh()
        self.assertEqual(inventory.resolve('Spotify')[0].name, 'Spotify Music')
        self.assertFalse(valid_aumid('spotify;rm -rf'))
        self.assertFalse(valid_aumid('C:\\evil.exe'))

    def test_inventory_warming_does_not_claim_uninstalled(self):
        released = threading.Event()
        inventory = InstalledAppInventory(discover=lambda: (released.wait(timeout=1), [])[1], auto_start=True)
        try:
            self.assertEqual(inventory.resolve('Spotify')[1], 'inventory_warming')
        finally:
            released.set()
        self.assertTrue(inventory._ready.wait(timeout=1))
        self.assertEqual(inventory.resolve('Spotify')[1], 'app_not_found')

    def test_ambiguous_similar_names_stay_ambiguous(self):
        inv = InstalledAppInventory(discover=lambda: [
            InstalledApp('Discord', 'shortcut','a.lnk','start_menu'),
            InstalledApp('Discorb', 'shortcut','b.lnk','start_menu'),
        ], auto_start=False)
        inv._refresh()
        self.assertIsNone(inv.resolve('Discor')[0])


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.inv = sample_inventory()
        self.inv._refresh()
        self.launched = []
        self.gateway = CoreDesktopAppGateway(launcher=lambda name: self.launched.append(name) or True,
                                              inventory=self.inv, dynamic=True)

    async def ask(self, text, name='Discord', *, trace=None):
        trace = trace or CorrelationContext.create()
        request = ToolRequest(trace, 'desktop_app', 'launch', {'app':name}, idempotency_key='same-turn')
        return await self.gateway.execute(request, evidence=ConfirmedUserAction(trace.turn_id, text, True, True))

    async def test_discovered_app_launch_is_authorized_without_per_app_route(self):
        outcome = await self.ask('Thanks Jarvis, could you please launch Discord for me?')
        self.assertEqual(outcome.status, ToolResultStatus.SUCCEEDED)
        self.assertEqual(outcome.output['app_label'], 'Discord')
        self.assertFalse(outcome.output['window_visible_verified'])
        self.assertEqual(self.launched, ['Discord'])

    async def test_builtin_file_explorer_and_natural_preamble(self):
        outcome = await self.ask('Hey Jarvis, please bring up File Explorer.', 'File Explorer')
        self.assertEqual(outcome.status, ToolResultStatus.SUCCEEDED)

    async def test_no_mismatched_or_uninstalled_app_execution(self):
        for text, target in [('Open Discord', 'Spotify'), ('Open Discord', 'Windows Terminal'),
                             ('Open Spotify website', 'Spotify'), ('Open Spotify in browser', 'Spotify'),
                             ('Open Discord and Spotify', 'Discord'), ('Open Spotify and Discord', 'Spotify'),
                             ('Do not open Discord', 'Discord'), ('How do I open Discord?', 'Discord'),
                             ('Imagine opening Discord', 'Discord'), ('Open Discord and delete my files', 'Discord'),
                             ('Open discord.com', 'Discord')]:
            with self.subTest(text=text, target=target):
                self.assertNotEqual((await self.ask(text, target)).status, ToolResultStatus.SUCCEEDED)
        self.assertFalse(self.launched)

    async def test_replays_are_same_turn_only(self):
        trace = CorrelationContext.create()
        one = await self.ask('Open Discord', trace=trace)
        two = await self.ask('Open Discord', trace=trace)
        self.assertIs(one, two)
        other = await self.ask('Open Spotify', 'Spotify', trace=trace)
        self.assertEqual(other.error_code, 'replay_key_conflict')
        self.assertEqual(self.launched, ['Discord'])

    async def test_launch_failure_is_truthful(self):
        self.gateway = CoreDesktopAppGateway(launcher=lambda name: False, inventory=self.inv, dynamic=True)
        outcome = await self.ask('Open Discord')
        self.assertEqual(outcome.status, ToolResultStatus.FAILED)
        self.assertEqual(outcome.error_code, 'app_launch_unavailable')


class PolicyContracts(unittest.TestCase):
    def test_no_arbitrary_commands_or_paths_from_model(self):
        source = (ROOT/'core/tools/desktop_apps.py').read_text(encoding='utf-8')
        self.assertNotIn('shell=True', source)
        self.assertNotIn('subprocess.Popen(', source)
        self.assertIn("'window_visible_verified': False", source)
        policy = (ROOT/'apps/desktop_alpha.py').read_text(encoding='utf-8')
        self.assertIn('Installed app display name', policy)
        self.assertIn('if self._universal_apps', policy)
        ui = (ROOT/'apps/desktop/ui/src/App.tsx').read_text(encoding='utf-8')
        self.assertIn('Core independently resolves installed apps', ui)
        self.assertIn("pending.tool === 'launch_app'", ui)

    def test_desktop_browser_tool_is_still_separate(self):
        source = (ROOT/'apps/desktop_unified_actions.py').read_text(encoding='utf-8')
        self.assertIn("selected_tool != 'launch_app'", source)
        self.assertIn('super().handle(', source)

if __name__ == '__main__':
    unittest.main()
