"""Bounded operational metadata. Request content and credentials have no columns."""
import collections
import math
from pathlib import Path
import sqlite3
import threading
import time

TENANTS = {'classscout', 'habigoal', 'camera', 'pandora', 'paperclip', 'unknown', 'operator'}
TASKS = {'text_chat_hu', 'text_chat', 'image_recognition', 'image_moderation'}
EVENTS = {'http', 'admitted', 'finished', 'acknowledged', 'cancelled', 'result_expired'}
COLUMNS = ('at', 'event', 'tenant', 'purpose', 'task', 'model', 'status', 'http_status',
           'route', 'method', 'error_code', 'queue_ms', 'switch_ms', 'load_ms',
           'inference_ms', 'duration_ms', 'disconnected')
RETENTION_SECONDS = 30 * 86400
MAX_EVENTS = 200000


def route_name(path):
    path = str(path).split('?', 1)[0]
    if path in {'/v1/models', '/v1/job-types', '/v1/jobs', '/v1/moderation/jobs',
                '/v1/chat/completions', '/v1/queue', '/v1/moderation/health', '/v1/usage'}:
        return path
    for prefix in ['/v1/jobs/', '/v1/moderation/jobs/']:
        if path.startswith(prefix):
            return prefix + ':id'
    return 'internal' if path.startswith('/internal/') else 'other'


def is_liveness_poll(method, route, purpose, http_status):
    """True for the 30-second status polls of the host monitor and the external watchdog.

    Both request GET /v1/queue marked as a test: the monitor with a project key (answered 200), the
    watchdog without one (answered 401). Together they would write about 5,800 events a day and fill most of
    MAX_EVENTS, so Metrics.record does not store them. A production-marked request, any other route and any
    other status (including 429 and 5xx) are still stored.
    """
    return method == 'GET' and route == '/v1/queue' and purpose == 'test' and http_status in {200, 401}


