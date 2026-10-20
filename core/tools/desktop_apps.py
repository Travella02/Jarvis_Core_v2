"""Core-owned dynamic Windows application launch authorization (0.1.5.8).

Mini proposes an installed app *name*, never a command or path. Core independently
matches the confirmed same-turn words to the OS-discovered app, then asks Windows
for a launch. This is not full desktop computer-use and it does not prove that a
window became visible. Browser tools and ordinary speech remain separate.
"""
from __future__ import annotations

import asyncio
import os
import re
import time
from pathlib import Path
from typing import Callable

from core.tools import ToolRequest, ToolResult, ToolResultStatus
from core.tools.gateway import ConfirmedUserAction
from core.tools.semantic_browser import _NEGATED, _NON_REQUEST, _SECOND_ACTION
from core.tools.app_discovery import InstalledApp, InstalledAppInventory, normalize, _system_apps, valid_aumid
from core.tools.app_launch_history import AppLaunchHistory

APP_TOOL = 'desktop_app'
APP_OPERATION = 'launch'
# Compatibility with 0.1.5.7 tests and the built-in fallback; discovery is NOT
# restricted to these names. V1's route-selection lesson was kept, not its wide
# filesystem execution capability.
APP_CATALOG = {
    'notepad': ('Notepad', 'notepad.exe', (r'\bnotepad\b',)),
    'calculator': ('Calculator', 'calc.exe', (r'\bcalculator\b', r'\bcalc\s+app\b')),
    'file_explorer': ('File Explorer', 'explorer.exe', (r'\bfile\s+explorer\b', r'\bwindows\s+explorer\b')),
}
_ACTION = re.compile(r'\b(?:open|launch|start|bring\s+up|pull\s+up|fire\s+up|show\s+me|run)\b', re.I)
_MULTI = re.compile(r'\b(?:and\s+then|then\s+(?:open|launch|start|close)|and\s+(?:open|launch|start|close|delete|send|email|search|download))\b', re.I)
_QUOTED = re.compile(r'["“”]|\b(?:quote|quoted|hypothetical|imagine|pretend|example|if\s+you|if\s+i)\b', re.I)
_EXPLICIT_WEB = re.compile(r'\b(?:web\s*site|website|web\s*page|url|link|in\s+(?:the\s+)?browser|in\s+(?:chrome|edge|firefox)|online)\b', re.I)
_HOST = re.compile(r'\b[a-z0-9-]+\.(?:com|net|org|io|app|gov|edu)\b', re.I)


def _authorized_app(text: object, app: InstalledApp, candidates: list[InstalledApp]) -> bool:
    """Veto unsafe/non-immediate requests; do not act as the intent model."""
    if not isinstance(text, str) or not (1 <= len(text) <= 2000):
        return False
    clean = ' '.join(text.split())
    verb = _ACTION.search(clean)
    if (not verb or _NEGATED.search(clean) or _NON_REQUEST.search(clean)
            or _SECOND_ACTION.search(clean) or _MULTI.search(clean)
            or _QUOTED.search(clean) or _EXPLICIT_WEB.search(clean)
            or '://' in clean or 'www.' in clean or _HOST.search(clean)):
        return False
    if re.search(r'\b(?:how|why|what|search|look\s+up|explain|describe|learn)\b', clean[:verb.start()], re.I):
        return False
    # Protect against hallucinated model targets: the actual installed app's
    # name/alias MUST appear in the confirmed transcript AFTER the action verb.
    spoken = ' ' + normalize(clean[verb.end():]) + ' '
    spoken = re.sub(r'\b(?:windows\s+explorer)\b', 'file explorer', spoken)
    if not any((' ' + alias + ' ') in spoken for alias in app.names):
        return False
    # Core won't partially execute multi-app utterances as a single launch,
    # even if Mini proposed only one of the requested apps.
    for other in candidates:
        if other == app or normalize(other.name) == normalize(app.name):
            continue
        for alias in other.names:
            if alias not in app.names and (' ' + alias + ' ') in spoken:
                return False
    return True


