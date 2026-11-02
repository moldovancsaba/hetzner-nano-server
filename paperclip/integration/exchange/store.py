"""Atomic exchange ledger with exact-byte replay, fenced leases and scoped capacity."""
import contextlib
import json
import os
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from .contract import Contract, ExchangeError, MAX_RESPONSE, digest, encode, iso, timestamp

SCHEMA = '''
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS operations(
 principal TEXT NOT NULL,id TEXT NOT NULL,route TEXT NOT NULL,sha256 TEXT NOT NULL,
 status INTEGER NOT NULL,response BLOB NOT NULL,resource TEXT NOT NULL,kind TEXT NOT NULL,created REAL NOT NULL,
 PRIMARY KEY(principal,id));
CREATE TABLE IF NOT EXISTS messages(
 id TEXT PRIMARY KEY,kind TEXT NOT NULL,application TEXT NOT NULL,client TEXT NOT NULL,
 producer TEXT NOT NULL,identity TEXT NOT NULL,body BLOB NOT NULL,sha256 TEXT NOT NULL,
 created REAL NOT NULL,expires REAL,processed INTEGER NOT NULL DEFAULT 0,
 UNIQUE(kind,application,client,identity));
CREATE TABLE IF NOT EXISTS deliveries(
 message TEXT NOT NULL,consumer TEXT NOT NULL,inbox TEXT NOT NULL,generation TEXT NOT NULL,
 token TEXT NOT NULL,lease_end REAL NOT NULL,acked REAL,receipt BLOB,
 PRIMARY KEY(message,consumer),FOREIGN KEY(message) REFERENCES messages(id));
CREATE TABLE IF NOT EXISTS consumer_contacts(
 principal TEXT NOT NULL,kind TEXT NOT NULL,application TEXT NOT NULL,client TEXT NOT NULL,
 inbox TEXT NOT NULL,last_contact REAL NOT NULL,PRIMARY KEY(principal,kind,application,client));
CREATE TABLE IF NOT EXISTS projection(
 application TEXT NOT NULL,client TEXT NOT NULL,evaluation TEXT NOT NULL,
 revision INTEGER NOT NULL,event_id TEXT NOT NULL,payload BLOB NOT NULL,
 PRIMARY KEY(application,client,evaluation));
CREATE INDEX IF NOT EXISTS message_pending ON messages(kind,application,client,created);
'''


