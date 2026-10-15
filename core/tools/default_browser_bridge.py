"""0.1.5.6 opt-in adapter: existing browser extension, never a separate profile.

The model chooses an action; v2 Core verifies the current user's utterance.
Only then may this adapter ask the V1-derived browser extension to act.
No webpage text ever becomes permission or routing authority.
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

    async def navigate(self, url: str) -> bool:
        """Reuse a single matching site tab, otherwise hand off to OS default.

        Never hijack another site, a duplicate ambiguous target, or an unknown
        browser. OS fallback is intentional and reports *handoff*, not load.
        """
        self.last_navigation_verified = False
        self.last_system_handoff = False
        host = self._host(url)
        if not host or not url.startswith('https://'):
            return False
        if self.bridge.status().get('connected'):
            try:
                state = await self._snapshot()
                matched = [tab for tab in state.get('tabs', []) if
                           isinstance(tab,dict) and self._host(tab.get('url')) == host and self._tab_id(tab)]
                active_id = self._tab_id(state.get('active_tab'))
                target = (matched[0] if len(matched)==1 else
                          next((tab for tab in matched if self._tab_id(tab)==active_id), None))
                if target is not None:
                    await self.bridge.execute('tab_switch', {'tab_id':self._tab_id(target)}, timeout_seconds=4)
                    await self.bridge.execute('navigate', {'url':url, 'wait_for_load':True}, timeout_seconds=6)
                    observed = await self._snapshot()
                    tab = observed.get('active_tab')
                    self.last_navigation_verified = self._tab_id(tab) == self._tab_id(target) and self._url_verified(url,tab.get('url'))
                    return self.last_navigation_verified
            except BrowserBridgeError:
                # Do not re-run a possibly successful navigation as another tab.
                return False
            except Exception:
                return False
        self.last_system_handoff = await self._safe_handoff(url)
        return self.last_system_handoff

    async def _safe_handoff(self, url:str) -> bool:
        try:
            from asyncio import to_thread
            return await to_thread(self._open_default, url) is True
        except Exception:
            return False

    async def _matching_tab(self, host: str) -> dict | None:
        state = await self._snapshot()
        matched = [tab for tab in state.get('tabs',[]) if isinstance(tab,dict) and self._host(tab.get('url'))==host and self._tab_id(tab)]
        return matched[0] if len(matched)==1 else None

    async def select_tab(self, host:str) -> bool:
        tab=await self._matching_tab(host)
        if not tab:return False
        response=await self.bridge.execute('tab_switch',{'tab_id':self._tab_id(tab)},timeout_seconds=4)
        return self._tab_id(response.get('active_tab'))==self._tab_id(tab)

    async def close_named_tab(self, host:str) -> bool:
        tab=await self._matching_tab(host)
        if not tab:return False
        await self.bridge.execute('tab_close',{'tab_id':self._tab_id(tab)},timeout_seconds=4)
        return not any(self._tab_id(t)==self._tab_id(tab) for t in (await self._snapshot()).get('tabs',[]))

    async def close_tab(self) -> bool:
        tab=(await self._snapshot()).get('active_tab')
        if not self._tab_id(tab):return False
        await self.bridge.execute('tab_close',{'tab_id':self._tab_id(tab)},timeout_seconds=4)
        return not any(self._tab_id(t)==self._tab_id(tab) for t in (await self._snapshot()).get('tabs',[]))

    async def next_tab(self) -> bool:
        state=await self._snapshot()
        active=state.get('active_tab') or {}
        tabs=[t for t in state.get('tabs',[]) if t.get('window_id')==active.get('window_id') and self._tab_id(t)]
        if len(tabs)<2:return False
        current=next((i for i,t in enumerate(tabs) if self._tab_id(t)==self._tab_id(active)),None)
        if current is None:return False
        target=tabs[(current+1)%len(tabs)]
        response=await self.bridge.execute('tab_switch',{'tab_id':self._tab_id(target)},timeout_seconds=4)
        return self._tab_id(response.get('active_tab'))==self._tab_id(target)

    async def _simple(self,operation:str) -> bool:
        response=await self.bridge.execute(operation,{},timeout_seconds=6)
        return bool(response.get('ok'))

    async def go_back(self) -> bool:return await self._simple('back')
    async def go_forward(self) -> bool:return await self._simple('forward')
    async def reload(self) -> bool:return await self._simple('refresh')

    async def media(self,operation:str,value:int|None=None) -> bool:
        if not self.bridge.status().get('connected'):return False
        if operation in ('play','pause'):
            command='media_control'; args={'action':'play' if operation=='play' else 'pause'}
        elif operation in ('mute','unmute'):
            command='media_mute'; args={'muted':operation=='mute'}
        elif operation=='volume' and type(value) is int and 0<=value<=100:
            command='media_volume'; args={'percent':value}
        else:return False
        response=await self.bridge.execute(command,args,timeout_seconds=6)
        return response.get('verified') is True

    async def close(self)->None:
        # Do not close the user's browser or extension when a conversation sleeps.
        return None
