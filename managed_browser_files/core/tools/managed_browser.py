"""Opt-in 0.1.5.4 managed browser: Core-authorized, read-only navigation.

Browser effects are never executed from provider callbacks. A model supplies a
proposal; Core compares it with a separately committed user transcript before
allowing this deliberately small set of operations. No script evaluation,
form filling, downloads, logins, data extraction, or arbitrary filesystem URLs.
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from urllib.parse import quote_plus, urlsplit
from typing import Protocol

from core.tools.contracts import ToolRequest, ToolResult, ToolResultStatus
from core.tools.gateway import ConfirmedUserAction
from core.tools.semantic_browser import _NEGATED, _NON_REQUEST, _SECOND_ACTION

CAPABILITY = 'desktop_browser'
ALLOWED = frozenset(('open', 'search', 'back', 'forward', 'reload', 'close_tab', 'next_tab'))
_DOMAIN = re.compile(r'^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$')
_ACTIONS = {
    'open': re.compile(r'\b(?:open|launch|visit|navigate|browse|pull\s+up|bring\s+up|go\s+to|take\s+me\s+to|show\s+me|load|head\s+to)\b', re.I),
    'search': re.compile(r'\b(?:search|find|look\s+up|show\s+me|find\s+(?:me\s+)?videos?)\b', re.I),
    'back': re.compile(r'\b(?:back|previous\s+page|page\s+before)\b', re.I),
    'forward': re.compile(r'\b(?:forward|next\s+page)\b', re.I),
    'reload': re.compile(r'\b(?:reload|refresh)\b', re.I),
    'close_tab': re.compile(r'\b(?:close|dismiss)\b', re.I),
    'next_tab': re.compile(r'\b(?:switch|next|other|change)\b', re.I),
}
_BLOCKED_TLDS = {'local', 'internal', 'localhost', 'onion', 'test', 'invalid'}
_COMPLEX_SUFFIXES = {'co.uk', 'org.uk', 'com.au', 'co.nz', 'com.br', 'co.jp'}
_EXPLICIT_HOST = re.compile(r'(?<![\w.-])(?:https?://)?(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)(?![\w.-])', re.I)


def normalize_host(site: object) -> str | None:
    if not isinstance(site, str): return None
    host = site.strip().lower()
    if host.startswith('www.'): host=host[4:]
    if not _DOMAIN.fullmatch(host) or host.rsplit('.',1)[-1] in _BLOCKED_TLDS:
        return None
    if any(p.startswith('xn--') for p in host.split('.')):
        return None  # IDN/homoglyph lookalikes deferred until explicit host confirmation UI.
    parts=host.split('.')
    # Only exact site hosts. Arbitrary subdomains and two-level public suffixes
    # need a separate approval surface to avoid hostname spoofing/confusion.
    if len(parts) > 2 and '.'.join(parts[-2:]) not in _COMPLEX_SUFFIXES:
        return None
    if len(parts) > 3:
        return None
    if len(parts) == 3 and '.'.join(parts[-2:]) not in _COMPLEX_SUFFIXES:
        return None
    return host


def site_label(host: str) -> str:
    pieces=host.split('.')
    return pieces[-3] if len(pieces)==3 else pieces[-2]


def trusted_intent(text: object, operation: str, host: str | None) -> bool:
    if not isinstance(text,str) or not (2 <= len(text) <= 2000) or operation not in ALLOWED:
        return False
    text=' '.join(text.split())
    safe=re.sub(r'\bappreciate\s+it\s+if\s+you\s+(?:could|would|can)\b',
                'appreciate it please', text, flags=re.I)
    if any(pattern.search(safe) for pattern in (_NEGATED, _NON_REQUEST, _SECOND_ACTION)):
        return False
    if not _ACTIONS[operation].search(text):
        return False
    # A single open-site effect must not silently satisfy one clause of a compound
    # request such as 'open Google and YouTube'. Search is a distinct operation.
    if operation=='open' and re.search(r'\b(?:open|launch|visit)\b.{0,100}\band\b', text, re.I):
        return False
    if operation in ('back','forward','reload','close_tab','next_tab'):
        if host not in (None,'current'): return False
        if operation=='close_tab' and not re.search(r'\b(?:tab|page|browser)\b',text,re.I): return False
        if operation=='next_tab' and not re.search(r'\btab\b',text,re.I): return False
        return True
    if not host: return False
    if operation=='search':
        if host=='google.com' and re.search(r'\b(?:web|internet|online|google)\b',text,re.I):
            return True
        if host=='youtube.com' and re.search(r'\b(?:youtube|you\s+tube)\b',text,re.I):
            return True
    # If a fully qualified host was spoken, require an EXACT host match.
    # Otherwise allow a model-proposed bare *registered* domain only if its
    # distinctive domain label was actually uttered by the user.
    mentioned=[]
    for match in _EXPLICIT_HOST.finditer(text):
        normalized=normalize_host(match.group(1))
        if normalized: mentioned.append(normalized)
    if mentioned:
        return len(set(mentioned)) == 1 and mentioned[0] == host
    label=site_label(host)
    return bool(re.search(r'(?<!\w)'+re.escape(label)+r'(?!\w)', text, re.I))


class BrowserOperations(Protocol):
    async def navigate(self, url: str) -> bool: ...
    async def go_back(self) -> bool: ...
    async def go_forward(self) -> bool: ...
    async def reload(self) -> bool: ...
    async def close_tab(self) -> bool: ...
    async def next_tab(self) -> bool: ...
    async def close(self) -> None: ...


class PlaywrightManagedBrowser:
    """Visible isolated browser profile. Only Core calls these methods.

    Playwright is optional and loaded lazily, so the accepted conversational
    path never gains a startup dependency or another model round trip.
    """
    def __init__(self, profile_dir: Path | None = None):
        self._profile = profile_dir or (Path(os.environ.get('LOCALAPPDATA') or Path.home()) /
                                      'ORVEX' / 'Jarvis' / 'BrowserProfile')
        self._playwright = None
        self._context = None
        self._current = None

    async def _context_ready(self):
        if self._context is not None: return self._context
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError('browser_dependency_missing') from exc
        self._profile.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()
        try:
            browser=self._playwright.chromium
            kwargs={'user_data_dir':str(self._profile),'headless':False,
                    'accept_downloads':False,'permissions':[],
                    'viewport':None,'no_viewport':True}
            if os.name=='nt':
                try: self._context = await browser.launch_persistent_context(channel='msedge', **kwargs)
                except Exception: self._context = await browser.launch_persistent_context(**kwargs)
            else:
                self._context=await browser.launch_persistent_context(**kwargs)
            return self._context
        except BaseException as exc:
            await self._playwright.stop();self._playwright=None
            if isinstance(exc,asyncio.CancelledError): raise
            raise RuntimeError('browser_start_failed') from exc

    async def _page(self):
        context=await self._context_ready()
        if self._current is not None and not self._current.is_closed():
            return self._current
        self._current=next((p for p in reversed(context.pages) if not p.is_closed()),None)
        if self._current is None: self._current=await context.new_page()
        return self._current

    async def navigate(self,url: str) -> bool:
        context=await self._context_ready()
        page=await self._page()
        if page.url!='about:blank':page=await context.new_page()
        await page.bring_to_front()
        self._current=page
        # Navigation commitment confirms the browser received/started a page,
        # NOT that website scripts or media loaded successfully.
        await page.goto(url,wait_until='commit',timeout=3500)
        return urlsplit(page.url).scheme in ('http','https')

    async def go_back(self) -> bool:
        page=await self._page()
        result=await page.go_back(wait_until='commit',timeout=3500)
        await page.bring_to_front()
        return result is not None

    async def go_forward(self) -> bool:
        page=await self._page()
        result=await page.go_forward(wait_until='commit',timeout=3500)
        await page.bring_to_front()
        return result is not None

    async def reload(self) -> bool:
        page=await self._page()
        if page.url=='about:blank':return False
        result=await page.reload(wait_until='commit',timeout=3500)
        await page.bring_to_front()
        return result is not None

    async def close_tab(self) -> bool:
        if self._context is None: return False
        page=await self._page()
        if page.url=='about:blank':return False
        await page.close()
        self._current=next((p for p in reversed(self._context.pages) if not p.is_closed()),None)
        return True

    async def next_tab(self) -> bool:
        if self._context is None:return False
        pages=[p for p in self._context.pages if not p.is_closed() and p.url!='about:blank']
        if len(pages)<2:return False
        selected=self._current if self._current in pages else pages[-1]
        self._current=pages[(pages.index(selected)+1)%len(pages)]
        await self._current.bring_to_front()
        return True

    async def close(self) -> None:
        try:
            if self._context is not None: await self._context.close()
        finally:
            self._context=None;self._current=None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright=None


class ManagedBrowserGateway:
    """Single-user, opt-in, transcript-bound browser authorization."""
    def __init__(self, browser: BrowserOperations | None = None):
        self.browser=browser or PlaywrightManagedBrowser()
        self._lock=asyncio.Lock()
        self._replays:dict[tuple[str,str],tuple[str,ToolResult]]={}

    async def execute(self, request:ToolRequest, *, evidence:ConfirmedUserAction|None) -> ToolResult:
        def outcome(status,code=None,message=None,output=None):
            return ToolResult(request.trace,request.tool_name,request.operation,status,output or {},
                              provider_call_id=request.provider_call_id,error_code=code,error_message=message)
        if request.tool_name!=CAPABILITY or request.operation not in ALLOWED:
            return outcome(ToolResultStatus.DENIED,'unknown_capability','That browser operation is not supported yet.')
        operation=request.operation
        arguments=dict(request.arguments)
        expected={'site','query'} if operation=='search' else {'site'}
        if set(arguments)!=expected:return outcome(ToolResultStatus.DENIED,'invalid_arguments','Those browser parameters are not supported.')
        site=arguments['site']
        host=normalize_host(site) if operation in ('open','search') else ('current' if site=='current' else None)
        if not host:return outcome(ToolResultStatus.DENIED,'unsafe_destination','I need a valid public website name to open.')
        query=arguments.get('query')
        if operation=='search' and (not isinstance(query,str) or not 2<=len(query.strip())<=160
                                    or any(c in query for c in '\r\n\0') or host not in ('youtube.com','google.com')):
            return outcome(ToolResultStatus.DENIED,'unsupported_search','I can search YouTube or Google in this browser test.')
        if (evidence is None or not evidence.confirmed or not evidence.local_desktop or
                request.trace.turn_id!=evidence.turn_id or not request.trace.turn_id or
                not trusted_intent(evidence.transcript,operation,host)):
            return outcome(ToolResultStatus.DENIED,'unverified_user_intent',
                           'I could not verify that immediate browser request, so I did not act.')
        replay=(evidence.turn_id,request.idempotency_key or request.trace.request_id)
        fingerprint=repr((operation,host,query))
        async with self._lock:
            previous=self._replays.get(replay)
            if previous:
                if previous[0]!=fingerprint:return outcome(ToolResultStatus.DENIED,'replay_key_conflict')
                return previous[1]
            if operation=='search':
                uri=('https://www.youtube.com/results?search_query=' if host=='youtube.com'
                     else 'https://www.google.com/search?q=')+quote_plus(query.strip())
            else:
                uri=f'https://www.{host}/' if operation=='open' else ''
            try:
                async def act():
                    if operation in ('open','search'):return await self.browser.navigate(uri)
                    return await getattr(self.browser,{'back':'go_back','forward':'go_forward',
                         'reload':'reload','close_tab':'close_tab','next_tab':'next_tab'}[operation])()
                success=await asyncio.wait_for(act(),timeout=7.0)
                result=(outcome(ToolResultStatus.SUCCEEDED,output={
                    'operation':operation,'browser_navigation_committed':success,
                    'page_loaded_verified':False,'url':uri if uri else None,
                    'user_message':'I completed the browser action.'})
                    if success else outcome(ToolResultStatus.FAILED,'not_available',
                                            'That browser action was not available in the current tab.'))
            except asyncio.TimeoutError:
                result=outcome(ToolResultStatus.FAILED,'unverified_timeout',
                               'I could not confirm that browser action completed.')
            except RuntimeError as exc:
                code=str(exc) if str(exc) in ('browser_dependency_missing','browser_start_failed') else 'browser_failure'
                message=('The browser component is not installed yet.' if code=='browser_dependency_missing'
                         else 'I could not start the managed browser.' if code=='browser_start_failed'
                         else 'I could not complete that browser action.')
                result=outcome(ToolResultStatus.FAILED,code,message)
            except Exception:
                result=outcome(ToolResultStatus.FAILED,'browser_failure',
                               'I could not confirm that browser action completed.')
            self._replays[replay]=(fingerprint,result)
            return result

    async def close(self):
        await self.browser.close()
