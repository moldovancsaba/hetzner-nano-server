"""Loopback-only bounded machine HTTP service; no browser or catalog capabilities."""
import argparse
import fcntl
import hashlib
import hmac
import json
import logging
import os
import re
import socket
import sqlite3
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .contract import CLIENTS, ExchangeError, MAX_REQUEST, encode
from .store import Store

LOG = logging.getLogger('source_exchange')


class Application:
    def __init__(self, store, principals, *, source_admission=True, claims_enabled=True):
        self.store = store
        self.source_admission, self.claims_enabled = source_admission, claims_enabled
        self.principals = principals
        self.rate_lock = threading.Lock()
        self.rates = {}
        ids, tokens = set(), set()
        for p in principals:
            if p['id'] in ids or p['token_sha256'] in tokens or not re.fullmatch('[a-f0-9]{64}', p['token_sha256']):
                raise ValueError('Invalid or duplicate principal')
            ids.add(p['id']); tokens.add(p['token_sha256'])
            for scope in p['clients']:
                if scope['client'] not in CLIENTS.get(scope['application'], set()):
                    raise ValueError('Invalid principal client scope')

    def authenticate(self, authorization, origin=None):
        if origin is not None or not authorization or not authorization.startswith('Bearer '):
            raise ExchangeError('unauthorized', 401)
        token = authorization[7:]
        if len(token) < 32 or len(token) > 512:
            raise ExchangeError('unauthorized', 401)
        value = hashlib.sha256(token.encode()).hexdigest()
        principal = None
        for row in self.principals:
            if hmac.compare_digest(value, row['token_sha256']):
                principal = row
        if principal is None:
            raise ExchangeError('unauthorized', 401)
        return principal

    def dispatch(self, method, route, headers, raw=b''):
        principal = self.authenticate(headers.get('Authorization'), headers.get('Origin'))
        with self.rate_lock:
            now = time.monotonic()
            tokens, previous = self.rates.get(principal['id'], (20.0, now))
            tokens = min(20.0, tokens + max(0.0, now - previous))
            if tokens < 1:raise ExchangeError('capacity_hold', 429, True, 5)
            self.rates[principal['id']] = (tokens - 1, now)
        if method == 'GET' and route == '/snapshot':
            if 'status:read' not in principal['scopes']:raise ExchangeError('forbidden',403)
            from .snapshot import snapshot
            return 200, encode(snapshot(self.store,principal))
        if method == 'GET' and route == '/status':
            return 200, encode(self.store.status(principal))
        if method == 'GET' and re.fullmatch(r'/operations/[a-f0-9-]{36}', route):
            return 200, encode(self.store.operation(principal, route.rsplit('/', 1)[1]))
        if method == 'POST':
            if route == '/source-offers' and not self.source_admission:
                raise ExchangeError('capacity_hold', 429, True, 300)
            if route.endswith('/claim') and not self.claims_enabled:
                raise ExchangeError('temporarily_unavailable', 503, True, 60)
            if headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
                raise ExchangeError('invalid_request', 415)
            return self.store.mutation(principal, headers.get('Idempotency-Key'), route, raw)
        raise ExchangeError('not_found', 404)


class Handler(BaseHTTPRequestHandler):
    server_version = 'SourceExchange'
    sys_version = ''

    def log_message(self, *_):
        pass

    def handle_one_request(self):
        self.connection.settimeout(10)
        def expire():
            try:self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:pass
        deadline = threading.Timer(30, expire)
        deadline.daemon = True
        deadline.start()
        try:super().handle_one_request()
        finally:deadline.cancel()

    def respond(self, status, body, retry_after=0):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Connection', 'close')
        if retry_after:
            self.send_header('Retry-After', str(retry_after))
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def handle_request(self):
        request_id = str(uuid.uuid4())
        status = 500
        try:
            if len(self.path) > 256 or '?' in self.path or not self.path.startswith('/integrations/v1/'):
                raise ExchangeError('not_found', 404)
            # Authenticate before reading a body, and refuse ambiguous HTTP framing.
            self.server.app.authenticate(self.headers.get('Authorization'), self.headers.get('Origin'))
            if self.headers.get('Transfer-Encoding') is not None or len(self.headers.get_all('Content-Length', [])) > 1 or len(self.headers.get_all('Authorization', [])) != 1 or len(self.headers.get_all('Idempotency-Key', [])) > 1:
                raise ExchangeError('invalid_request', 400)
            raw = b''
            if self.command == 'POST':
                try:
                    length = int(self.headers.get('Content-Length', '-1'))
                except ValueError:
                    raise ExchangeError('invalid_request', 400) from None
                if not 0 < length <= MAX_REQUEST:
                    raise ExchangeError('invalid_request', 413)
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ExchangeError('invalid_request', 400)
            route = self.path[len('/integrations/v1'):]
            status, body = self.server.app.dispatch(self.command, route, self.headers, raw)
            self.respond(status, body)
        except ExchangeError as e:
            status = e.status
            self.respond(status, encode({'code': e.code, 'request_id': request_id, 'retryable': e.retryable, 'retry_after_seconds': e.retry_after}), e.retry_after)
        except (sqlite3.Error, OSError, RuntimeError):
            status = 503
            self.respond(status, encode({'code': 'temporarily_unavailable', 'request_id': request_id, 'retryable': True, 'retry_after_seconds': 60}), 60)
        finally:
            LOG.info('%s', json.dumps({'request_id': request_id, 'status': status, 'method': self.command}))

    do_GET = do_POST = do_PUT = do_DELETE = do_OPTIONS = handle_request


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, address, app):
        if address[0] != '127.0.0.1':
            raise ValueError('Source exchange binds only to IPv4 loopback')
        self.app = app
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.slots.acquire(False):
            request.close()
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    path = Path(args.config)
    if path.stat().st_mode & 0o077:
        raise SystemExit('Configuration must be private (0600)')
    config = json.loads(path.read_text())
    os.umask(0o077)
    store = Store(config['database'])
    lease = os.open(Path(config['database']).with_suffix('.service.lock'), os.O_CREAT | os.O_RDWR, 0o600)
    try:fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('Broker already running')
    app = Application(store, config['principals'], source_admission=config.get('source_admission',False), claims_enabled=config.get('claims_enabled',False))
    logging.basicConfig(level=logging.INFO)
    Server(('127.0.0.1', config.get('port', 9091)), app).serve_forever(poll_interval=0.5)


if __name__ == '__main__':
    main()