class Store:
    def __init__(self, path, *, clock=time.time, capacity=20, daily=20, contract=None):
        self.path, self.clock = Path(path), clock
        self.capacity, self.daily, self.contract = capacity, daily, contract or Contract()
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        os.chmod(self.path, 0o600)
        with self.connection() as db:
            if db.execute('PRAGMA user_version').fetchone()[0] not in (0, 1):
                raise RuntimeError('Unsupported exchange database version')
            db.executescript(SCHEMA)
            db.execute('INSERT OR IGNORE INTO meta VALUES(?,?)', ('generation', str(uuid.uuid4())))
            db.execute('PRAGMA user_version=1')

    @contextlib.contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA busy_timeout=5000')
            if db.execute('PRAGMA synchronous').fetchone()[0] != 2 or db.execute('PRAGMA foreign_keys').fetchone()[0] != 1:
                raise RuntimeError('Unsafe database configuration')
            yield db
        finally:
            db.close()

    @contextlib.contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def generation(self, db):
        return db.execute("SELECT value FROM meta WHERE key='generation'").fetchone()[0]

    @staticmethod
    def allowed(principal, scope):
        if scope not in principal['clients']:
            raise ExchangeError('forbidden', 403)
        return scope['application'], scope['client']

    def mutation(self, principal, operation, route, raw):
        try:
            if str(uuid.UUID(operation)) != operation:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ExchangeError('invalid_request') from None
        schema, capability, kind = self.route(route)
        if capability not in principal['scopes']:
            raise ExchangeError('forbidden', 403)
        value = self.contract.parse(raw)
        self.contract.validate(schema, value)
        app, client = self.allowed(principal, value['scope'])
        now = self.clock()
        with self.transaction() as db:
            saved = db.execute('SELECT * FROM operations WHERE principal=? AND id=?', (principal['id'], operation)).fetchone()
            if saved:
                if saved['route'] != route or saved['sha256'] != digest(raw):
                    raise ExchangeError('idempotency_conflict', 409)
                return saved['status'], bytes(saved['response'])
            available = os.statvfs(self.path.parent)
            if schema in ('SourceOffer','OutcomeEvent') and (available.f_bavail * available.f_frsize < 64 * 1024 * 1024 or self.path.stat().st_size > (192 if schema == 'SourceOffer' else 256) * 1024 * 1024):
                raise ExchangeError('capacity_hold', 429, True, 300)
            if schema in ('SourceOffer', 'OutcomeEvent'):
                status, response, resource = self.publish(db, principal, kind, value, raw, operation, app, client, now)
            elif schema == 'ClaimRequest':
                status, response, resource = self.claim(db, principal, kind, value, operation, app, client, now)
            else:
                status, response, resource = self.receipt(db, principal, kind, route, value, operation, app, client, now)
            encoded = encode(response)
            if len(encoded) > MAX_RESPONSE:
                raise ExchangeError('capacity_hold', 429, True, 60)
            db.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?)',
                       (principal['id'], operation, route, digest(raw), status, encoded, resource, kind, now))
            return status, encoded

    @staticmethod
    def route(route):
        if route == '/source-offers':
            return 'SourceOffer', 'sources:write', 'source_offer'
        if route == '/events':
            return 'OutcomeEvent', 'events:write', 'event'
        if route in ('/deliveries/claim', '/events/claim'):
            source = route.startswith('/deliveries')
            return 'ClaimRequest', 'sources:claim' if source else 'events:claim', 'source_claim' if source else 'event_claim'
        parts = route.split('/')
        if len(parts) == 4 and parts[1] in ('deliveries', 'events') and parts[3] == 'receipt':
            try:
                uuid.UUID(parts[2])
            except ValueError:
                raise ExchangeError('invalid_request') from None
            return 'IntakeReceipt', 'sources:claim' if parts[1] == 'deliveries' else 'events:claim', 'source_receipt' if parts[1] == 'deliveries' else 'event_receipt'
        raise ExchangeError('not_found', 404)

    def publish(self, db, principal, kind, value, raw, operation, app, client, now):
        identity = value['packet_id' if kind == 'source_offer' else 'event_id']
        old = db.execute('SELECT * FROM messages WHERE kind=? AND application=? AND client=? AND identity=?', (kind, app, client, identity)).fetchone()
        if old:
            # A resource can be republished under a fresh transport operation, never silently replaced.
            if old['producer'] != principal['id'] or old['sha256'] != digest(encode(value)):
                raise ExchangeError('idempotency_conflict', 409)
            resource = old['id']
        else:
            if kind == 'source_offer':
                if timestamp(value['expires_at']) <= now or timestamp(value['fetched_at']) > now + 300:
                    raise ExchangeError('invalid_request')
                if db.execute("SELECT count(*) FROM messages WHERE kind='source_offer' AND application=? AND client=? AND processed=0", (app, client)).fetchone()[0] >= self.capacity:
                    raise ExchangeError('capacity_hold', 429, True, 60)
                if db.execute("SELECT count(*) FROM messages WHERE kind='source_offer' AND application=? AND client=? AND created>=?", (app, client, now - now % 86400)).fetchone()[0] >= self.daily:
                    raise ExchangeError('capacity_hold', 429, True, 3600)
            else:
                if timestamp(value['occurred_at'])>now+300:raise ExchangeError('invalid_request')
                self.validate_event_reference(db, value, app, client)
                if db.execute("SELECT count(*) FROM messages WHERE kind='event' AND application=? AND client=? AND created>=?", (app, client, now - now % 86400)).fetchone()[0] >= 1000:
                    raise ExchangeError('capacity_hold', 429, True, 3600)
                # A feedback lane independent from source capacity remains bounded during outages.
                if db.execute("SELECT count(*) FROM messages m WHERE kind='event' AND application=? AND client=? AND NOT EXISTS(SELECT 1 FROM deliveries d WHERE d.message=m.id AND d.acked IS NOT NULL)", (app, client)).fetchone()[0] >= 1000:
                    raise ExchangeError('capacity_hold', 429, True, 60)
            resource = str(uuid.uuid4())
            db.execute('INSERT INTO messages(id,kind,application,client,producer,identity,body,sha256,created,expires) VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (resource, kind, app, client, principal['id'], identity, raw, digest(encode(value)), now, timestamp(value['expires_at']) if kind == 'source_offer' else None))
            if kind == 'event':
                self.project(db, app, client, value['evaluation_id'])
        return 202, {'operation_id': operation, 'resource_id': resource, 'state': 'broker_saved', 'received_at': iso(now)}, resource

    @staticmethod
    def rank(payload):
        if payload['event_type'] == 'delivery_readback':
            return 6 if payload['readback']['result'] == 'found_matching' else 5
        return {'queued': 0, 'not_checked': 1, 'checked': 2, 'rejected': 3,
                'submission_accepted': 4, 'uncertain': 5}.get(payload.get('state'), 1)

    def project(self, db, app, client, evaluation):
        current = db.execute('SELECT * FROM projection WHERE application=? AND client=? AND evaluation=?',
                             (app, client, evaluation)).fetchone()
        revision, predecessor = (current['revision'], current['event_id']) if current else (0, None)
        display = json.loads(current['payload']) if current else None
        while True:
            row = db.execute("SELECT body FROM messages WHERE kind='event' AND application=? AND client=? AND json_extract(body,'$.evaluation_id')=? AND json_extract(body,'$.revision')=?", (app, client, evaluation, revision + 1)).fetchone()
            if not row:
                break
            event = json.loads(row['body'])
            if event['previous_event_id'] != predecessor:
                break
            revision, predecessor = event['revision'], event['event_id']
            payload = event['payload']
            if display is None or self.rank(payload) >= self.rank(display):
                display = payload
            db.execute('INSERT INTO projection VALUES(?,?,?,?,?,?) ON CONFLICT(application,client,evaluation) DO UPDATE SET revision=excluded.revision,event_id=excluded.event_id,payload=excluded.payload',
                       (app, client, evaluation, revision, predecessor, encode(display)))
            packet = display.get('packet_id')
            completed = display.get('state') == 'rejected' or (display['event_type'] == 'delivery_readback' and display['readback']['result'] == 'found_matching')
            if packet and completed:
                db.execute("UPDATE messages SET processed=1 WHERE kind='source_offer' AND application=? AND client=? AND identity=?", (app, client, packet))

    def validate_event_reference(self, db, value, app, client):
        payload = value['payload']
        if value['revision'] == 1 and value['previous_event_id'] is not None or value['revision'] > 1 and value['previous_event_id'] is None:
            raise ExchangeError('invalid_request')
        packet = payload.get('packet_id')
        if packet and not db.execute("SELECT 1 FROM messages WHERE kind='source_offer' AND application=? AND client=? AND identity=?", (app, client, packet)).fetchone():
            raise ExchangeError('invalid_request')
        if value['previous_event_id']:
            predecessor = db.execute("SELECT body FROM messages WHERE kind='event' AND identity=? AND application=? AND client=?", (value['previous_event_id'], app, client)).fetchone()
            if predecessor:
                prior = json.loads(predecessor['body'])
                if prior['evaluation_id'] != value['evaluation_id'] or prior['revision'] != value['revision'] - 1:
                    raise ExchangeError('invalid_request')
        prior = db.execute("SELECT body FROM messages WHERE kind='event' AND application=? AND client=? AND json_extract(body,'$.evaluation_id')=? AND json_extract(body,'$.revision')=?", (app, client, value['evaluation_id'], value['revision'])).fetchone()
        if prior:
            raise ExchangeError('idempotency_conflict', 409)

    def consumer(self, db, principal, kind, value, app, client, now):
        direction = 'sources' if kind.startswith('source') else 'events'
        if value['broker_generation'] != self.generation(db):
            raise ExchangeError('stale_lease', 409)
        if principal.get('inbox_ids', {}).get(direction) != value['inbox_id']:
            raise ExchangeError('forbidden', 403)
        db.execute('INSERT INTO consumer_contacts VALUES(?,?,?,?,?,?) ON CONFLICT(principal,kind,application,client) DO UPDATE SET inbox=excluded.inbox,last_contact=excluded.last_contact',
                   (principal['id'], direction, app, client, value['inbox_id'], now))

    def claim(self, db, principal, kind, value, operation, app, client, now):
        self.consumer(db, principal, kind, value, app, client, now)
        source = kind == 'source_claim'
        rows = db.execute('''SELECT m.* FROM messages m LEFT JOIN deliveries d ON d.message=m.id AND d.consumer=?
            WHERE m.kind=? AND m.application=? AND m.client=? AND (d.message IS NULL OR (d.acked IS NULL AND d.lease_end<=?))
            AND (m.expires IS NULL OR m.expires>?) ORDER BY m.created,m.id LIMIT ?''',
            (principal['id'], 'source_offer' if source else 'event', app, client, now, now, value['limit'])).fetchall()
        items = []
        generation = self.generation(db)
        for row in rows:
            token, end = secrets.token_urlsafe(32), now + value['lease_seconds']
            item = {'delivery_id': row['id'], 'lease_token': token, 'lease_expires_at': iso(end),
                    'broker_generation': generation, 'offer' if source else 'event': json.loads(row['body'])}
            if len(encode({'items': items + [item], 'retry_after_seconds': 60})) > MAX_RESPONSE:
                break
            db.execute('INSERT INTO deliveries VALUES(?,?,?,?,?,?,NULL,NULL) ON CONFLICT(message,consumer) DO UPDATE SET inbox=excluded.inbox,generation=excluded.generation,token=excluded.token,lease_end=excluded.lease_end',
                       (row['id'], principal['id'], value['inbox_id'], generation, token, end))
            items.append(item)
        return 200, {'items': items, 'retry_after_seconds': 60 if not items else 0}, operation

    def receipt(self, db, principal, kind, route, value, operation, app, client, now):
        self.consumer(db, principal, kind, value, app, client, now)
        identity = route.split('/')[2]
        row = db.execute('SELECT d.*,m.application,m.client,m.kind FROM deliveries d JOIN messages m ON m.id=d.message WHERE d.message=? AND d.consumer=?', (identity, principal['id'])).fetchone()
        if not row or row['application'] != app or row['client'] != client or row['kind'] != ('source_offer' if kind == 'source_receipt' else 'event'):
            raise ExchangeError('not_found', 404)
        if row['inbox'] != value['inbox_id'] or row['generation'] != value['broker_generation'] or not secrets.compare_digest(row['token'], value['lease_token']):
            raise ExchangeError('stale_lease', 409)
        if row['acked'] is not None:
            if bytes(row['receipt']) != encode(value):
                raise ExchangeError('idempotency_conflict', 409)
            acknowledged = row['acked']
        else:
            if row['lease_end'] <= now:
                raise ExchangeError('stale_lease', 409)
            db.execute('UPDATE deliveries SET acked=?,receipt=? WHERE message=? AND consumer=?', (now, encode(value), identity, principal['id']))
            if kind == 'source_receipt' and value['disposition'] in ('policy_refused', 'expired'):
                db.execute('UPDATE messages SET processed=1 WHERE id=?', (identity,))
            acknowledged = now
        return 200, {'operation_id': operation, 'delivery_id': identity, 'state': 'acknowledged', 'acknowledged_at': iso(acknowledged)}, identity

    def operation(self, principal, identity):
        if 'operations:read' not in principal['scopes']:
            raise ExchangeError('forbidden', 403)
        with self.connection() as db:
            row = db.execute('SELECT * FROM operations WHERE principal=? AND id=?', (principal['id'], identity)).fetchone()
            if not row:
                raise ExchangeError('not_found', 404)
            return {'operation_id': identity, 'state': 'committed', 'resource_id': row['resource'],
                    'result_type': row['kind'], 'recorded_at': iso(row['created']), 'method': 'POST',
                    'route': row['route'], 'request_sha256': row['sha256'], 'status_code': row['status'],
                    'response': json.loads(row['response'])}

    def status(self, principal):
        if 'status:read' not in principal['scopes']:
            raise ExchangeError('forbidden', 403)
        now, pending, events, held, oldest, contact = self.clock(), 0, 0, 0, None, None
        with self.connection() as db:
            if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ExchangeError('temporarily_unavailable', 503, True, 60)
            for scope in principal['clients']:
                app, client = scope['application'], scope['client']
                rows = db.execute('''SELECT m.kind,m.created FROM messages m WHERE m.application=? AND m.client=? AND
                    ((m.kind='source_offer' AND m.processed=0) OR (m.kind='event' AND NOT EXISTS(SELECT 1 FROM deliveries d WHERE d.message=m.id AND d.acked IS NOT NULL)))''', (app, client)).fetchall()
                held += db.execute("SELECT count(*) FROM messages WHERE kind='source_offer' AND application=? AND client=? AND processed=0 AND expires<=?", (app, client, now)).fetchone()[0]
                held += db.execute("SELECT count(*) FROM projection WHERE application=? AND client=? AND (json_extract(payload,'$.state')='uncertain' OR json_extract(payload,'$.readback.result') IN ('unavailable','found_conflict'))", (app, client)).fetchone()[0]
                for row in rows:
                    pending += row['kind'] == 'source_offer'
                    events += row['kind'] == 'event'
                    oldest = row['created'] if oldest is None else min(oldest, row['created'])
                for row in db.execute('SELECT last_contact FROM consumer_contacts WHERE application=? AND client=?', (app, client)):
                    contact = row[0] if contact is None else max(contact, row[0])
            return {'schema_version': self.contract.version, 'checked_at': iso(now), 'observed_through': iso(now),
                    'broker_generation': self.generation(db), 'status': 'healthy', 'source_pending': pending,
                    'events_pending': events, 'held_count': held, 'oldest_pending_seconds': None if oldest is None else max(0, int(now - oldest)),
                    'last_consumer_contact': None if contact is None else iso(contact)}

    def backup(self, destination):
        target = Path(destination)
        if target.resolve() == self.path.resolve() or target.exists():
            raise ValueError('Backup must use a new private destination')
        target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        with self.connection() as db, sqlite3.connect(target) as dest:
            db.backup(dest)
            if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup integrity failure')
        with target.open('rb') as f:
            os.fsync(f.fileno())