def _windows_dir(which: str) -> Path | None:
    """Use Windows APIs, not untrusted environment variables or PATH."""
    import ctypes
    from ctypes import wintypes
    fn = getattr(ctypes.WinDLL('kernel32', use_last_error=True), which)
    fn.argtypes = [wintypes.LPWSTR, wintypes.UINT]
    fn.restype = wintypes.UINT
    buffer = ctypes.create_unicode_buffer(32768)
    count = fn(buffer, len(buffer))
    return Path(buffer.value) if 0 < count < len(buffer) else None


def launch_windows_installed_app(app: InstalledApp) -> bool:
    """Launch solely an OS-enumerated route; no model-supplied path or args."""
    if os.name != 'nt' or not isinstance(app, InstalledApp):
        return False
    if app.kind == 'system':
        folder = _windows_dir('GetWindowsDirectoryW' if app.target == 'explorer.exe' else 'GetSystemDirectoryW')
        if folder is None or app.target not in {'notepad.exe', 'calc.exe', 'explorer.exe'}:
            return False
        exe = folder / app.target
    elif app.kind == 'aumid' and app.source == 'start_apps':
        if not valid_aumid(app.target):
            return False
        windows = _windows_dir('GetWindowsDirectoryW')
        if windows is None or not (windows/'explorer.exe').is_file():
            return False
        # Explorer asks the Windows shell to launch an OS-registered AppsFolder
        # identity. AppID is selected from the inventory, never model-supplied.
        os.startfile(str(windows/'explorer.exe'), arguments='shell:AppsFolder\\' + app.target)
        return True
    elif app.kind == 'shortcut' and app.source == 'start_menu':
        exe = Path(app.target)
        if exe.suffix.lower() not in {'.lnk', '.appref-ms'}:
            return False
        # Revalidate original Start Menu provenance before shell handoff.
        roots = [Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData'))/'Microsoft/Windows/Start Menu/Programs',
                 Path(os.environ.get('APPDATA', ''))/'Microsoft/Windows/Start Menu/Programs']
        if not any(exe.resolve().is_relative_to(root.resolve()) for root in roots if root.is_dir()):
            return False
    elif app.kind == 'executable' and app.source == 'app_paths':
        exe = Path(app.target)
        if not exe.is_absolute() or exe.suffix.lower() != '.exe':
            return False
    else:
        return False
    if not exe.is_file():
        return False
    os.startfile(str(exe))
    return True


def launch_windows_system_app(app_id: str) -> bool:
    """Compatibility entry point used by 0.1.5.7; not a path-based launcher."""
    inventory = InstalledAppInventory(auto_start=False)
    app, _ = inventory.resolve(app_id.replace('_', ' '))
    return launch_windows_installed_app(app) if app is not None else False


