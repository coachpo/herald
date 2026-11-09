from __future__ import annotations

import hashlib
import json
import sqlite3
import stat

import pytest

from backend import database
from backend.core.crypto import encrypt_json_bytes
from backend.store import Store


# The actual v1 schema is kept here independently of the current initializer.
# Migration tests must start with the old format, not a modified v2 database.
V1_SCHEMA = '''
CREATE TABLE targets (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
 config_encrypted TEXT NOT NULL, is_default INTEGER NOT NULL, enabled INTEGER NOT NULL
);
CREATE TABLE messages (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
 priority INTEGER NOT NULL CHECK(priority BETWEEN 1 AND 5),
 received_at REAL NOT NULL, idempotency_key TEXT UNIQUE, content_hash TEXT NOT NULL
);
CREATE TABLE deliveries (
 id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
 target_id TEXT REFERENCES targets(id) ON DELETE SET NULL,
 target_name TEXT NOT NULL, kind TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','sending','retry','sent','failed')),
 attempts INTEGER NOT NULL DEFAULT 0, cycle_attempts INTEGER NOT NULL DEFAULT 0,
 available_at REAL NOT NULL, lease_token TEXT, last_error TEXT,
 created_at REAL NOT NULL, updated_at REAL NOT NULL, completed_at REAL,
 UNIQUE(message_id, target_id)
);
CREATE INDEX delivery_due ON deliveries(status,available_at);
CREATE INDEX delivery_message ON deliveries(message_id);
CREATE INDEX messages_received ON messages(received_at DESC,id DESC);
PRAGMA user_version=1;
'''
STATUSES = ('pending', 'sending', 'retry', 'sent', 'failed')


def _legacy_payload(status):
    return {'title': '', 'body': f'legacy {status}', 'priority': 3,
            'idempotency_key': f'legacy-key-{status}'}


