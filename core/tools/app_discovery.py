"""Windows application inventory, never a model-controlled executable launcher.

Derived from the *approach* in V1 jarvis/computer/apps.py (quick Start Menu /
App Paths sources, exact-name precedence, duplicate routes), deliberately not
from its broad filesystem scans or arbitrary command execution machinery.

Inventory is built on a daemon thread independently of Realtime turns.
Start Menu, registered App Paths, and Windows Start apps (including packaged
MSIX/UWP apps) are discoverable. This is deliberately NOT an exhaustive
all-drive search, arbitrary executable scanner, or unrestricted launcher.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import json
import os
import subprocess
from pathlib import Path
import re
import threading
import time
from typing import Callable, Iterable

_BAD = re.compile(r'\b(?:uninstall|uninstaller|setup|installer|update|updater|repair|crash|reporter|helper|telemetry|diagnostic|bootstrap|remove)\b', re.I)
_NORMAL = re.compile(r'[^a-z0-9]+')
_VENDOR = ('microsoft ', 'google ', 'mozilla ', 'adobe ', 'apple ', 'nvidia ')
# Bare names like 'Windows' or 'Help' are not specific enough for remote-model execution.
_TOO_GENERIC = frozenset({'app', 'application', 'program', 'settings', 'help', 'windows', 'browser'})


def normalize(value: str) -> str:
    return ' '.join(_NORMAL.sub(' ', value.casefold().replace('&', ' and ')).split())


def aliases(name: str) -> frozenset[str]:
    base = normalize(name)
    result = {base}
    for prefix in _VENDOR:
        if base.startswith(prefix):
            result.add(base[len(prefix):])
    # Generic trailing descriptors are not app-specific mappings.
    # For example, Windows can register 'Spotify Music' as its Start display
    # name while the user naturally says 'Spotify'. Collisions stay ambiguous.
    for suffix in (' music', ' desktop'):
        if base.endswith(suffix):
            result.add(base[:-len(suffix)])
    if base.endswith(' app'):
        result.add(base[:-4])
    if base.endswith(' application'):
        result.add(base[:-12])
    return frozenset(a for a in result if len(a) >= 3 and a not in _TOO_GENERIC)


@dataclass(frozen=True)
class InstalledApp:
    name: str
    kind: str  # shortcut, executable, system
    target: str  # locally enumerated; never supplied to the model
    source: str

    @property
    def names(self) -> frozenset[str]:
        return aliases(self.name)


def _system_apps() -> list[InstalledApp]:
    # Stable fallback names. The system executable is resolved inside the
    # Windows system directory when actually launched, NOT through PATH.
    return [InstalledApp('Notepad', 'system', 'notepad.exe', 'system'),
            InstalledApp('Calculator', 'system', 'calc.exe', 'system'),
            InstalledApp('File Explorer', 'system', 'explorer.exe', 'system')]


def discover_windows_apps(*, roots: Iterable[Path] | None = None,
                          registry: Callable[[], Iterable[InstalledApp]] | None = None,
                          start_apps: Callable[[], Iterable[InstalledApp]] | None = None,
                          include_system: bool = True) -> list[InstalledApp]:
    """Bounded OS-registered discovery, with injectable sources for tests.

    A real Windows scan also includes Get-StartApps (MSIX/Store identities).
    Injected roots never implicitly invoke host OS discovery in test runs.
    """
    native_scan = roots is None
    if roots is None:
        if os.name != 'nt':
            return _system_apps() if include_system else []
        roots = (Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) / 'Microsoft/Windows/Start Menu/Programs',
                 Path(os.environ.get('APPDATA', '')) / 'Microsoft/Windows/Start Menu/Programs')
    if registry is None:
        registry = _read_app_paths if os.name == 'nt' and native_scan else lambda: ()
    if start_apps is None:
        start_apps = _read_start_apps if os.name == 'nt' and native_scan else lambda: ()
    found: list[InstalledApp] = _system_apps() if include_system else []
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        # Start Menu is a bounded, known source; avoid following symlink dirs.
        for current, dirs, files in os.walk(root, followlinks=False):
            depth = len(Path(current).relative_to(root).parts)
            if depth >= 5:
                dirs[:] = []
            else:
                dirs[:] = [d for d in dirs if not (Path(current)/d).is_symlink()]
            for filename in files:
                if not filename.lower().endswith(('.lnk', '.appref-ms')):
                    continue
                name = Path(filename).stem
                if not name or _BAD.search(name) or not aliases(name):
                    continue
                file_path = Path(current)/filename
                if file_path.is_symlink():
                    continue
                found.append(InstalledApp(name, 'shortcut', str(file_path), 'start_menu'))
    try:
        for item in registry():
            if (isinstance(item, InstalledApp) and item.kind == 'executable'
                    and item.target.lower().endswith('.exe') and not _BAD.search(item.name)
                    and aliases(item.name)):
                found.append(item)
    except OSError:
        pass
    try:
        for item in start_apps():
            if (isinstance(item, InstalledApp) and item.kind == 'aumid'
                    and item.source == 'start_apps'
                    and valid_aumid(item.target) and aliases(item.name)
                    and not _BAD.search(item.name)):
                found.append(item)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        pass
    # Prefer OS launch routes over less authoritative fallbacks.
    priority = {'start_menu': 0, 'system': 1, 'app_paths': 2, 'start_apps': 3}
    by_route: dict[tuple[str, str], InstalledApp] = {}
    for item in found:
        by_route.setdefault((item.kind, item.target.casefold()), item)
    return sorted(by_route.values(), key=lambda a: (priority.get(a.source, 4), normalize(a.name), a.target.casefold()))


def _read_app_paths() -> Iterable[InstalledApp]:
    """Read Windows registered App Paths. No registry-supplied arguments."""
    try:
        import winreg
    except ImportError:
        return []
    results: list[InstalledApp] = []
    subkey = r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths'
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, subkey) as parent:
                count = winreg.QueryInfoKey(parent)[0]
                for i in range(min(count, 5000)):
                    key = winreg.EnumKey(parent, i)
                    if not key.lower().endswith('.exe') or _BAD.search(key):
                        continue
                    try:
                        with winreg.OpenKey(parent, key) as entry:
                            path = winreg.QueryValueEx(entry, '')[0]
                    except OSError:
                        continue
                    if (not isinstance(path, str) or '"' in path or '\x00' in path
                            or not Path(path).is_absolute() or not Path(path).is_file()
                            or Path(path).suffix.lower() != '.exe'):
                        continue
                    results.append(InstalledApp(Path(key).stem, 'executable', path, 'app_paths'))
        except OSError:
            continue
    return results


# Start apps are enumerated by the OS itself, including Microsoft Store/MSIX
# registrations which do not have a normal executable in App Paths. AUMIDs are
# identities, not executable commands. Still validate to avoid shell metacharacters
# even though the source is OS enumeration and never user/model-supplied.
_AUMID = re.compile(r'[A-Za-z0-9_.!\\{}-]{3,220}\Z')


def valid_aumid(value: object) -> bool:
    return (isinstance(value, str) and _AUMID.fullmatch(value) is not None
            and not value.startswith(('\\', '.', '-')) and '..' not in value)


def _windows_directory() -> Path | None:
    if os.name != 'nt':
        return None
    try:
        import ctypes
        from ctypes import wintypes
        func = ctypes.WinDLL('kernel32', use_last_error=True).GetWindowsDirectoryW
        func.argtypes = [wintypes.LPWSTR, wintypes.UINT]
        func.restype = wintypes.UINT
        buffer = ctypes.create_unicode_buffer(32768)
        size = func(buffer, len(buffer))
        return Path(buffer.value) if 0 < size < len(buffer) else None
    except (OSError, AttributeError, ValueError):
        return None


def _read_start_apps() -> Iterable[InstalledApp]:
    """Read registered Windows Start apps via a fixed, bounded OS query.

    Executes no discovered command and accepts no input from the model/user.
    PowerShell is used for discovery only; failure keeps existing routes alive.
    """
    if os.name != 'nt':
        return []
    windows = _windows_directory()
    powershell = windows/'System32/WindowsPowerShell/v1.0/powershell.exe' if windows else None
    if powershell is None or not powershell.is_file():
        return []
    command = ('[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; '
               'Get-StartApps | Select-Object -Property Name,AppID | ConvertTo-Json -Compress')
    try:
        completed = subprocess.run(
            [str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', command],
            capture_output=True, timeout=12, check=False,
            encoding='utf-8', errors='replace',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0 or len(completed.stdout) > 2_000_000:
        return []
    try:
        rows = json.loads(completed.stdout)
    except (ValueError, TypeError):
        return []
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        return []
    result: list[InstalledApp] = []
    for row in rows[:6000]:
        if not isinstance(row, dict):
            continue
        name, app_id = row.get('Name'), row.get('AppID')
        if (isinstance(name, str) and 1 <= len(name) <= 120
                and aliases(name) and not _BAD.search(name) and valid_aumid(app_id)):
            result.append(InstalledApp(name, 'aumid', app_id, 'start_apps'))
    return result


class InstalledAppInventory:
    def __init__(self, *, discover: Callable[[], list[InstalledApp]] = discover_windows_apps,
                 auto_start: bool = True, refresh_seconds: int = 300):
        self._discover = discover
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._items: list[InstalledApp] = _system_apps()
        self._expires = 0.0
        self._refresh_seconds = refresh_seconds
        self._running = False
        if auto_start:
            self.refresh_async()

    def refresh_async(self) -> None:
        with self._lock:
            if self._running or time.monotonic() < self._expires:
                return
            self._running = True
        threading.Thread(target=self._refresh, daemon=True, name='jarvis-app-inventory').start()

    def _refresh(self) -> None:
        try:
            items = self._discover()
            with self._lock:
                self._items = items
                self._expires = time.monotonic() + self._refresh_seconds
        except Exception:
            # Fail closed to known system apps. Don't block voice startup.
            with self._lock:
                self._expires = time.monotonic() + 30
        finally:
            with self._lock:
                self._running = False
            self._ready.set()

    def candidates(self) -> list[InstalledApp]:
        self.refresh_async()
        with self._lock:
            return list(self._items)

    def resolve(self, name: str) -> tuple[InstalledApp | None, str]:
        """Only accept unique, credible installed identities; never a path.

        Exact aliases take precedence. Approximate names must be strong and
        non-ambiguous, otherwise the system asks for clarification instead.
        """
        if not isinstance(name, str) or len(name) > 120:
            return None, 'invalid_application'
        key = normalize(name)
        if len(key) < 3 or key in _TOO_GENERIC or '/' in name or '\\' in name or ':' in name:
            return None, 'invalid_application'
        items = self.candidates()
        # An initial Windows registration query can take several seconds.
        # Do not misreport a non-builtin app as absent while discovery runs.
        inventory_warming = not self._ready.is_set()
        direct = [x for x in items if key in x.names]
        if direct:
            return _choose(direct)
        scored = sorted(((max((SequenceMatcher(None, key, a).ratio() for a in x.names), default=0), x)
                         for x in items), key=lambda v: v[0], reverse=True)
        if len(key) < 5 or not scored or scored[0][0] < 0.9:
            return None, 'inventory_warming' if inventory_warming else 'app_not_found'
        # A misspelling cannot silently choose between two distinct near-matches.
        top = [item for score, item in scored if score >= scored[0][0] - 0.04]
        return _choose(top)


def _choose(candidates: list[InstalledApp]) -> tuple[InstalledApp | None, str]:
    # Identically named shortcuts can represent different apps. Distinct target
    # names across sources can only merge if exactly the same normalized name.
    groups: dict[str, list[InstalledApp]] = {}
    for item in candidates:
        groups.setdefault(normalize(item.name), []).append(item)
    if len(groups) > 1:
        # "Chrome" and "Google Chrome" canonicalize if only one is a vendor
        # suffix and the other isn't an unrelated program.
        canonical = {next(iter(sorted(aliases(k), key=len))) for k in groups}
        if len(canonical) != 1:
            return None, 'app_ambiguous'
    # Multiple routes carrying the exact same installed display identity are
    # not multiple different apps (e.g. Discord user shortcut, machine shortcut,
    # and Windows Start app). Do not confuse routes with user-facing variants.
    # Prefer user Start Menu shortcuts; they generally point to the current
    # user's active installation, before machine-wide and packaged fallbacks.
    appdata = os.environ.get('APPDATA', '').casefold().rstrip('\\/')
    def route_rank(item: InstalledApp) -> tuple[int, str]:
        target = item.target.casefold()
        if item.source == 'start_menu' and appdata and target.startswith(appdata + os.sep.casefold()):
            return (0, target)
        return ({'start_menu': 1, 'system': 2, 'app_paths': 3,
                 'start_apps': 4}.get(item.source, 5), target)
    ordered = sorted(candidates, key=route_rank)
    return ordered[0], 'resolved'