class CoreDesktopAppGateway:
    def __init__(self, *, launcher: Callable[[str], bool] | None = None,
                 inventory: InstalledAppInventory | None = None, dynamic: bool = False,
                 history: AppLaunchHistory | None = None) -> None:
        # The injected string launcher supports inert tests; production receives
        # only a validated InstalledApp instance with an OS-enumerated target.
        self._launch = launcher
        self.dynamic = dynamic
        self.inventory = inventory or (InstalledAppInventory() if dynamic else InstalledAppInventory(
            discover=_system_apps, auto_start=False))
        # Production persists accepted launch routes locally; inert injected
        # test launchers remain side-effect free unless history is explicit.
        self.history = history if history is not None else (
            AppLaunchHistory() if dynamic and launcher is None else None)
        self._lock = asyncio.Lock()
        self._replays: dict[tuple[str, str], tuple[str, ToolResult]] = {}

    async def execute(self, request: ToolRequest, *, evidence: ConfirmedUserAction | None) -> ToolResult:
        def result(status: ToolResultStatus, code: str | None = None, detail: str | None = None,
                   output: dict | None = None) -> ToolResult:
            return ToolResult(request.trace, request.tool_name, request.operation, status,
                              output or {}, provider_call_id=request.provider_call_id,
                              error_code=code, error_message=detail)
        if request.tool_name != APP_TOOL or request.operation != APP_OPERATION:
            return result(ToolResultStatus.DENIED, 'unknown_capability')
        app_name = request.arguments.get('app')
        if set(request.arguments) != {'app'} or not isinstance(app_name, str):
            return result(ToolResultStatus.DENIED, 'invalid_application')
        # Recognize the old stable API ids (e.g. file_explorer) as names, but
        # dynamic apps require absolutely no per-app code or enum.
        if not self.dynamic and app_name not in APP_CATALOG:
            return result(ToolResultStatus.DENIED, 'unapproved_application',
                          'That application is not supported in the baseline mode.')
        match_name = APP_CATALOG[app_name][0] if app_name in APP_CATALOG else app_name
        app, resolution = self.inventory.resolve(match_name)
        if app is None:
            detail = ('I found multiple matching applications. Please use a more specific app name.'
                      if resolution == 'app_ambiguous' else
                      'I am still checking your installed apps. Please try again in a moment.'
                      if resolution == 'inventory_warming' else
                      f"I couldn't find an installed app named {app_name} on this computer.")
            return result(ToolResultStatus.DENIED, resolution, detail)
        if (evidence is None or not evidence.confirmed or not evidence.local_desktop
                or not request.trace.turn_id or evidence.turn_id != request.trace.turn_id
                or not _authorized_app(evidence.transcript, app, self.inventory.candidates())):
            return result(ToolResultStatus.DENIED, 'unverified_user_intent',
                          'I could not verify an immediate request for that application, so I did not open it.')
        key = (evidence.turn_id, request.idempotency_key or request.trace.request_id)
        fingerprint = f'{APP_TOOL}/{APP_OPERATION}/{normalize(app.name)}'
        async with self._lock:
            existing = self._replays.get(key)
            if existing:
                return existing[1] if existing[0] == fingerprint else result(ToolResultStatus.DENIED, 'replay_key_conflict')
            # IMPORTANT: Authorization above occurs ONCE, before considering
            # any alternative launch registrations or persisted preferences.
            # Only use routes for exactly the same resolved display identity.
            routes = [app]
            if self.dynamic:
                routes.extend(candidate for candidate in self.inventory.candidates()
                              if normalize(candidate.name) == normalize(app.name)
                              and not (candidate.kind == app.kind and candidate.source == app.source
                                       and candidate.target.casefold() == app.target.casefold()))
            if self.history is not None:
                preferred = self.history.preferred(app.name, routes)
                if preferred is not None:
                    routes = [preferred] + [route for route in routes if route != preferred]
            unique_routes: list[InstalledApp] = []
            seen: set[tuple[str, str, str]] = set()
            for route in routes:
                identity = (route.kind, route.source, route.target.casefold())
                if identity not in seen:
                    seen.add(identity)
                    unique_routes.append(route)
            # The budget is best-effort: a synchronous Windows shell call may
            # itself stall, but we must not detach a late launch in a thread.
            deadline = time.monotonic() + 8.0
            accepted = False
            attempts = 0
            for route in unique_routes[:3]:
                if attempts and time.monotonic() >= deadline:
                    break
                attempts += 1
                try:
                    # Injected test launcher uses display names, not paths.
                    accepted = (self._launch(app_name) if self._launch else
                                launch_windows_installed_app(route)) is True
                except Exception:
                    accepted = False
                if self.history is not None:
                    self.history.record(route, accepted=accepted)
                if accepted:
                    break  # OS accepted a handoff; retry could open duplicates.
            if accepted:
                outcome = result(ToolResultStatus.SUCCEEDED, output={
                    'app': app.name, 'app_label': app.name,
                    'launch_handoff_accepted': True, 'window_visible_verified': False,
                    'user_message': f'I asked Windows to open {app.name}.',
                })
            else:
                outcome = result(ToolResultStatus.FAILED, 'app_launch_unavailable',
                                 f"I tried the available ways to open {app.name}, but Windows didn't accept the launch.")
            self._replays[key] = (fingerprint, outcome)
            return outcome
