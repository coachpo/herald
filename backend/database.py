"""SQLite durability settings and the complete, single-version schema."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

SCHEMA = '''
CREATE TABLE IF NOT EXISTS targets (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
 config_encrypted TEXT NOT NULL, is_default INTEGER NOT NULL, enabled INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
 priority INTEGER NOT NULL CHECK(priority BETWEEN 1 AND 5),
 received_at REAL NOT NULL, idempotency_key TEXT UNIQUE, content_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deliveries (
 id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
 target_id TEXT REFERENCES targets(id) ON DELETE SET NULL,
 target_name TEXT NOT NULL, kind TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','sending','retry','sent','failed')),
 attempts INTEGER NOT NULL DEFAULT 0, cycle_attempts INTEGER NOT NULL DEFAULT 0,
 available_at REAL NOT NULL, lease_token TEXT, last_error TEXT,
 created_at REAL NOT NULL, updated_at REAL NOT NULL, completed_at REAL,
 UNIQUE(message_id, target_id)
);
CREATE INDEX IF NOT EXISTS delivery_due ON deliveries(status,available_at);
CREATE INDEX IF NOT EXISTS delivery_message ON deliveries(message_id);
CREATE INDEX IF NOT EXISTS messages_received ON messages(received_at DESC,id DESC);
'''

@contextmanager
def connection(path: Path, *, write: bool = False):
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA busy_timeout=5000')
        if write:
            db.execute('BEGIN IMMEDIATE')
        yield db
        if write:
            db.commit()
    except BaseException:
        if db.in_transaction:
            db.rollback()
        raise
    finally:
        db.close()


def initialize(path: Path) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with connection(path) as db:
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0, 1):
            raise RuntimeError('unsupported database schema; use a new data directory')
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('BEGIN IMMEDIATE;\n' + SCHEMA + '\nPRAGMA user_version=1;\nCOMMIT;')
    path.chmod(0o600)
