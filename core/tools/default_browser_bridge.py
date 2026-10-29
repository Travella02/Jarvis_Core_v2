"""Core-authorized default-browser bridge with conservative tab reuse.

A connected browser extension can identify and update an existing tab by ID.
Without a connected/authorized extension the OS opens the user's default
browser; Windows ShellExecute cannot control existing tabs, so reuse is NOT
claimed in that fallback. This adapter never guesses a tab or targets a
browser page merely because its title looks similar.
"""
from __future__ import annotations

import asyncio
from urllib.parse import urlsplit, parse_qs
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
        self.last_scroll_identity: tuple[int,str] | None = None

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

    async def verify_active_site(self, host: str) -> bool:
        """Independently ground a site-omitting video search in the active tab.

        No arbitrary background tab or stale affinity counts as context. The
        connected extension must report the same HTTPS tab as active and in
        its current tabs list, with a guarded-navigation capability.
        """
        if host != 'youtube.com' or not self._refresh_instance():
            return False
        if 'navigate_target_guarded' not in self.bridge.status().get('capabilities', ()):
            return False
        try:
            state = await self._snapshot()
            active = state.get('active_tab') or {}
            tab_id = self._tab_id(active)
            if not tab_id or self._host(active.get('url')) != host or urlsplit(str(active.get('url') or '')).scheme != 'https':
                return False
            return any(self._tab_id(tab) == tab_id and
                       str(tab.get('url') or '') == str(active.get('url') or '')
                       for tab in state.get('tabs', ()) if isinstance(tab, dict))
        except Exception:
            return False

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

    async def select_result(self, index: int) -> bool:
        """Open a grounded YouTube search result in its existing tab.

        No model-provided URL or selector crosses this boundary. The connected
        extension supplies a fresh page snapshot; Core selects a deduplicated,
        validated watch link and uses the already guarded same-host navigation.
        """
        self.last_navigation_verified = False
        self.last_navigation_route = 'result_not_verified'
        self.last_media_verified = False
        if type(index) is not int or not 1 <= index <= 10 or not self._refresh_instance():
            return False
        if not {'snapshot', 'navigate_target_guarded'}.issubset(
                set(self.bridge.status().get('capabilities', ()))):
            self.last_navigation_route = 'result_bridge_outdated'
            return False
        try:
            before = await self._snapshot()
            active = before.get('active_tab') or {}
            tab_id = self._tab_id(active)
            old_url = str(active.get('url') or '')
            parsed = urlsplit(old_url)
            if not (tab_id and self._host(old_url) == 'youtube.com'
                    and parsed.scheme == 'https' and parsed.path == '/results'
                    and parse_qs(parsed.query).get('search_query')):
                self.last_navigation_route = 'result_not_search_page'
                return False
            snapshot = await self.bridge.execute('snapshot', {}, timeout_seconds=4)
            page = snapshot.get('page') or {}
            observed_tab = snapshot.get('active_tab') or {}
            # Snapshot is active-tab-only; never confuse a focus switch with
            # authorization for a different tab.
            if (self._tab_id(observed_tab) != tab_id or
                    str(page.get('url') or '') != old_url or
                    not page.get('supported')):
                self.last_navigation_route = 'result_tab_changed'
                return False
            videos = []
            seen = set()
            for element in page.get('elements', [])[:160]:
                if not isinstance(element, dict) or element.get('disabled') or element.get('risk') != 'normal':
                    continue
                target = str(element.get('href') or '')
                parts = urlsplit(target)
                if parts.scheme != 'https' or self._host(target) != 'youtube.com' or parts.path != '/watch':
                    continue
                ids = parse_qs(parts.query).get('v', [])
                video_id = ids[0] if len(ids) == 1 else ''
                if not (len(video_id) == 11 and video_id.isascii() and
                        all(ch.isalnum() or ch in '-_' for ch in video_id)):
                    continue
                if video_id not in seen:
                    seen.add(video_id)
                    videos.append('https://www.youtube.com/watch?v=' + video_id)
            if not 1 <= index <= len(videos):
                self.last_navigation_route = 'result_index_unavailable'
                return False
            target_url = videos[index - 1]
            await self.bridge.execute('navigate', {
                'url':target_url, 'tab_id':tab_id, 'expected_host':'youtube.com',
                'wait_for_load':False,
            },timeout_seconds=4)
            # chrome.tabs.update may return before Chrome publishes the new URL
            # to tabs_list. Verify the SAME tab with a bounded read-only poll;
            # never navigate twice or accept a mere command acknowledgement.
            # Slow YouTube navigation must not become a false reported failure.
            same_video = False
            for delay in (0, 0.15, 0.25, 0.4, 0.6, 0.9):
                if delay:
                    await asyncio.sleep(delay)
                after = await self._snapshot()
                target = next((tab for tab in after.get('tabs', []) if self._tab_id(tab) == tab_id), None)
                observed = str(target.get('url') or '') if target else ''
                watched = urlsplit(observed)
                # YouTube can add tracking parameters; the actual video ID,
                # HTTPS host, path and original tab identity must match.
                same_video = bool(target and watched.scheme == 'https' and
                                  self._host(observed) == 'youtube.com' and
                                  watched.path == '/watch' and
                                  parse_qs(watched.query).get('v') == [target_url.rsplit('=', 1)[-1]])
                if same_video:
                    break
            if not same_video:
                self.last_navigation_route = 'result_navigation_unverified'
                return False
            self.last_navigation_verified = True
            self.last_navigation_route = 'selected_video_same_tab'
            self._affinity['youtube.com'] = tab_id
            # Opening a YouTube watch page is verified, but playback is not
            # automatically asserted. Modern browsers may block autoplay.
            return True
        except (BrowserBridgeError, ValueError, TypeError, KeyError):
            self.last_navigation_route = 'result_bridge_failed'
            return False
        except Exception:
            self.last_navigation_route = 'result_bridge_failed'
            return False

    async def verify_active_youtube_results(self) -> bool:
        if not self._refresh_instance():
            return False
        if not {'snapshot','scroll'}.issubset(set(self.bridge.status().get('capabilities', ()))):
            return False
        try:
            state=await self.bridge.execute('snapshot', {}, timeout_seconds=4)
            active=state.get('active_tab') or {}
            page=state.get('page') or {}
            url=str(active.get('url') or '')
            parts=urlsplit(url)
            return bool(self._tab_id(active) and parts.scheme=='https'
                        and self._host(url)=='youtube.com' and parts.path=='/results'
                        and parse_qs(parts.query).get('search_query')
                        and page.get('supported') is True and page.get('url')==url)
        except Exception:
            return False

    async def verify_scroll_identity(self, identity: tuple[int,str]) -> bool:
        # Contextual continuations must remain on exactly the same active tab
        # and URL as the last confirmed scroll (never a background tab).
        if not self._refresh_instance() or 'snapshot' not in self.bridge.status().get('capabilities', ()): return False
        try:
            state=await self.bridge.execute('snapshot', {}, timeout_seconds=4)
            active=state.get('active_tab') or {}
            page=state.get('page') or {}
            return (type(identity) is tuple and len(identity)==2 and
                    self._tab_id(active)==identity[0] and active.get('url')==identity[1] and
                    page.get('url')==identity[1] and page.get('supported') is True)
        except Exception:
            return False

    async def verify_active_youtube_watch(self) -> int:
        # Bound a media command to a freshly verified active watch tab. A
        # background YouTube tab does not grant permission to pause it.
        if not self._refresh_instance() or 'snapshot' not in self.bridge.status().get('capabilities', ()): return 0
        try:
            state=await self.bridge.execute('snapshot', {}, timeout_seconds=4)
            active=state.get('active_tab') or {}
            page=state.get('page') or {}
            url=str(active.get('url') or '')
            parts=urlsplit(url)
            video_id=parse_qs(parts.query).get('v', [''])[0]
            if (self._tab_id(active) and parts.scheme=='https' and self._host(url)=='youtube.com'
                    and parts.path=='/watch' and len(video_id)==11 and
                    page.get('supported') is True and page.get('url')==url):
                return self._tab_id(active)
        except Exception:
            pass
        return 0

    async def scroll(self, direction: str) -> bool:
        """Scroll only a freshly verified active public tab and check actual movement.

        The extension independently checks both tab ID and original URL before
        changing anything. A command ACK by itself does not prove movement.
        """
        self.last_scroll_route='not_verified'
        self.last_scroll_identity=None
        if direction not in ('up','down','top','bottom') or not self._refresh_instance():
            return False
        if not {'snapshot','scroll'}.issubset(set(self.bridge.status().get('capabilities', ()))):
            self.last_scroll_route='extension_outdated'
            return False
        try:
            before=await self.bridge.execute('snapshot', {}, timeout_seconds=4)
            active=before.get('active_tab') or {}
            page=before.get('page') or {}
            tab_id=self._tab_id(active)
            url=str(active.get('url') or '')
            if not (tab_id and urlsplit(url).scheme in ('https','http')
                    and page.get('supported') is True and page.get('url')==url
                    and type(page.get('scroll_y')) is int):
                self.last_scroll_route='unsupported_page'
                return False
            old=page['scroll_y']
            max_scroll=max(0, int(page.get('scroll_height') or 0) - int(page.get('viewport_height') or 0))
            if max_scroll==0 or ((direction in ('top','up') and old<=0) or
                                 (direction in ('bottom','down') and old>=max_scroll)):
                self.last_scroll_route='already_at_edge'
                self.last_scroll_identity=(tab_id,url)
                return True
            await self.bridge.execute('scroll', {'direction':direction,'tab_id':tab_id,'expected_url':url}, timeout_seconds=4)
            for delay in (0,0.10,0.18):
                if delay: await asyncio.sleep(delay)
                after=await self.bridge.execute('snapshot', {}, timeout_seconds=4)
                current=after.get('active_tab') or {}
                current_page=after.get('page') or {}
                if (self._tab_id(current)!=tab_id or str(current.get('url') or '')!=url
                    or current_page.get('url')!=url):
                    self.last_scroll_route='tab_changed'
                    return False
                new=current_page.get('scroll_y')
                if type(new) is int and ((direction in ('down','bottom') and new>old) or
                                         (direction in ('up','top') and new<old)):
                    self.last_scroll_route='verified_scroll'
                    self.last_scroll_identity=(tab_id,url)
                    return True
            self.last_scroll_route='movement_unverified'
            return False
        except Exception:
            self.last_scroll_route='bridge_scroll_failed'
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

    async def media(self, operation: str, value: int | None = None, *, preferred_tab_id: int = 0) -> bool:
        if not self.bridge.status().get('connected'):return False
        if operation in ('play','pause'):
            command = 'media_control'; args = {'action':'play' if operation == 'play' else 'pause'}
        elif operation in ('mute','unmute'):
            command = 'media_mute'; args = {'muted':operation == 'mute'}
        elif operation == 'volume' and type(value) is int and 0 <= value <= 100:
            command = 'media_volume'; args = {'percent':value}
        elif operation in ('fullscreen', 'exit_fullscreen'):
            command = 'media_fullscreen'; args = {'action': 'enter' if operation == 'fullscreen' else 'exit'}
        else:return False
        if preferred_tab_id:
            if type(preferred_tab_id) is not int or preferred_tab_id<1 or not await self.verify_active_youtube_watch()==preferred_tab_id:
                return False
            args['preferred_tab_id']=preferred_tab_id
        response = await self.bridge.execute(command,args,timeout_seconds=6)
        return response.get('verified') is True

    async def close(self) -> None:
        # Do not close the user's browser or extension when a conversation sleeps.
        self._affinity.clear()
        self._instance_id = None
        return None
