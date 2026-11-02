"""Isolated *headless* browser for opt-in Terra tasks.

Never controls a user's browser profile, focused app, physical cursor or keys.
An isolated in-memory session may be reused on one dedicated worker thread.
Never uses a normal browser profile; session state is discarded on close.
Playwright is an OPTIONAL dependency, downloaded browser installed separately.
"""
from __future__ import annotations
from urllib.parse import urlsplit, urljoin
import re
from .terra_navigation import WindowIdentity


def approved_background_url(value: str, hosts: str) -> str | None:
    try:
        uri=urlsplit(value)
        allowed={h.strip().lower() for h in hosts.split(',') if h.strip()}
        if (uri.scheme!='https' or not uri.hostname or uri.username or uri.password
                or uri.port not in (None,443) or uri.hostname.lower() not in allowed
                or uri.fragment or len(value)>600 or not allowed):return None
        return value
    except ValueError:return None

def compact_page_observation_for_speech(observation: str, *, limit: int = 235) -> str:
    """Short, fact-bound speech from a verified read-only page observation.

    The full bounded DOM observation remains available to Core in the caller;
    do not send raw multilingual page dumps to the TTS response. No model
    interpretation and no navigation or new permissions occur here.
    """
    if not isinstance(observation, str):
        return 'I could not summarize the inspected background page.'
    prefix = 'Isolated browser at '
    marker = '. Page title: '
    text_marker = '. Visible page text: '
    if not observation.startswith(prefix) or marker not in observation or text_marker not in observation:
        return observation[:limit].strip()
    left, _, body = observation.partition(text_marker)
    host_text, _, page_title = left.partition(marker)
    host = host_text[len(prefix):].strip()[:100]
    title = page_title.strip()[:90]
    body = body.rsplit('. No action was taken.', 1)[0].strip()
    # This is a compact *extract*, not a claim that every page was understood.
    # Select the first substantive sentence; avoid dumping subsequent languages.
    sentences = [piece.strip() for piece in re.split(r'(?<=[.!?。！？])\s+', body) if piece.strip()]
    excerpt = next((s for s in sentences if s.casefold().rstrip('.!') != title.casefold().rstrip('.!')), '')
    if len(excerpt) > 125:
        excerpt = excerpt[:125].rsplit(' ', 1)[0].rstrip(' ,;:') + '…'
    result = f'I inspected the background browser at {host}. Page: {title or "untitled"}.'
    if excerpt:
        result += f' It says: {excerpt}'
    return result[:limit].strip()


class IsolatedBrowserDriver:
    """All operations are Playwright page-local; no OS-level input injection."""
    def __init__(self,url:str,hosts:str,*,factory=None):
        if not approved_background_url(url,hosts):raise ValueError('background_url_not_approved')
        self.url=url;self.hosts=hosts;self.factory=factory
        self.pw=None;self.browser=None;self.context=None;self.page=None
        self.window=WindowIdentity(-1,'isolated-browser.exe','Isolated browser task',(0,0,1280,800))

    def __enter__(self):
        if self.factory is None:
            from playwright.sync_api import sync_playwright
            self.pw=sync_playwright().start()
            self.factory=self.pw.chromium
        try:
            self.browser=self.factory.launch(headless=True)
            self.context=self.browser.new_context(viewport={'width':1280,'height':800},accept_downloads=False)
            self.page=self.context.new_page()
            self.page.on('dialog',lambda dialog:dialog.dismiss())
            self.page.goto(self.url,wait_until='domcontentloaded',timeout=15000)
            self._check_origin()
            return self
        except Exception:
            self.__exit__(None,None,None)
            raise

    def __exit__(self,*_):
        for thing in ('context','browser','pw'):
            obj=getattr(self,thing,None)
            if obj is not None:
                try:obj.close() if thing != 'pw' else obj.stop()
                except Exception:pass
                setattr(self,thing,None)
        self.page=None

    def resolve_safe_link(self, label: str) -> str:
        """Read-only link check: exact accessible text + safe same-host HTTPS.

        Mutating actions and arbitrary element clicks never use this shortcut.
        """
        self._check_origin()
        links=self.page.get_by_role('link', name=re.compile('^'+re.escape(label)+'$', re.I))
        if links.count()!=1:
            raise ValueError('ambiguous_link')
        href=links.first.get_attribute('href')
        if not href:
            raise ValueError('link_no_href')
        url=urljoin(self.page.url,href)
        parsed=urlsplit(url)
        origin=urlsplit(self.page.url)
        if (not approved_background_url(url,self.hosts) or parsed.hostname!=origin.hostname
                or parsed.query or parsed.fragment or not parsed.path.startswith('/')
                or re.search(r'(?i)(?:^|[-_/])(delete|remove|logout|logoff|checkout|purchase|pay|submit|install|download)(?:$|[-_/])',parsed.path)):
            raise ValueError('unsafe_link')
        self._check_origin()
        return url

    def open_verified_link(self,url:str) -> None:
        self._check_origin()
        # Recheck the candidate destination immediately before navigation.
        if urlsplit(url).hostname!=urlsplit(self.page.url).hostname or not approved_background_url(url,self.hosts):
            raise ValueError('unsafe_link')
        self.page.goto(url,wait_until='domcontentloaded',timeout=10000)
        self._check_origin()

    def read_page_summary(self, *, max_chars: int = 650) -> str:
        """Bounded read-only DOM observation; no model call or physical input."""
        self._check_origin()
        host = urlsplit(self.page.url).hostname or ''
        title = re.sub(r'\s+', ' ', str(self.page.title() or '')).strip()[:160]
        body = self.page.locator('body').inner_text(timeout=2500)
        text = re.sub(r'\s+', ' ', str(body or '')).strip()[:max_chars]
        self._check_origin()
        return f'Isolated browser at {host}. Page title: {title or "(untitled)"}. Visible page text: {text or "(none)"}. No action was taken.'

    def _check_origin(self):
        if not self.page or not approved_background_url(self.page.url,self.hosts):
            raise RuntimeError('background_origin_changed')
        if self.context and len(self.context.pages)!=1:
            raise RuntimeError('background_popup_blocked')

    def identity(self):
        self._check_origin()
        return self.window

    def screenshot(self,window):
        self._check_origin()
        return self.page.screenshot(type='png',full_page=False,animations='disabled',timeout=5000)

    def perform(self,action,window):
        self._check_origin()
        kind=action['type']
        if kind in ('click','double_click'):
            self.page.mouse.click(action['x'],action['y'],click_count=2 if kind=='double_click' else 1)
        elif kind=='scroll':
            self.page.mouse.move(action['x'],action['y'])
            self.page.mouse.wheel(0,action['scroll_y'])
        elif kind=='keypress':
            keys={'esc':'Escape','escape':'Escape','up':'ArrowUp','down':'ArrowDown',
                  'left':'ArrowLeft','right':'ArrowRight','pageup':'PageUp','pagedown':'PageDown',
                  'enter':'Enter','space':'Space','tab':'Tab','ctrl':'Control'}
            self.page.keyboard.press('+'.join(keys.get(x,x.title()) for x in action['keys']))
        elif kind=='type':self.page.keyboard.type(action['text'],delay=0)
        elif kind=='screenshot':pass
        else:raise ValueError('Unsupported action')
        self._check_origin()
