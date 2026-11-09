"""Short SQLite transactions own receipt, delivery state and retention."""
from __future__ import annotations
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4
from . import database
from .core.crypto import decrypt_json_bytes, encrypt_json_bytes
from .models import MessageInput, RoutingInput, TargetInput
from .routing import match_rules
from .target_config import normalize_target_config

_SECRETS = {'device_key', 'access_token', 'app_token', 'password'}

class StoreError(Exception):
    def __init__(self, code: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(code)


def _now(value):
    return time.time() if value is None else value


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _date(value):
    return None if value is None else datetime.fromtimestamp(value, timezone.utc).isoformat()


class Store:
    def __init__(self, db_path: Path, encryption_key: str):
        self.db_path = Path(db_path)
        self.encryption_key = encryption_key

    def initialize(self):
        database.initialize(self.db_path)
        # Fail closed on a changed/lost encryption key without changing data.
        with database.connection(self.db_path) as db:
            for row in db.execute('SELECT config_encrypted FROM targets'):
                self._decrypt(row['config_encrypted'])

    def check(self):
        with database.connection(self.db_path) as db:
            db.execute('SELECT COUNT(*) FROM messages').fetchone()

    def _decrypt(self, ciphertext):
        return json.loads(decrypt_json_bytes(ciphertext, self.encryption_key))

    def _target(self, row):
        config = self._decrypt(row['config_encrypted'])
        return {'id': row['id'], 'name': row['name'], 'kind': row['kind'],
                'is_default': bool(row['is_default']), 'enabled': bool(row['enabled']),
                'config': {k: v for k, v in config.items() if k not in _SECRETS}}

    def create_target(self, data):
        target = TargetInput.model_validate(data).model_dump()
        config = normalize_target_config(target['kind'], target['config'])
        target_id = str(uuid4())
        encrypted = encrypt_json_bytes(_json(config).encode(), self.encryption_key)
        with database.connection(self.db_path, write=True) as db:
            db.execute('INSERT INTO targets VALUES (?,?,?,?,?,?)', (target_id, target['name'],
                       target['kind'], encrypted, int(target['is_default']), int(target['enabled'])))
            row = db.execute('SELECT * FROM targets WHERE id=?', (target_id,)).fetchone()
        return self._target(row)

    def update_target(self, target_id, data):
        target = TargetInput.model_validate(data).model_dump()
        with database.connection(self.db_path) as db:
            previous = db.execute('SELECT * FROM targets WHERE id=?', (target_id,)).fetchone()
        if previous is None:
            raise StoreError('target_not_found', 404)
        config = dict(target['config'])
        if previous['kind'] == target['kind']:
            old_config = self._decrypt(previous['config_encrypted'])
            for field in _SECRETS:
                if field not in config and field in old_config:
                    config[field] = old_config[field]
        config = normalize_target_config(target['kind'], config)
        encrypted = encrypt_json_bytes(_json(config).encode(), self.encryption_key)
        with database.connection(self.db_path, write=True) as db:
            current = db.execute('SELECT * FROM targets WHERE id=?', (target_id,)).fetchone()
            if current is None:
                raise StoreError('target_not_found', 404)
            if dict(current) != dict(previous):
                raise StoreError('target_changed', 409)
            if current['kind'] != target['kind'] and db.execute(
                    "SELECT 1 FROM deliveries WHERE target_id=? AND status!='sent' LIMIT 1",
                    (target_id,)).fetchone():
                raise StoreError('target_has_unfinished_deliveries', 409)
            changed = db.execute('UPDATE targets SET name=?,kind=?,config_encrypted=?,is_default=?,enabled=? WHERE id=?',
                                 (target['name'], target['kind'], encrypted, int(target['is_default']),
                                  int(target['enabled']), target_id)).rowcount
            if not changed:
                raise StoreError('target_not_found', 404)
            row = db.execute('SELECT * FROM targets WHERE id=?', (target_id,)).fetchone()
        return self._target(row)

    def list_targets(self):
        with database.connection(self.db_path) as db:
            return [self._target(row) for row in db.execute('SELECT * FROM targets ORDER BY name,id')]

    def delete_target(self, target_id):
        with database.connection(self.db_path, write=True) as db:
            if db.execute("SELECT 1 FROM deliveries WHERE target_id=? AND status!='sent' LIMIT 1", (target_id,)).fetchone():
                raise StoreError('target_has_unfinished_deliveries', 409)
            if any(target_id in rule['target_ids'] for rule in self._routing(db)['rules']):
                raise StoreError('target_referenced_by_routing', 409)
            if not db.execute('DELETE FROM targets WHERE id=?', (target_id,)).rowcount:
                raise StoreError('target_not_found', 404)

    def _routing(self, db):
        row = db.execute('SELECT revision,rules_json FROM routing_config WHERE id=1').fetchone()
        return {'revision': row['revision'], 'rules': json.loads(row['rules_json'])}

    def get_routing(self):
        with database.connection(self.db_path) as db:
            return self._routing(db)

    def update_routing(self, payload):
        data = RoutingInput.model_validate(payload).model_dump()
        with database.connection(self.db_path, write=True) as db:
            current = self._routing(db)
            if current['revision'] != data['revision']:
                raise StoreError('routing_changed', 409)
            # Disabled rules retain references too; enabling a target is required
            # only when a new receipt actually selects it.
            for target_id in {target_id for rule in data['rules'] for target_id in rule['target_ids']}:
                if db.execute('SELECT 1 FROM targets WHERE id=?', (target_id,)).fetchone() is None:
                    raise StoreError('target_unavailable')
            revision = current['revision'] + 1
            db.execute('UPDATE routing_config SET revision=?,rules_json=? WHERE id=1',
                       (revision, _json(data['rules'])))
        return {'revision': revision, 'rules': data['rules']}

    def receive(self, payload, *, now=None):
        data = MessageInput.model_validate(payload).model_dump()
        requested = data['target_ids']
        if requested is not None:
            requested = sorted(set(requested))
        canonical = {'title': data['title'], 'body': data['body'], 'priority': data['priority'], 'target_ids': requested}
        content_hash = hashlib.sha256(_json(canonical).encode()).hexdigest()
        stamp, message_id = _now(now), str(uuid4())
        with database.connection(self.db_path, write=True) as db:
            if data['idempotency_key'] is not None:
                original = db.execute('SELECT id,content_hash FROM messages WHERE idempotency_key=?', (data['idempotency_key'],)).fetchone()
                if original is not None:
                    if original['content_hash'] != content_hash:
                        raise StoreError('idempotency_conflict', 409)
                    return {'message_id': original['id'], 'duplicate': True}
            decision = {'mode': 'explicit', 'rules_revision': None, 'matched_rule_ids': []}
            if requested is None:
                routing = self._routing(db)
                matched, requested = match_rules(routing['rules'], data)
                decision = {'mode': 'rules' if matched else 'defaults',
                            'rules_revision': routing['revision'], 'matched_rule_ids': matched}
                if not matched:
                    requested = [row['id'] for row in db.execute(
                        'SELECT id FROM targets WHERE enabled=1 AND is_default=1 ORDER BY id')]
            targets = []
            for target_id in requested:
                target = db.execute('SELECT * FROM targets WHERE id=? AND enabled=1', (target_id,)).fetchone()
                if target is None:
                    raise StoreError('target_unavailable')
                targets.append(target)
            if not targets:
                raise StoreError('no_targets')
            db.execute('''INSERT INTO messages
                (id,title,body,priority,received_at,idempotency_key,content_hash,routing_decision_json)
                VALUES (?,?,?,?,?,?,?,?)''',
                       (message_id, data['title'], data['body'], data['priority'], stamp,
                        data['idempotency_key'], content_hash, _json(decision)))
            for target in targets:
                db.execute('''INSERT INTO deliveries
                    (id,message_id,target_id,target_name,kind,status,available_at,created_at,updated_at)
                    VALUES (?,?,?,?,?,'pending',?,?,?)''',
                           (str(uuid4()), message_id, target['id'], target['name'], target['kind'], stamp, stamp, stamp))
        return {'message_id': message_id, 'duplicate': False}

    def _delivery(self, row):
        value = dict(row)
        value.pop('lease_token', None)
        for field in ('available_at', 'created_at', 'updated_at', 'completed_at'):
            value[field] = _date(value[field])
        return value

    def _message(self, db, row):
        value = dict(row)
        value.pop('content_hash', None)
        decision = value.pop('routing_decision_json')
        value['routing_decision'] = json.loads(decision) if decision is not None else None
        value['received_at'] = _date(value['received_at'])
        value['deliveries'] = [self._delivery(d) for d in db.execute(
            'SELECT * FROM deliveries WHERE message_id=? ORDER BY created_at,id', (row['id'],))]
        return value

    def get_message(self, message_id):
        with database.connection(self.db_path) as db:
            row = db.execute('SELECT * FROM messages WHERE id=?', (message_id,)).fetchone()
            if row is None:
                raise StoreError('message_not_found', 404)
            return self._message(db, row)

    def list_messages(self, limit=50, before=None):
        if not 1 <= limit <= 100:
            raise StoreError('invalid_page_size')
        args, clause = [], ''
        if before:
            try:
                stamp, message_id = json.loads(base64.urlsafe_b64decode(before.encode()))
                stamp = float(stamp)
                if not isinstance(message_id, str):
                    raise ValueError
            except (ValueError, TypeError):
                raise StoreError('invalid_cursor') from None
            clause = ' WHERE (received_at,id) < (?,?)'
            args += [stamp, message_id]
        with database.connection(self.db_path) as db:
            rows = db.execute('SELECT * FROM messages' + clause + ' ORDER BY received_at DESC,id DESC LIMIT ?', (*args, limit + 1)).fetchall()
            messages = [self._message(db, row) for row in rows[:limit]]
        cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            cursor = base64.urlsafe_b64encode(_json([last['received_at'], last['id']]).encode()).decode()
        return {'messages': messages, 'next_cursor': cursor}

    def claim(self, limit=4, *, max_attempts=5, now=None):
        stamp, claimed = _now(now), []
        with database.connection(self.db_path, write=True) as db:
            db.execute("UPDATE deliveries SET status='failed',last_error='attempts_exhausted',completed_at=?,updated_at=? WHERE status IN ('pending','retry') AND cycle_attempts>=?", (stamp, stamp, max_attempts))
            rows = db.execute("SELECT * FROM deliveries WHERE status IN ('pending','retry') AND available_at<=? ORDER BY available_at,id LIMIT ?", (stamp, limit)).fetchall()
            for row in rows:
                lease = str(uuid4())
                db.execute("UPDATE deliveries SET status='sending',attempts=attempts+1,cycle_attempts=cycle_attempts+1,lease_token=?,updated_at=? WHERE id=?", (lease, stamp, row['id']))
                target = db.execute('SELECT * FROM targets WHERE id=?', (row['target_id'],)).fetchone()
                message = db.execute('SELECT title,body,priority FROM messages WHERE id=?', (row['message_id'],)).fetchone()
                claimed.append({**dict(row), 'status': 'sending', 'attempts': row['attempts'] + 1,
                                'cycle_attempts': row['cycle_attempts'] + 1, 'lease_token': lease,
                                'kind': target['kind'], 'config': self._decrypt(target['config_encrypted']), 'message': dict(message)})
        return claimed

    def finish(self, delivery_id, lease_token, *, error=None, max_attempts=5,
               backoff_base_seconds=5, backoff_max_seconds=300, now=None):
        stamp = _now(now)
        with database.connection(self.db_path, write=True) as db:
            row = db.execute("SELECT * FROM deliveries WHERE id=? AND status='sending' AND lease_token=?", (delivery_id, lease_token)).fetchone()
            if row is None:
                return False
            terminal = error is None or row['cycle_attempts'] >= max_attempts
            status = 'sent' if error is None else ('failed' if terminal else 'retry')
            delay = min(backoff_max_seconds, backoff_base_seconds * 2 ** min(row['cycle_attempts'] - 1, 30))
            db.execute('UPDATE deliveries SET status=?,last_error=?,lease_token=NULL,available_at=?,completed_at=?,updated_at=? WHERE id=?',
                       (status, error, stamp if terminal else stamp + delay, stamp if terminal else None, stamp, delivery_id))
            return True

    def recover(self, *, max_attempts=5, now=None):
        # Only call after the application acquires its exclusive data-dir lock.
        stamp = _now(now)
        with database.connection(self.db_path, write=True) as db:
            return db.execute('''UPDATE deliveries SET
                status=CASE WHEN cycle_attempts>=? THEN 'failed' ELSE 'retry' END,
                last_error='interrupted',lease_token=NULL,available_at=?,updated_at=?,
                completed_at=CASE WHEN cycle_attempts>=? THEN ? ELSE NULL END
                WHERE status='sending' ''', (max_attempts, stamp, stamp, max_attempts, stamp)).rowcount

    def manual_retry(self, delivery_id, *, now=None):
        stamp = _now(now)
        with database.connection(self.db_path, write=True) as db:
            row = db.execute('SELECT * FROM deliveries WHERE id=?', (delivery_id,)).fetchone()
            if row is None:
                raise StoreError('delivery_not_found', 404)
            if row['status'] != 'failed':
                raise StoreError('only_failed_deliveries_can_retry', 409)
            db.execute("UPDATE deliveries SET status='pending',cycle_attempts=0,available_at=?,completed_at=NULL,updated_at=? WHERE id=?", (stamp, stamp, delivery_id))
            row = db.execute('SELECT * FROM deliveries WHERE id=?', (delivery_id,)).fetchone()
        return self._delivery(row)

    def cleanup(self, retention_days, *, now=None):
        if retention_days <= 0:
            raise StoreError('invalid_retention')
        cutoff = _now(now) - retention_days * 86400
        with database.connection(self.db_path, write=True) as db:
            return db.execute('''DELETE FROM messages WHERE
                EXISTS (SELECT 1 FROM deliveries WHERE message_id=messages.id)
                AND NOT EXISTS (SELECT 1 FROM deliveries WHERE message_id=messages.id
                                AND (status!='sent' OR completed_at IS NULL OR completed_at>=?))''', (cutoff,)).rowcount
