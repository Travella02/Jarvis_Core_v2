"""Isolated *headless* browser for opt-in Terra tasks.

Never controls a user's browser profile, focused app, physical cursor or keys.
Creates a fresh disposable context for each task; no cookies persist.
Playwright is an OPTIONAL dependency, downloaded browser installed separately.
"""
from __future__ import annotations
from urllib.parse import urlsplit
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
