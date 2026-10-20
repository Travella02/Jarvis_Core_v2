"""Local, bounded OS-verified application launch handoff history.

The history is *advisory*: a stored path is NEVER a launch capability. A caller
may prefer it only after matching the exact route against its current trusted
OS-discovered inventory. Handoff acceptance is not proof that a window opened.

No user transcripts, browsing history, command arguments, or credentials stored.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Sequence

from core.tools.app_discovery import InstalledApp, normalize

_MAX_EVENTS = 120
_MAX_PREFERENCES = 128
_MAX_READ_BYTES = 150_000


def default_history_path() -> Path:
    base = os.environ.get('LOCALAPPDATA') if os.name == 'nt' else None
    if not base:
        base = str(Path.home() / '.local' / 'state')
    return Path(base) / 'ORVEX' / 'Jarvis' / 'app_launch_history.json'



class AppLaunchHistory:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_history_path()
        self._lock = threading.Lock()
        self._loaded = False
        self._data: dict = {'version': 1, 'preferred': {}, 'recent': []}

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            if self.path.is_symlink() or self.path.stat().st_size > _MAX_READ_BYTES:
                return
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError, TypeError):
            return
        if not isinstance(data, dict) or data.get('version') != 1:
            return
        prefs, recent = data.get('preferred'), data.get('recent')
        if not isinstance(prefs, dict) or not isinstance(recent, list):
            return
        self._data = {'version': 1,
                      'preferred': {k: v for k, v in list(prefs.items())[-_MAX_PREFERENCES:]
                                    if isinstance(k, str) and isinstance(v, dict)},
                      'recent': [row for row in recent[-_MAX_EVENTS:] if isinstance(row, dict)]}

    def preferred(self, canonical_name: str, candidates: Sequence[InstalledApp]) -> InstalledApp | None:
        """Return only an app already enumerated by the trusted inventory."""
        with self._lock:
            self._load()
            entry = self._data['preferred'].get(normalize(canonical_name))
            if not isinstance(entry, dict):
                return None
            for app in candidates:
                if (normalize(app.name) == normalize(canonical_name) and
                        app.kind == entry.get('kind') and app.source == entry.get('source') and
                        app.target.casefold() == str(entry.get('target', '')).casefold()):
                    return app
        return None

    def record(self, app: InstalledApp, *, accepted: bool) -> None:
        """Log actual launch attempts only, never an unauthorized request."""
        key = normalize(app.name)
        with self._lock:
            self._load()
            prefs = self._data['preferred']
            route = {'kind': app.kind, 'source': app.source, 'target': app.target}
            if accepted:
                # FIFO insertion order lets us bound the cache with no database.
                prefs.pop(key, None)
                prefs[key] = route
                while len(prefs) > _MAX_PREFERENCES:
                    prefs.pop(next(iter(prefs)))
            elif isinstance(prefs.get(key), dict) and all(
                    prefs[key].get(field) == route[field] for field in route):
                # Failure invalidates a previously accepted route.
                prefs.pop(key, None)
            self._data['recent'].append({
                'at_unix': int(time.time()), 'app': app.name, 'kind': app.kind,
                'source': app.source, 'target': app.target,
                'result': 'handoff_accepted' if accepted else 'handoff_failed',
            })
            del self._data['recent'][:-_MAX_EVENTS]
            self._save()

    def _save(self) -> None:
        # A history write failure must not turn a successful OS handoff into a
        # failed app launch. Never write to tracked repository source files.
        temp_path = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd, temp_path = tempfile.mkstemp(prefix='.jarvis-app-log-', suffix='.json', dir=str(self.path.parent))
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(self._data, stream, ensure_ascii=False, separators=(',', ':'))
            try:
                os.chmod(temp_path, 0o600)
            except OSError:
                pass
            os.replace(temp_path, self.path)
        except (OSError, ValueError, TypeError):
            pass
        finally:
            if temp_path is not None:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except OSError:
                    pass