def distribution(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return {'samples': 0, 'p50_ms': None, 'p95_ms': None, 'max_ms': None}
    return {'samples': len(values), 'p50_ms': round(values[(len(values)-1)//2], 2),
            'p95_ms': round(values[math.ceil(.95*len(values))-1], 2), 'max_ms': round(values[-1], 2)}


class Metrics:
    def __init__(self, path, clock=time.time):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self.lock = threading.RLock()
        self.failures = 0
        self.db = sqlite3.connect(str(path), timeout=.25, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA journal_size_limit=4194304')
        self.db.execute('PRAGMA wal_autocheckpoint=256')
        self.db.execute('PRAGMA max_page_count=16384')
        self.db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value REAL)')
        self.db.execute('INSERT OR IGNORE INTO settings VALUES (?, ?)', ('started_at', self.clock()))
        self.db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, at REAL, event TEXT, '
                        'tenant TEXT, purpose TEXT, task TEXT, model TEXT, status TEXT, http_status INTEGER, '
                        'route TEXT, method TEXT, error_code TEXT, queue_ms REAL, switch_ms REAL, load_ms REAL, '
                        'inference_ms REAL, duration_ms REAL, disconnected INTEGER)')
        self.db.execute('CREATE INDEX IF NOT EXISTS events_window ON events(at, tenant, purpose)')
        self.db.commit()
        self.writes = 0
        self.last_prune = 0
        self.prune()

    def prune(self):
        with self.lock:
            boundary = self.db.execute('SELECT id FROM events ORDER BY id DESC LIMIT 1 OFFSET ?', (MAX_EVENTS,)).fetchone()
            removed = self.db.execute('SELECT MAX(at) FROM events WHERE at < ? OR id <= ?',
                                      (self.clock()-RETENTION_SECONDS, boundary[0] if boundary else -1)).fetchone()[0]
            if removed is not None:
                self.db.execute('INSERT INTO settings VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=MAX(value, excluded.value)',
                                ('discarded_through', removed))
            self.db.execute('DELETE FROM events WHERE at < ?', (self.clock()-RETENTION_SECONDS,))
            self.db.execute('DELETE FROM events WHERE id <= COALESCE((SELECT id FROM events '
                            'ORDER BY id DESC LIMIT 1 OFFSET ?), -1)', (MAX_EVENTS,))
            self.db.commit()
            self.last_prune = self.clock()

    @classmethod
    def readonly(cls, path):
        obj = cls.__new__(cls)
        obj.path, obj.clock, obj.failures = Path(path), time.time, None
        obj.lock = threading.RLock()
        obj.db = sqlite3.connect(obj.path.resolve().as_uri()+'?mode=ro', uri=True, timeout=1,
                                 check_same_thread=False)
        return obj

    def record(self, event, tenant='unknown', purpose='production', **fields):
        """Store one event; False when it was refused or not stored (unknown event, liveness poll, write failure).

        Only a write failure counts toward `failures`.
        """
        try:
            if event not in EVENTS:
                return False
            if event == 'http' and is_liveness_poll(fields.get('method'), fields.get('route'), purpose, fields.get('http_status')):
                return False
            row = {'at': self.clock(), 'event': event,
                   'tenant': tenant if tenant in TENANTS else 'unknown',
                   'purpose': purpose if purpose in {'test', 'production'} else 'invalid'}
            for key in ['task', 'model', 'status', 'http_status', 'route', 'method', 'error_code',
                        'queue_ms', 'switch_ms', 'load_ms', 'inference_ms', 'duration_ms', 'disconnected']:
                value = fields.get(key)
                if key.endswith('_ms'):
                    value = round(float(value), 3) if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 else None
                elif key in {'http_status', 'disconnected'}:
                    value = int(value) if isinstance(value, (bool, int)) else None
                elif key == 'task':
                    value = value if value in TASKS else None
                else:
                    value = value[:200] if isinstance(value, str) else None
                row[key] = value
            with self.lock:
                self.db.execute('INSERT INTO events ('+','.join(COLUMNS)+') VALUES ('+
                                ','.join('?' for _ in COLUMNS)+')', [row.get(k) for k in COLUMNS])
                self.db.commit()
                self.writes += 1
                if self.writes % 100 == 0 or self.clock()-self.last_prune >= 3600:
                    self.prune()
            return True
        except (sqlite3.Error, OSError, ValueError, TypeError):
            try:
                with self.lock:
                    self.db.rollback()
            except sqlite3.Error:
                pass
            self.failures += 1
            return False

    def summary(self, hours=12, tenant=None, now=None):
        if not 0 < hours <= 720:
            raise ValueError('Window must be positive and at most 720 hours')
        now = self.clock() if now is None else now
        with self.lock:
            started = self.db.execute('SELECT value FROM settings WHERE key=?', ('started_at',)).fetchone()[0]
            sql = 'SELECT '+','.join(COLUMNS)+' FROM events WHERE at >= ? AND at <= ?'
            parameters = [now-hours*3600, now]
            if tenant is not None:
                sql += ' AND tenant=?'
                parameters.append(tenant)
            groups = {}
            for values in self.db.execute(sql, parameters):
                row = dict(zip(COLUMNS, values))
                key = (row['tenant'], row['purpose'])
                if key not in groups:
                    groups[key] = {'project': key[0], 'purpose': key[1], 'admitted':0, 'completed':0,
                        'failed':0, 'acknowledged':0, 'cancelled':0, 'unacknowledged_expired_results':0,
                        'model_switches':0, 'http_requests':0, 'http_statuses':collections.Counter(),
                        'errors':collections.Counter(), 'models':collections.Counter(), 'tasks':collections.Counter(),
                        'client_disconnects':0, 'timings':{name:[] for name in
                            ['queue_ms','switch_ms','load_ms','inference_ms','duration_ms']}, 'latest_event_at':0}
                group = groups[key]
                group['latest_event_at'] = max(group['latest_event_at'], row['at'])
                if row['error_code']:
                    group['errors'][row['error_code']] += 1
                if row['event'] == 'http':
                    group['http_requests'] += 1
                    group['http_statuses'][str(row['http_status'])] += 1
                    group['client_disconnects'] += bool(row['disconnected'])
                elif row['event'] == 'admitted':
                    group['admitted'] += 1
                    if row['model']:group['models'][row['model']] += 1
                    if row['task']:group['tasks'][row['task']] += 1
                elif row['event'] == 'finished':
                    if row['status'] in {'completed','failed'}:group[row['status']] += 1
                    group['model_switches'] += (row['switch_ms'] or 0)>0
                    for name in group['timings']:
                        if row[name] is not None:group['timings'][name].append(row[name])
                elif row['event'] in {'acknowledged','cancelled'}:
                    group[row['event']] += 1
                elif row['event'] == 'result_expired':
                    group['unacknowledged_expired_results'] += 1
            oldest = self.db.execute('SELECT MIN(at) FROM events').fetchone()[0]
            discarded = self.db.execute('SELECT value FROM settings WHERE key=?', ('discarded_through',)).fetchone()
        reports = []
        for key in sorted(groups):
            report = groups[key]
            report['timings'] = {name:distribution(values) for name, values in report['timings'].items()}
            reports.append(report)
        return {'schema_version': 'operational-usage.v1', 'window_start': now-hours*3600,
                'window_end': now, 'tracking_started_at': started, 'oldest_retained_event_at': oldest,
                'full_window_tracked': started <= now-hours*3600 and (not discarded or discarded[0] < now-hours*3600),
                'retention_days': 30, 'event_cap': MAX_EVENTS, 'write_failures_since_restart': self.failures,
                'projects': reports,
                'notes': ['Purpose is declared by the caller; unmarked tests look like production.',
                          'Test-marked GET /v1/queue polls answered 200 or 401 (the host monitor and external watchdog) are not stored.',
                          'Completion proves server output; acknowledgement proves a client deleted its retained result.',
                          'No request bodies, answers, image hashes, job IDs, IPs or credentials are retained.']}

    def close(self):
        with self.lock:
            self.db.close()


class UnavailableMetrics:
    available = False
    failures = 1

    def record(self, *args, **kwargs):
        return False


def open_metrics(path):
    try:
        return Metrics(path)
    except (sqlite3.Error, OSError):
        # Operational analytics must not stop inference or alter the separate model-demand ledger.
        return UnavailableMetrics()
