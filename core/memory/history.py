"""Jarvis Core v2: durable, local transcript/event history (0.1.6.1).

This is an *evidence archive*, not a model memory or a claim of perfect audio
transcription. Store only confirmed user transcriptions, user-facing replies,
and post-execution Core tool outcomes. Never store provider prompts or speculative
responses. This module is intentionally independent of Realtime/Luna.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

SCHEMA_VERSION = 1
MAX_TEXT = 1_048_576  # refuse enormous records rather than silently truncating words
VALID_ROLES = frozenset({'user', 'assistant', 'action'})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def _flag(value: object, default: bool) -> bool:
    if value is None:
        return default
    s = str(value).strip().lower()
    if s in {'1','true','yes','on'}:
        return True
    if s in {'0','false','no','off'}:
        return False
    raise ValueError('JARVIS_CHAT_HISTORY_ENABLED must be 0/1, true/false, yes/no, or on/off')


class ConversationHistoryStore:
    """SQLite archive scoped by owner, device and fresh desktop conversation session.

    Each write uses its own short transaction for crash recovery; WAL supports
    concurrent read-only searches while voice events arrive. The caller should
    dispatch writes via asyncio.to_thread to keep the audio loop responsive.
    """

    def __init__(self, db_path: str | Path, *, owner_id: str = 'local-development-user') -> None:
        self.path = Path(db_path).expanduser().resolve()
        self.owner_id = owner_id
        if not owner_id or not owner_id.strip():
            raise ValueError('owner_id required')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == 'posix':
            try:
                self.path.parent.chmod(0o700)
            except OSError:
                pass
        self._initialize()
        if os.name == 'posix':
            try:
                self.path.chmod(0o600)
            except OSError:
                pass

    @classmethod
    def from_environment(cls, project_root: Path, env: Mapping[str,str], *, owner_id: str='local-development-user') -> 'ConversationHistoryStore | None':
        if not _flag(env.get('JARVIS_CHAT_HISTORY_ENABLED'), True):
            return None
        configured = str(env.get('JARVIS_CHAT_HISTORY_DB', '')).strip()
        db_path = Path(configured).expanduser() if configured else project_root / '.runtime' / 'memory' / 'chat_history.sqlite3'
        if not db_path.is_absolute():
            db_path = project_root / db_path
        return cls(db_path, owner_id=owner_id)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA busy_timeout=5000')
            db.execute('PRAGMA secure_delete=ON')
            with db:
                yield db
        finally:
            db.close()

    def _initialize(self) -> None:
        with self._db() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS history_sessions (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_history_session_owner
                    ON history_sessions(owner_id, started_at);
                CREATE TABLE IF NOT EXISTS history_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES history_sessions(id) ON DELETE CASCADE,
                    owner_id TEXT NOT NULL,
                    turn INTEGER NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant','action')),
                    source TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    event_key TEXT NOT NULL,
                    UNIQUE(session_id, event_key)
                );
                CREATE INDEX IF NOT EXISTS idx_history_entries_session
                    ON history_entries(session_id, id);
                CREATE INDEX IF NOT EXISTS idx_history_entries_owner
                    ON history_entries(owner_id, id);
            ''')
            # Optional FTS5 search index. Use plain substring search if the system
            # SQLite build lacks FTS5 (some embedded Windows environments do).
            try:
                db.executescript('''
                    CREATE VIRTUAL TABLE IF NOT EXISTS history_fts USING fts5(
                        text, content='history_entries', content_rowid='id'
                    );
                    CREATE TRIGGER IF NOT EXISTS history_fts_insert AFTER INSERT ON history_entries BEGIN
                        INSERT INTO history_fts(rowid,text) VALUES(new.id,new.text);
                    END;
                    CREATE TRIGGER IF NOT EXISTS history_fts_delete AFTER DELETE ON history_entries BEGIN
                        INSERT INTO history_fts(history_fts,rowid,text) VALUES('delete',old.id,old.text);
                    END;
                ''')
            except sqlite3.OperationalError as error:
                if 'fts5' not in str(error).lower():
                    raise
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError(f'History database uses a newer schema: {version}')
            db.execute(f'PRAGMA user_version={SCHEMA_VERSION}')

    def start_session(self, *, device_id: str='desktop-alpha', model: str='unknown') -> str:
        session_id = uuid4().hex
        with self._db() as db:
            db.execute('INSERT INTO history_sessions(id,owner_id,device_id,model,started_at) VALUES(?,?,?,?,?)',
                       (session_id,self.owner_id,device_id,model,_utc_now()))
        return session_id

    def end_session(self, session_id: str) -> None:
        with self._db() as db:
            db.execute('UPDATE history_sessions SET ended_at=COALESCE(ended_at,?) WHERE id=? AND owner_id=?',
                       (_utc_now(),session_id,self.owner_id))

    def append(self, session_id: str, *, turn: int, role: str, source: str, text: str, status: str='reported') -> bool:
        if role not in VALID_ROLES:
            raise ValueError(f'unsupported history role: {role!r}')
        if not isinstance(text,str) or not text.strip():
            return False
        if len(text) > MAX_TEXT:
            raise ValueError('history text exceeds maximum; no truncation performed')
        if not isinstance(turn,int) or turn < 0:
            raise ValueError('turn must be nonnegative integer')
        if not isinstance(source,str) or len(source) > 128 or not source:
            raise ValueError('invalid source')
        if not isinstance(status,str) or len(status)>128 or not status:
            raise ValueError('invalid status')
        # The renderer can report the same response twice through overlapping
        # completion paths. Ignore exact duplicates for the same turn and role,
        # but keep different actual replies and distinct action outcomes.
        fingerprint = json.dumps([turn,role,text] if role!='action' else [turn,role,source,text,status],
                                 ensure_ascii=False,separators=(',',':'))
        event_key = hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()
        with self._db() as db:
            cur=db.execute('''INSERT OR IGNORE INTO history_entries
                (session_id,owner_id,turn,role,source,text,created_at,status,event_key)
                SELECT id,owner_id,?,?,?,?,?,?,? FROM history_sessions
                WHERE id=? AND owner_id=?''',
                (turn,role,source,text,_utc_now(),status,event_key,session_id,self.owner_id))
            if not cur.rowcount:
                exists=db.execute('SELECT 1 FROM history_sessions WHERE id=? AND owner_id=?', (session_id,self.owner_id)).fetchone()
                if not exists: raise ValueError('unknown session or owner')
            return bool(cur.rowcount)

    def sessions(self, limit: int=30) -> list[dict[str,Any]]:
        with self._db() as db:
            rows=db.execute('''SELECT s.id,s.started_at,s.ended_at,s.device_id,s.model,
                COUNT(e.id) AS entries FROM history_sessions s
                LEFT JOIN history_entries e ON e.session_id=s.id
                WHERE s.owner_id=? GROUP BY s.id
                ORDER BY s.started_at DESC LIMIT ?''',(self.owner_id,self._limit(limit))).fetchall()
            return [dict(row) for row in rows]

    def entries(self, session_id: str, limit: int=500) -> list[dict[str,Any]]:
        with self._db() as db:
            rows=db.execute('''SELECT e.id,e.turn,e.role,e.source,e.text,e.created_at,e.status
                FROM history_entries e JOIN history_sessions s ON s.id=e.session_id
                WHERE e.session_id=? AND s.owner_id=?
                ORDER BY e.id ASC LIMIT ?''',(session_id,self.owner_id,self._limit(limit,10000))).fetchall()
            return [dict(row) for row in rows]

    def search(self, query: str, limit: int=50) -> list[dict[str,Any]]:
        query=str(query).strip()
        if not query:
            return []
        with self._db() as db:
            params=(self.owner_id,)
            columns='e.id,e.session_id,e.turn,e.role,e.source,e.text,e.created_at,e.status'
            try:
                expression='"'+query.replace('"','""')+'"'
                rows=db.execute(f'''SELECT {columns} FROM history_fts f
                    JOIN history_entries e ON e.id=f.rowid
                    WHERE e.owner_id=? AND history_fts MATCH ?
                    ORDER BY e.id DESC LIMIT ?''', params+(expression,self._limit(limit))).fetchall()
                if rows: return [dict(row) for row in rows]
            except sqlite3.OperationalError:
                pass
            escaped=query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
            rows=db.execute(f'''SELECT {columns} FROM history_entries e
                WHERE e.owner_id=? AND e.text LIKE ? ESCAPE '\\'
                ORDER BY e.id DESC LIMIT ?''',params+('%'+escaped+'%',self._limit(limit))).fetchall()
            return [dict(row) for row in rows]

    def delete_session(self, session_id: str) -> bool:
        with self._db() as db:
            cur=db.execute('DELETE FROM history_sessions WHERE id=? AND owner_id=?',(session_id,self.owner_id))
        return bool(cur.rowcount)

    @staticmethod
    def _limit(value: int, maximum: int=500) -> int:
        if not isinstance(value,int) or value < 1: raise ValueError('limit must be positive')
        return min(value,maximum)