@pytest.fixture
def v1_database(settings):
    settings.data_dir.mkdir(mode=0o700)
    encrypted = encrypt_json_bytes(json.dumps({
        'server_base_url': 'https://8.8.8.8', 'topic': 'legacy',
        'access_token': 'legacy-test-credential-not-real',
    }).encode(), settings.encryption_key)
    with sqlite3.connect(settings.database_path) as db:
        db.executescript(V1_SCHEMA)
        db.execute('INSERT INTO targets VALUES (?,?,?,?,?,?)',
                   ('legacy-target', 'Legacy target', 'ntfy', encrypted, 1, 1))
        for index, status in enumerate(STATUSES):
            payload = _legacy_payload(status)
            # This is the v1 wire-request fingerprint, with target_ids normalized
            # to null. The new computed target set must not be incorporated.
            canonical = {'title': payload['title'], 'body': payload['body'],
                         'priority': payload['priority'], 'target_ids': None}
            fingerprint = hashlib.sha256(json.dumps(
                canonical, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
            ).encode()).hexdigest()
            db.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?)', (
                f'message-{status}', '', payload['body'], 3, 10 + index,
                payload['idempotency_key'], fingerprint,
            ))
            db.execute('''INSERT INTO deliveries
                (id,message_id,target_id,target_name,kind,status,attempts,
                 cycle_attempts,available_at,lease_token,last_error,created_at,
                 updated_at,completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                f'delivery-{status}', f'message-{status}', 'legacy-target',
                'Legacy target', 'ntfy', status, index + 1,
                0 if status == 'pending' else 2, 20,
                'old-lease' if status == 'sending' else None,
                'legacy-error' if status in ('retry', 'failed') else None,
                10 + index, 20, 20 if status in ('sent', 'failed') else None,
            ))
    return settings.database_path


def _rows(path, table):
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY id')]


def _schema(path):
    with sqlite3.connect(path) as db:
        return db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name').fetchall()


def test_new_database_is_v2_with_durable_connection_settings(settings):
    database.initialize(settings.database_path)
    with database.connection(settings.database_path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 2
        assert db.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
        assert db.execute('PRAGMA synchronous').fetchone()[0] == 2
        assert db.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        assert db.execute('PRAGMA busy_timeout').fetchone()[0] == 5000
        assert dict(db.execute('SELECT * FROM routing_config').fetchone()) == {
            'id': 1, 'revision': 0, 'rules_json': '[]',
        }
        assert 'routing_decision_json' in {
            column['name'] for column in db.execute('PRAGMA table_info(messages)')
        }
    assert stat.S_IMODE(settings.database_path.stat().st_mode) == 0o600


def test_v1_migration_preserves_all_durable_fields_and_constraints(v1_database, settings):
    original = {table: _rows(v1_database, table) for table in ('targets', 'messages', 'deliveries')}
    database.initialize(v1_database)
    assert _rows(v1_database, 'targets') == original['targets']
    assert _rows(v1_database, 'deliveries') == original['deliveries']
    assert _rows(v1_database, 'messages') == [
        {**message, 'routing_decision_json': None} for message in original['messages']
    ]
    with database.connection(v1_database) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 2
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    with pytest.raises(sqlite3.IntegrityError), database.connection(v1_database, write=True) as db:
        db.execute('''INSERT INTO messages
            (id,title,body,priority,received_at,idempotency_key,content_hash)
            SELECT 'duplicate-message',title,body,priority,received_at,idempotency_key,content_hash
            FROM messages WHERE id='message-pending' ''')
    with pytest.raises(sqlite3.IntegrityError), database.connection(v1_database, write=True) as db:
        db.execute('''INSERT INTO deliveries
            (id,message_id,target_id,target_name,kind,status,available_at,created_at,updated_at)
            SELECT 'duplicate-delivery',message_id,target_id,target_name,kind,status,
                   available_at,created_at,updated_at FROM deliveries WHERE id='delivery-pending' ''')
    with pytest.raises(sqlite3.IntegrityError), database.connection(v1_database, write=True) as db:
        db.execute("UPDATE deliveries SET target_id='missing-target' WHERE id='delivery-pending'")
    with pytest.raises(sqlite3.IntegrityError), database.connection(v1_database, write=True) as db:
        db.execute("UPDATE messages SET priority=6 WHERE id='message-pending'")
    with pytest.raises(sqlite3.IntegrityError), database.connection(v1_database, write=True) as db:
        db.execute("INSERT INTO routing_config VALUES (2,0,'[]')")
    with pytest.raises(sqlite3.IntegrityError), database.connection(v1_database, write=True) as db:
        db.execute('UPDATE routing_config SET rules_json=NULL WHERE id=1')


def test_v1_records_remain_queryable_replayable_and_retryable(v1_database, settings):
    store = Store(v1_database, settings.encryption_key)
    store.initialize()
    assert store.list_targets()[0]['config']['topic'] == 'legacy'
    assert 'access_token' not in store.list_targets()[0]['config']
    assert len(store.list_messages()['messages']) == len(STATUSES)
    for status in STATUSES:
        detail = store.get_message(f'message-{status}')
        assert detail['routing_decision'] is None
        assert 'routing_decision_json' not in detail
        assert detail['deliveries'][0]['status'] == status
        assert store.receive(_legacy_payload(status)) == {
            'message_id': f'message-{status}', 'duplicate': True,
        }
    assert store.recover(max_attempts=5, now=100) == 1
    assert store.get_message('message-sending')['deliveries'][0]['status'] == 'retry'
    retry = store.manual_retry('delivery-failed', now=100)
    assert retry['attempts'] == 5 and retry['cycle_attempts'] == 0
    claims = store.claim(10, max_attempts=5, now=100)
    assert {claim['id'] for claim in claims} == {
        f'delivery-{status}' for status in STATUSES if status != 'sent'
    }
    assert all(claim['config']['access_token'] == 'legacy-test-credential-not-real' for claim in claims)
    for claim in claims:
        assert store.finish(claim['id'], claim['lease_token'], now=101)
    assert all(store.get_message(f'message-{status}')['deliveries'][0]['status'] == 'sent' for status in STATUSES)
    assert store.get_message('message-sent')['deliveries'][0]['attempts'] == 4
    assert len(_rows(v1_database, 'messages')) == 5
    assert len(_rows(v1_database, 'deliveries')) == 5


def test_v2_repeated_initialization_preserves_routing_and_receipts(v1_database):
    database.initialize(v1_database)
    rules = json.dumps([{'id': 'retained-rule', 'enabled': False,
                         'all': [{'field': 'priority', 'op': 'gte', 'value': 4}],
                         'target_ids': ['legacy-target']}])
    with sqlite3.connect(v1_database) as db:
        db.execute('UPDATE routing_config SET revision=7,rules_json=? WHERE id=1', (rules,))
    before = {table: _rows(v1_database, table) for table in ('targets', 'messages', 'deliveries', 'routing_config')}
    database.initialize(v1_database)
    database.initialize(v1_database)
    assert {table: _rows(v1_database, table) for table in before} == before


@pytest.mark.parametrize('version', [3, 999])
def test_higher_schema_version_is_rejected_without_changing_database(settings, version):
    settings.data_dir.mkdir(mode=0o700)
    with sqlite3.connect(settings.database_path) as db:
        db.execute(f'PRAGMA user_version={version}')
        db.execute('CREATE TABLE future_data (value TEXT)')
        db.execute("INSERT INTO future_data VALUES ('preserve me')")
    original_schema = _schema(settings.database_path)
    with pytest.raises(RuntimeError, match='unsupported database schema'):
        database.initialize(settings.database_path)
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == version
        assert db.execute('SELECT * FROM future_data').fetchall() == [('preserve me',)]
    assert _schema(settings.database_path) == original_schema


def test_v1_migration_failure_rolls_back_schema_rows_and_version(v1_database, monkeypatch):
    original_schema = _schema(v1_database)
    original = {table: _rows(v1_database, table) for table in ('targets', 'messages', 'deliveries')}
    create_routing = database._create_routing_config

    def fail_after_routing_created(db):
        create_routing(db)
        raise sqlite3.OperationalError('simulated interrupted migration')

    monkeypatch.setattr(database, '_create_routing_config', fail_after_routing_created)
    with pytest.raises(sqlite3.OperationalError, match='simulated interrupted migration'):
        database.initialize(v1_database)
    assert _schema(v1_database) == original_schema
    assert {table: _rows(v1_database, table) for table in original} == original
    with sqlite3.connect(v1_database) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 1
    monkeypatch.setattr(database, '_create_routing_config', create_routing)
    database.initialize(v1_database)
    with sqlite3.connect(v1_database) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 2


def test_new_database_failure_does_not_leave_partial_schema(settings, monkeypatch):
    create_routing = database._create_routing_config

    def fail_after_routing_created(db):
        create_routing(db)
        raise sqlite3.OperationalError('simulated first-start failure')

    monkeypatch.setattr(database, '_create_routing_config', fail_after_routing_created)
    with pytest.raises(sqlite3.OperationalError, match='simulated first-start failure'):
        database.initialize(settings.database_path)
    assert _schema(settings.database_path) == []
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 0
    monkeypatch.setattr(database, '_create_routing_config', create_routing)
    database.initialize(settings.database_path)
    assert _rows(settings.database_path, 'routing_config') == [
        {'id': 1, 'revision': 0, 'rules_json': '[]'},
    ]
