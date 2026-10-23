"""Opt-in 0.1.5.5 managed browser: Core-authorized navigation and basic HTML5 media.

Browser effects are never executed from provider callbacks. A model supplies a
proposal; Core compares it with a separately committed user transcript before
allowing this deliberately small set of operations. No script evaluation,
form filling, downloads, logins, arbitrary page scripting,
account data extraction, or filesystem URLs. Media uses only audited static code.
"""
from __future__ import annotations

import asyncio
import os
import re
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus, urlsplit
from typing import Protocol

from core.tools.contracts import ToolRequest, ToolResult, ToolResultStatus
from core.tools.gateway import ConfirmedUserAction
from core.tools.semantic_browser import _NEGATED, _NON_REQUEST, _SECOND_ACTION

CAPABILITY = 'desktop_browser'
ALLOWED = frozenset(('open', 'open_managed', 'search', 'back', 'forward', 'reload', 'close_tab', 'next_tab',
                     'select_tab', 'close_named_tab', 'play', 'pause', 'mute', 'unmute', 'volume',
                     'select_result', 'fullscreen', 'exit_fullscreen'))
NAMED_TABS = frozenset(('select_tab','close_named_tab'))
MEDIA = frozenset(('play','pause','mute','unmute','volume','fullscreen','exit_fullscreen'))
_DOMAIN = re.compile(r'^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$')
_ACTIONS = {
    'open': re.compile(r'\b(?:open|launch|visit|navigate|browse|pull\s+up|bring\s+up|go\s+to|take\s+me\s+to|show\s+me|load|head\s+to)\b', re.I),
    'open_managed': re.compile(r'\b(?:open|launch|visit|navigate|browse|pull\s+up|bring\s+up|go\s+to|take\s+me\s+to|show\s+me|load|head\s+to)\b', re.I),
    'search': re.compile(r'\b(?:search|find|look\s+up|show\s+me|find\s+(?:me\s+)?videos?)\b', re.I),
    'back': re.compile(r'\b(?:back|previous\s+page|page\s+before)\b', re.I),
    'forward': re.compile(r'\b(?:forward|next\s+page)\b', re.I),
    'reload': re.compile(r'\b(?:reload|refresh)\b', re.I),
    'close_tab': re.compile(r'\b(?:close|dismiss)\b', re.I),
    'next_tab': re.compile(r'\b(?:switch|next|other|change)\b', re.I),
    'select_tab': re.compile(r'\b(?:switch|show|select|go|move|change|bring)\b', re.I),
    'close_named_tab': re.compile(r'\b(?:close|dismiss)\b', re.I),
    'play': re.compile(r'\b(?:play|resume|start)\b', re.I),
    'pause': re.compile(r'\b(?:pause|stop)\b', re.I),
    'mute': re.compile(r'\bmute\b|\bturn\s+(?:the\s+)?sound\s+off\b', re.I),
    'unmute': re.compile(r'\bunmute\b|\bturn\s+(?:the\s+)?sound\s+on\b', re.I),
    'volume': re.compile(r'\b(?:volume|sound)\b', re.I),
    'select_result': re.compile(r'\b(?:play|open|select|choose|click|watch|start|show)\b', re.I),
    'fullscreen': re.compile(r'\b(?:full\s?screen|maximize)\b', re.I),
    'exit_fullscreen': re.compile(r'\b(?:exit|leave|close|stop)\b.*\bfull\s?screen\b|\b(?:minimize|unfullscreen)\b', re.I),
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


def _phonetic_search_evidence(text: str, host: str | None, query: object) -> bool:
    """Conservative STT repair, not intent routing or a generic fuzzy command.

    Realtime must already have proposed SEARCH. Only tolerate a search-like
    *verb* immediately preceding a clearly named supported search site, and
    require all model-proposed query words to be independently present in the
    same utterance. No site or search-topic inference from the model itself.
    """
    if host not in ('youtube.com', 'google.com') or not isinstance(query, str):
        return False
    query_words = re.findall(r'[a-z0-9]+', query.casefold())
    if not query_words or len(query_words)>12:
        return False
    words = re.findall(r'[a-z0-9]+', text.casefold())
    # A near-spelled verb alone is not authority. The user's actual spoken
    # query must support the model-proposed destination AND the query topic.
    if not all(word in words for word in query_words):
        return False
    label=site_label(host)
    for index,word in enumerate(words[:-1]):
        if word != 'search' and 4 <= len(word) <= 8 and re.sub(r'[aeiouy]', '', word) == 'srch':
            if label in words[index+1:index+4]:
                return True
    return False


def trusted_intent(text: object, operation: str, host: str | None, value: object=None, query: object=None) -> bool:
    if not isinstance(text,str) or not (2 <= len(text) <= 2000) or operation not in ALLOWED:
        return False
    text=' '.join(text.split())
    safe=re.sub(r'\bappreciate\s+it\s+if\s+you\s+(?:could|would|can)\b',
                'appreciate it please', text, flags=re.I)
    if operation=='pause':
        safe=re.sub(r'(?<!\w)stop(?=\s+(?:the\s+)?(?:video|playback|player)\b)', 'pause', safe, flags=re.I)
    if any(pattern.search(safe) for pattern in (_NEGATED, _NON_REQUEST, _SECOND_ACTION)):
        return False
    if not _ACTIONS[operation].search(text):
        if not (operation=='search' and _phonetic_search_evidence(text,host,query)):
            return False
    # A single open-site effect must not silently satisfy one clause of a compound
    # request such as 'open Google and YouTube'. Search is a distinct operation.
    if operation in ('open','open_managed') and re.search(r'\b(?:open|launch|visit)\b.{0,100}\band\b', text, re.I):
        return False
    if operation == 'open':
        # Never silently change an explicitly requested managed-browser open
        # into a different OS-default-browser effect.
        if re.search(r"\b(?:in|using|with|through)\s+(?:(?:the|a)\s+)?(?:(?:your|jarvis(?:'s)?)\s+)?(?:managed|controlled|jarvis)\s+browser\b|\b(?:in|using|with|through)\s+(?:your|jarvis(?:'s)?)\s+browser\b", text, re.I):
            return False
    if operation == 'open_managed':
        # Cross-browser automation is not installed. A separate Jarvis-owned
        # tab is only allowed when the user explicitly asks for that surface.
        if not re.search(r"\b(?:in|using|with|through)\s+(?:(?:the|a)\s+)?(?:(?:your|jarvis(?:'s)?)\s+)?(?:managed|controlled|jarvis)\s+browser\b|\b(?:in|using|with|through)\s+(?:your|jarvis(?:'s)?)\s+browser\b", text, re.I):
            return False
    if operation == 'select_result':
        if host != 'current' or type(value) is not int or not 1 <= value <= 10: return False
        # Reject conflicting/multiple ordinals and model-invented indices.
        # The currently heard utterance, not previous page text, is authority.
        ordinal_words = {1:('first','1st'),2:('second','2nd'),3:('third','3rd'),
                         4:('fourth','4th'),5:('fifth','5th'),6:('sixth','6th'),
                         7:('seventh','7th'),8:('eighth','8th'),9:('ninth','9th'),
                         10:('tenth','10th')}
        spoken = set()
        tokens = re.findall(r'(?<!\w)(?:10|[1-9])(?!\w)', text)
        spoken.update(int(token) for token in tokens)
        for number, words in ordinal_words.items():
            if any(re.search(r'(?<!\w)'+re.escape(word)+r'(?!\w)',text,re.I) for word in words):
                spoken.add(number)
        if spoken != {value} or re.search(r'\b(?:and|then)\b',text,re.I): return False
        if not re.search(r'\b(?:video|result|one|it|that|this|clip|episode)\b',text,re.I): return False
        return True
    if operation in MEDIA:
        if host != 'current' or re.search(r'\b(?:and|then)\b',text,re.I): return False
        if operation in ('fullscreen','exit_fullscreen'):
            return bool(re.search(r'\bfull\s?screen\b|\bunfullscreen\b',text,re.I))
        # A media intent must be about playback, not a request to operate a named site.
        if not (re.search(r'\b(?:video|player|audio|sound|volume|music|playback|it|this|that)\b',text,re.I)
                or text.strip().lower().rstrip(' .!?') in {'play','pause','mute','unmute'}):
            return False
        if operation == 'volume':
            # Absolute percentage only. Never guess a relative change or choose
            # between multiple numbers mentioned in the same instruction.
            numerals=re.findall(r'(?<!\d)\d+(?!\d)',text)
            return (type(value) is int and 0 <= value <= 100 and
                    numerals == [str(value)] and not
                    re.search(r'\b(?:by|increase|decrease|raise|lower)\b',text,re.I))
        return True
    if operation in NAMED_TABS:
        if not host or host == 'current' or re.search(r'\b(?:and|then)\b',text,re.I): return False
        # Every named-tab operation targets the exact explicitly requested site.
        mentioned=[normalize_host(x.group(1)) for x in _EXPLICIT_HOST.finditer(text)]
        if any(x is None for x in mentioned): return False
        explicit=mentioned
        return (len(set(explicit)) == 1 and explicit[0] == host) if explicit else bool(
            re.search(r'(?<!\w)'+re.escape(site_label(host))+r'(?!\w)',text,re.I))
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
        if normalized is None:
            # A spoken malformed/spoofed hostname must not fall through to
            # matching a safe-looking registered-domain label.
            return False
        mentioned.append(normalized)
    if mentioned:
        return len(set(mentioned)) == 1 and mentioned[0] == host
    label=site_label(host)
    return bool(re.search(r'(?<!\w)'+re.escape(label)+r'(?!\w)', text, re.I))


def confirmed_site_search_query(transcript: object, site: object, query: object) -> bool:
    """Verify a model-supplied query for a current-turn, same-site search.

    For composite site-return requests we cannot infer a search from model
    parameters alone. Require independently transcribed search intent, one
    supported destination and the actual search subject in the utterance.
    The normal ManagedBrowserGateway subsequently performs its full authorization.
    """
    if not isinstance(transcript, str) or not isinstance(query, str) or not isinstance(site, str):
        return False
    host = normalize_host(site)
    if host not in ('youtube.com', 'google.com'):
        return False
    if len(query.strip()) < 2 or len(query.strip()) > 160:
        return False
    if not re.search(r'\b(?:search|find|look\s+up)\b', transcript, re.I):
        return False
    if not trusted_intent(transcript, 'search', host, query=query):
        return False
    # Composite return-and-search requests must not authorize a model-invented
    # query. Every distinctive search token must be in the verified utterance;
    # permit neutral 'video/videos' query fillers, but no new subject terms.
    utterance_tokens=set(re.findall(r'[a-z0-9]+', transcript.casefold()))
    query_tokens=re.findall(r'[a-z0-9]+', query.casefold())
    if not query_tokens or len(query_tokens)>24:
        return False
    ignored={'video','videos','a','an','the','about','for','of','on','in'}
    significant=[t for t in query_tokens if t not in ignored]
    return bool(significant) and all(token in utterance_tokens for token in significant)


class BrowserOperations(Protocol):
    async def navigate(self, url: str) -> bool: ...
    async def go_back(self) -> bool: ...
    async def go_forward(self) -> bool: ...
    async def reload(self) -> bool: ...
    async def close_tab(self) -> bool: ...
    async def next_tab(self) -> bool: ...
    async def select_tab(self, host: str) -> bool: ...
    async def close_named_tab(self, host: str) -> bool: ...
    async def media(self, operation: str, value: int | None=None) -> bool: ...
    async def select_result(self, index: int) -> bool: ...
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

    def _find_named_tab(self, host: str):
        if self._context is None: return None
        pages=[]
        for page in self._context.pages:
            if page.is_closed(): continue
            page_host=(urlsplit(page.url).hostname or '').lower().removeprefix('www.')
            if page_host == host: pages.append(page)
        # A named target must resolve unambiguously; never pick a random tab.
        return pages[0] if len(pages)==1 else None

    async def select_tab(self, host: str) -> bool:
        page=self._find_named_tab(host)
        if page is None: return False
        self._current=page
        await page.bring_to_front()
        return True

    async def close_named_tab(self, host: str) -> bool:
        page=self._find_named_tab(host)
        if page is None:return False
        await page.close()
        self._current=next((p for p in reversed(self._context.pages) if not p.is_closed()),None)
        if self._current is not None:await self._current.bring_to_front()
        return True

    async def media(self, operation: str, value: int | None=None) -> bool:
        if self._context is None: return False
        page=await self._page()
        if page.url=='about:blank': return False
        # Only HTML5 video elements; audited fixed function, never model JS.
        player=page.locator('video:visible').first
        if await player.count()==0: return False
        await page.bring_to_front()
        if operation=='play':
            return bool(await player.evaluate('async el => {try {await el.play(); return !el.paused;} catch {return false;}}'))
        if operation=='pause':
            return bool(await player.evaluate('el => {el.pause(); return el.paused;}'))
        if operation in ('mute','unmute'):
            return bool(await player.evaluate('(el, isMuted) => {el.muted=isMuted; return el.muted===isMuted;}',operation=='mute'))
        if operation=='volume' and type(value) is int and 0<=value<=100:
            return bool(await player.evaluate('(el, volume) => {el.volume=volume/100; return Math.abs(el.volume*100-volume)<0.1;}',value))
        return False

    async def close(self) -> None:
        try:
            if self._context is not None: await self._context.close()
        finally:
            self._context=None;self._current=None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright=None


def open_in_system_default(url: str) -> bool:
    """Hand off a validated HTTPS URL to the OS default browser.

    This reports OS acceptance only; it cannot confirm that the page loaded.
    Never pass model-authored arbitrary URLs here: gateway constructs the URL
    from the independently verified public registrable hostname.
    """
    if os.name == 'nt':
        os.startfile(url)  # Windows ShellExecute picks the user's registered handler.
        return True
    return webbrowser.open_new_tab(url) is True


class ManagedBrowserGateway:
    """Single-user, opt-in, transcript-bound browser authorization."""
    def __init__(self, browser: BrowserOperations | None = None, *, advanced: bool = False,
                 launch_default=None, bridge_mode: bool = False):
        self.browser=browser or PlaywrightManagedBrowser()
        self.bridge_mode=bridge_mode
        self.advanced=advanced
        self._launch_default=launch_default or open_in_system_default
        self._lock=asyncio.Lock()
        self._replays:dict[tuple[str,str],tuple[str,ToolResult]]={}

    async def execute(self, request:ToolRequest, *, evidence:ConfirmedUserAction|None) -> ToolResult:
        def outcome(status,code=None,message=None,output=None):
            return ToolResult(request.trace,request.tool_name,request.operation,status,output or {},
                              provider_call_id=request.provider_call_id,error_code=code,error_message=message)
        if request.tool_name!=CAPABILITY or request.operation not in ALLOWED or (self.bridge_mode and request.operation=='open_managed') or (not self.advanced and request.operation in (MEDIA|NAMED_TABS|{'open_managed','select_result'})):
            return outcome(ToolResultStatus.DENIED,'unknown_capability','That browser operation is not supported yet.')
        operation=request.operation
        arguments=dict(request.arguments)
        expected={'site','query'} if operation=='search' else {'site','value'} if operation in ('volume','select_result') else {'site'}
        if set(arguments)!=expected:return outcome(ToolResultStatus.DENIED,'invalid_arguments','Those browser parameters are not supported.')
        site=arguments['site']
        host=normalize_host(site) if operation in ({'open','open_managed','search'}|NAMED_TABS) else ('current' if site=='current' else None)
        if not host:return outcome(ToolResultStatus.DENIED,'unsafe_destination','I need a valid public website name to open.')
        query=arguments.get('query')
        value=arguments.get('value')
        if operation=='select_result' and (type(value) is not int or not 1<=value<=10 or not self.bridge_mode):
            return outcome(ToolResultStatus.DENIED,'invalid_result_selection',
                           'I need a numbered result in a connected browser to select.')
        if operation=='volume' and (type(value) is not int or not 0<=value<=100):
            return outcome(ToolResultStatus.DENIED,'invalid_volume','Please give a volume from 0 to 100 percent.')
        if operation=='search' and (not isinstance(query,str) or not 2<=len(query.strip())<=160
                                    or any(c in query for c in '\r\n\0') or host not in ('youtube.com','google.com')):
            return outcome(ToolResultStatus.DENIED,'unsupported_search','I can search YouTube or Google in this browser test.')
        if (evidence is None or not evidence.confirmed or not evidence.local_desktop or
                request.trace.turn_id!=evidence.turn_id or not request.trace.turn_id or
                not trusted_intent(evidence.transcript,operation,host,value,query)):
            return outcome(ToolResultStatus.DENIED,'unverified_user_intent',
                           'I could not verify that immediate browser request, so I did not act.')
        replay=(evidence.turn_id,request.idempotency_key or request.trace.request_id)
        fingerprint=repr((operation,host,query,value))
        async with self._lock:
            previous=self._replays.get(replay)
            if previous:
                if previous[0]!=fingerprint:return outcome(ToolResultStatus.DENIED,'replay_key_conflict')
                return previous[1]
            if operation=='search':
                uri=('https://www.youtube.com/results?search_query=' if host=='youtube.com'
                     else 'https://www.google.com/search?q=')+quote_plus(query.strip())
            else:
                uri=(f'https://{host}/' if self.advanced and operation=='open'
                     else f'https://www.{host}/') if operation in ('open','open_managed') else ''
            try:
                async def act():
                    if operation in ('open','search') and self.bridge_mode:
                        # A connected extension may reuse an existing matching tab;
                        # otherwise the adapter asks Windows to open in its default.
                        return await self.browser.navigate(uri)
                    if operation in ('open','search') and self.advanced:
                        # Do not start/reuse the separate Playwright browser for
                        # ordinary opens. The user chooses their system default.
                        return await asyncio.to_thread(self._launch_default, uri)
                    if operation in ('open','open_managed','search'):return await self.browser.navigate(uri)
                    if operation=='select_result':return await self.browser.select_result(value)
                    if operation=='select_tab':return await self.browser.select_tab(host)
                    if operation=='close_named_tab':return await self.browser.close_named_tab(host)
                    if operation in MEDIA:return await self.browser.media(operation,value)
                    return await getattr(self.browser,{'back':'go_back','forward':'go_forward',
                         'reload':'reload','close_tab':'close_tab','next_tab':'next_tab'}[operation])()
                success=await asyncio.wait_for(act(),timeout=7.0)
                if self.bridge_mode and operation in ('open', 'search', 'select_result'):
                    # No transcript, query text, URL or browser-history content
                    # in diagnostics: only the navigation route and connection.
                    route=getattr(self.browser,'last_navigation_route','unknown')
                    print(f'[Jarvis Browser Route] operation={operation} | route={route} | accepted={bool(success)}', flush=True)
                result=(outcome(ToolResultStatus.SUCCEEDED,output={
                    'navigation_route':getattr(self.browser,'last_navigation_route','unknown') if self.bridge_mode else 'not_applicable',
                    'operation':operation,'browser_navigation_committed':success if (operation in ('open','search') and not self.advanced) or operation == 'open_managed' else False,
                    'system_browser_handoff_accepted':bool(success and self.advanced and operation in ('open','search') and (not self.bridge_mode or getattr(self.browser,'last_system_handoff',False))),
                    'page_loaded_verified':bool(success and self.bridge_mode and getattr(self.browser,'last_navigation_verified',False)),'url':uri if uri else None,
                    'user_message':('I opened the selected video in your existing tab.' if operation=='select_result' else 'I completed that media control.' if operation in MEDIA else 'I opened that page in your browser.' if self.bridge_mode and getattr(self.browser,'last_navigation_verified',False) else 'I sent the website to your default browser.') if self.advanced and operation in ('open','search') else 'I completed the browser action.'})
                    if success else outcome(ToolResultStatus.FAILED,'not_available',
                                            ('The default browser did not accept that website request.' if self.advanced and operation in ('open','search')
                                             else 'I could not find or verify that numbered video on the current YouTube search page.' if operation == 'select_result'
                                             else 'I need the Jarvis browser extension connected to control that video.' if self.bridge_mode and operation in MEDIA
                                             else 'I can only control video inside Jarvis managed browser right now.' if operation in MEDIA
                                             else 'I need the Jarvis browser extension connected to control that tab.' if self.bridge_mode and (operation in NAMED_TABS or operation in ('close_tab','next_tab','back','forward','reload'))
                                             else 'I can only control tabs inside Jarvis managed browser right now.' if operation in NAMED_TABS or operation in ('close_tab','next_tab','back','forward','reload')
                                             else 'I could not find a matching tab or supported video player for that request.')))
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
