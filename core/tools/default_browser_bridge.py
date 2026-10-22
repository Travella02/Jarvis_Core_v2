"""Core-authorized default-browser bridge with conservative tab reuse.

A connected browser extension can identify and update an existing tab by ID.
Without a connected/authorized extension the OS opens the user's default
browser; Windows ShellExecute cannot control existing tabs, so reuse is NOT
claimed in that fallback. This adapter never guesses a tab or targets a
browser page merely because its title looks similar.
"""
from __future__ import annotations

from urllib.parse import urlsplit
from typing import Callable

from core.tools.browser_bridge import BrowserBridge, BrowserBridgeError
from core.tools.managed_browser import open_in_system_default


class DefaultBrowserBridgeAdapter:
    def __init__(self, bridge: BrowserBridge, *, open_default: Callable[[str], bool] | None = None):
        self.bridge = bridge
        self._open_default = open_default or open_in_system_default
        self.last_navigation_verified = False
        self.last_system_handoff = False
        self.last_navigation_route = 'none'
        # Ephemeral tab affinity for successful actions in this *same browser
        # instance*. Never trust it without a fresh tabs_list and host check.
        self._affinity: dict[str, int] = {}
        self._instance_id: str | None = None

    async def _snapshot(self) -> dict:
        if not self.bridge.status().get('connected'):
            raise BrowserBridgeError('browser_extension_disconnected')
        return await self.bridge.execute('tabs_list', {}, timeout_seconds=4)

    @staticmethod
    def _host(url: object) -> str:
        return (urlsplit(str(url or '')).hostname or '').lower().removeprefix('www.')

    @classmethod
    def _url_verified(cls, requested: str, actual: object) -> bool:
        expected, observed = urlsplit(requested), urlsplit(str(actual or ''))
        return (expected.scheme == 'https' and observed.scheme == 'https' and
                cls._host(actual) == cls._host(requested) and
                (observed.path or '/') == (expected.path or '/') and
                observed.query == expected.query)

    @staticmethod
    def _tab_id(tab: object) -> int:
        if not isinstance(tab, dict):
            return 0
        value = tab.get('id')
        return value if type(value) is int and value > 0 else 0

    def _refresh_instance(self) -> bool:
        status = self.bridge.status()
        if not status.get('connected'):
            self._affinity.clear()
            self._instance_id = None
            return False
        # Reset affinity if a different extension takes over the bridge.
        current = status.get('instance_id')
        if not isinstance(current, str) or not current:
            self._affinity.clear()
            self._instance_id = None
        elif current != self._instance_id:
            self._affinity.clear()
            self._instance_id = current
        return True

    def _pick_tab(self, state: dict, host: str) -> dict | None:
        matches = [tab for tab in state.get('tabs', []) if
                   isinstance(tab, dict) and self._host(tab.get('url')) == host
                   and self._tab_id(tab)]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            return None
        # The user's active matching tab wins over stored navigation history.
        active_id = self._tab_id(state.get('active_tab'))
        selected = next((tab for tab in matches if self._tab_id(tab) == active_id), None)
        if selected is not None:
            return selected
        remembered = self._affinity.get(host)
        # Only a previously verified tab in the *current* bridge instance is
        # eligible. No arbitrary first-tab choice when duplicates exist.
        return next((tab for tab in matches if self._tab_id(tab) == remembered), None)

    async def navigate(self, url: str) -> bool:
        self.last_navigation_verified = False
        self.last_system_handoff = False
        self.last_navigation_route = 'none'
        host = self._host(url)
        if not host or not url.startswith('https://'):
            self.last_navigation_route = 'invalid_url'
            return False
        connected = self._refresh_instance()
        # Old extension workers implement 'navigate active tab' and ignore
        # tab_id. Never send a targeted request until the worker explicitly
        # advertises the atomic/hostname-guarded navigation capability.
        if connected and 'navigate_target_guarded' not in self.bridge.status().get('capabilities', ()):
            self.last_navigation_route = 'default_extension_outdated'
            self.last_system_handoff = await self._safe_handoff(url)
            if not self.last_system_handoff:self.last_navigation_route = 'default_handoff_failed'
            return self.last_system_handoff
        if connected:
            try:
                state = await self._snapshot()
                matches = [tab for tab in state.get('tabs', []) if
                           isinstance(tab,dict) and self._host(tab.get('url')) == host and self._tab_id(tab)]
                target = self._pick_tab(state, host)
                if target is not None:
                    tab_id = self._tab_id(target)
                    # Atomic target: the extension independently verifies the
                    # old tab's host before applying the authorized URL.
                    # Never 'switch then navigate active tab' (focus race).
                    await self.bridge.execute('navigate', {
                        'url': url, 'tab_id': tab_id, 'expected_host': host,
                        'wait_for_load': True,
                    }, timeout_seconds=6)
                    observed = await self._snapshot()
                    tab = next((t for t in observed.get('tabs', []) if self._tab_id(t) == tab_id), None)
                    self.last_navigation_verified = bool(tab and self._url_verified(url, tab.get('url')))
                    if self.last_navigation_verified:
                        self._affinity[host] = tab_id
                        self.last_navigation_route = 'reused_connected_tab'
                    else:
                        self.last_navigation_route = 'navigation_not_verified'
                    return self.last_navigation_verified
                self.last_navigation_route = 'default_new_site' if not matches else 'default_ambiguous_tabs'
            except BrowserBridgeError:
                # An uncertain navigation may already have completed. Never
                # open another tab as an automatic retry.
                self.last_navigation_route = 'bridge_command_failed'
                return False
            except Exception:
                self.last_navigation_route = 'bridge_command_failed'
                return False
        else:
            self.last_navigation_route = 'default_bridge_disconnected'
        self.last_system_handoff = await self._safe_handoff(url)
        if not self.last_system_handoff:
            self.last_navigation_route = 'default_handoff_failed'
        return self.last_system_handoff

    async def _safe_handoff(self, url: str) -> bool:
        try:
            from asyncio import to_thread
            return await to_thread(self._open_default, url) is True
        except Exception:
            return False

    async def _matching_tab(self, host: str) -> dict | None:
        self._refresh_instance()
        state = await self._snapshot()
        return self._pick_tab(state, host)

    async def select_tab(self, host: str) -> bool:
        tab = await self._matching_tab(host)
        if not tab:return False
        response = await self.bridge.execute('tab_switch', {'tab_id': self._tab_id(tab)}, timeout_seconds=4)
        ok = self._tab_id(response.get('active_tab')) == self._tab_id(tab)
        if ok:self._affinity[host] = self._tab_id(tab)
        return ok

    async def close_named_tab(self, host: str) -> bool:
        tab = await self._matching_tab(host)
        if not tab:return False
        await self.bridge.execute('tab_close', {'tab_id': self._tab_id(tab)}, timeout_seconds=4)
        success = not any(self._tab_id(t) == self._tab_id(tab) for t in (await self._snapshot()).get('tabs', []))
        if success and self._affinity.get(host) == self._tab_id(tab):self._affinity.pop(host, None)
        return success

    async def close_tab(self) -> bool:
        tab = (await self._snapshot()).get('active_tab')
        if not self._tab_id(tab):return False
        await self.bridge.execute('tab_close', {'tab_id': self._tab_id(tab)}, timeout_seconds=4)
        success = not any(self._tab_id(t) == self._tab_id(tab) for t in (await self._snapshot()).get('tabs', []))
        if success:
            self._affinity = {host: tab_id for host, tab_id in self._affinity.items() if tab_id != self._tab_id(tab)}
        return success

    async def next_tab(self) -> bool:
        state = await self._snapshot()
        active = state.get('active_tab') or {}
        tabs = [t for t in state.get('tabs', []) if t.get('window_id') == active.get('window_id') and self._tab_id(t)]
        if len(tabs) < 2:return False
        current = next((i for i,t in enumerate(tabs) if self._tab_id(t) == self._tab_id(active)),None)
        if current is None:return False
        target = tabs[(current + 1) % len(tabs)]
        response = await self.bridge.execute('tab_switch', {'tab_id':self._tab_id(target)}, timeout_seconds=4)
        return self._tab_id(response.get('active_tab')) == self._tab_id(target)

    async def _simple(self, operation: str) -> bool:
        response = await self.bridge.execute(operation, {}, timeout_seconds=6)
        return bool(response.get('ok'))

    async def go_back(self) -> bool:return await self._simple('back')
    async def go_forward(self) -> bool:return await self._simple('forward')
    async def reload(self) -> bool:return await self._simple('refresh')

    async def media(self, operation: str, value: int | None = None) -> bool:
        if not self.bridge.status().get('connected'):return False
        if operation in ('play','pause'):
            command = 'media_control'; args = {'action':'play' if operation == 'play' else 'pause'}
        elif operation in ('mute','unmute'):
            command = 'media_mute'; args = {'muted':operation == 'mute'}
        elif operation == 'volume' and type(value) is int and 0 <= value <= 100:
            command = 'media_volume'; args = {'percent':value}
        else:return False
        response = await self.bridge.execute(command,args,timeout_seconds=6)
        return response.get('verified') is True

    async def close(self) -> None:
        # Do not close the user's browser or extension when a conversation sleeps.
        self._affinity.clear()
        self._instance_id = None
        return None
