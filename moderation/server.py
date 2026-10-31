"""Image normalization and inference for moderation, plus the retired standalone job service.

The live gateway imports only normalize_image and infer from this module (gateway/server.py). The Jobs,
Handler and Server classes below are the original standalone service on port 8089; its unit has been
disabled since the gateway cutover and they are kept only for rollback.
"""
import base64
import binascii
import hashlib
import hmac
import io
import json
import os
import queue
import secrets
import threading
import time
import urllib.request
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image, ImageOps, UnidentifiedImageError
try:
    from .policy import CATEGORIES, MODEL, PROMPT, SCHEMA, VERSION
except ImportError:
    from policy import CATEGORIES, MODEL, PROMPT, SCHEMA, VERSION

MAX_BODY = 6 * 1024 * 1024
MAX_IMAGE = 4 * 1024 * 1024
MAX_PIXELS = 16_000_000
TTL = 900
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
warnings.simplefilter('error', Image.DecompressionBombWarning)


def normalize_image(encoded):
    if not isinstance(encoded, str) or len(encoded) > (MAX_IMAGE * 4 // 3 + 4):
        raise ValueError('image_base64 must contain at most 4 MiB of image bytes')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError('Invalid base64') from None
    if not raw or len(raw) > MAX_IMAGE:
        raise ValueError('Image exceeds 4 MiB or is empty')
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise ValueError('Only JPEG, PNG and WebP are supported')
            if source.width * source.height > MAX_PIXELS or getattr(source, 'n_frames', 1) != 1:
                raise ValueError('Use one still image, maximum 16 megapixels')
            source.load()
            image = ImageOps.exif_transpose(source)
            image.thumbnail((640, 640))
            if 'A' in image.getbands():
                rgba = image.convert('RGBA')
                background = Image.new('RGBA', rgba.size, 'white')
                background.alpha_composite(rgba)
                image = background.convert('RGB')
            else:
                image = image.convert('RGB')
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=88)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('Invalid, unsupported or oversized image') from None
    normalized = output.getvalue()
    return normalized, hashlib.sha256(raw).hexdigest(), hashlib.sha256(normalized).hexdigest()


def infer(image, model=MODEL, think=None):
    body = {'model': model, 'prompt': PROMPT,
            'images': [base64.b64encode(image).decode()], 'format': SCHEMA,
            'stream': False, 'keep_alive': '1m',
            'options': {'num_ctx': 2048, 'num_batch': 32, 'num_predict': 256, 'temperature': 0}}
    if think is not None:
        body['think'] = think
    request = urllib.request.Request('http://127.0.0.1:11434/api/generate',
                                     data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.load(response)
    if not data.get('done') or data.get('done_reason') == 'length':
        raise ValueError('Incomplete model output')
    parsed = json.loads(data['response'])
    if not isinstance(parsed, dict) or set(parsed) != {'categories', 'evidence'}:
        raise ValueError('Invalid model output')
    cats = parsed['categories']
    if not isinstance(cats, dict) or set(cats) != set(CATEGORIES):
        raise ValueError('Invalid category output')
    if any(value is not None and type(value) is not bool for value in cats.values()):
        raise ValueError('Invalid category type')
    if not isinstance(parsed['evidence'], str) or len(parsed['evidence']) > 2000:
        raise ValueError('Invalid evidence')
    flags = [category for category in CATEGORIES if cats[category] is True]
    return {'schema_version': VERSION, 'model': model, 'review_required': True,
            'automated_decision': 'none',
            'signal': 'flagged' if flags else 'uncertain' if None in cats.values() else 'no_flags_detected',
            'flags': flags,
            'categories': {category: ('detected' if value is True else 'not_detected' if value is False else 'uncertain')
                           for category, value in cats.items()},
            'evidence': parsed['evidence'],
            'limitations': 'Experimental screening; missed content and false alarms are known. No flags is not approval.',
            'timing': {'model_load_seconds': round(data.get('load_duration', 0) / 1e9, 4),
                       'inference_seconds': round(data.get('total_duration', 0) / 1e9, 4)}}


class Jobs:
    def __init__(self, inference=infer):
        self.inference = inference
        self.lock = threading.Lock()
        self.rows = {}
        self.pending = queue.Queue(maxsize=3)
        threading.Thread(target=self.work, daemon=True).start()

    def clean(self):
        now = time.time()
        self.rows = {key: row for key, row in self.rows.items()
                     if row['status'] in {'queued', 'running'} or now - row['finished_at'] < TTL}

    def submit(self, image, original_hash, normalized_hash, idempotency=None):
        with self.lock:
            self.clean()
            if idempotency:
                for job_id, row in self.rows.items():
                    if row.get('_idempotency') == idempotency:
                        if row['image_sha256'] != original_hash:
                            return None, 'conflict'
                        return job_id, None
            if len(self.rows) >= 32 or self.pending.full():
                return None, 'busy'
            job_id = secrets.token_urlsafe(24)
            self.rows[job_id] = {'id': job_id, 'status': 'queued', 'created_at': time.time(),
                                 'image_sha256': original_hash, 'normalized_sha256': normalized_hash,
                                 '_idempotency': idempotency}
            self.pending.put_nowait((job_id, image))
            return job_id, None

    def read(self, job_id):
        with self.lock:
            self.clean()
            row = self.rows.get(job_id)
            return {key: value for key, value in row.items() if not key.startswith('_')} if row else None

    def work(self):
        while True:
            job_id, image = self.pending.get()
            with self.lock:
                self.rows[job_id]['status'] = 'running'
                self.rows[job_id]['started_at'] = time.time()
            failed = False
            try:
                result = self.inference(image)
                update = {'status': 'completed', 'result': result}
            except Exception:
                failed = True
                update = {'status': 'failed', 'error': {'code': 'analysis_unavailable',
                          'message': 'Analysis failed or timed out. Keep human review pending; retry later.'},
                          'review_required': True}
            finally:
                image = None
            with self.lock:
                self.rows[job_id].update(update, finished_at=time.time())
            self.pending.task_done()
            # An upstream HTTP timeout need not cancel generation. Allow recovery before the next job.
            if failed:
                time.sleep(30)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *args):
        pass

    def send(self, status, data, **headers):
        body = json.dumps(data).encode()
        self.send_response(status)
        for name, value in {'Content-Type': 'application/json', 'Cache-Control': 'no-store',
                            'X-Content-Type-Options': 'nosniff', 'Content-Length': str(len(body)),
                            **headers}.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def auth(self):
        expected = 'Bearer ' + self.server.api_key
        if not hmac.compare_digest(self.headers.get('Authorization', '').encode('utf-8'), expected.encode('utf-8')):
            self.send(401, {'error': {'code': 'unauthorized'}})
            return False
        return True

    def do_GET(self):
        if not self.auth():
            return
        if self.path == '/v1/moderation/health':
            return self.send(200, {'status': 'ok', 'schema_version': VERSION, 'model': MODEL,
                                   'queue_depth': self.server.jobs.pending.qsize(),
                                   'review_required': True})
        prefix = '/v1/moderation/jobs/'
        if not self.path.startswith(prefix) or not self.path[len(prefix):] or '/' in self.path[len(prefix):]:
            return self.send(404, {'error': {'code': 'not_found'}})
        row = self.server.jobs.read(self.path[len(prefix):])
        if not row:
            return self.send(404, {'error': {'code': 'job_not_found', 'message': 'Job expired, unknown or lost after restart; resubmit if needed.'}})
        return self.send(200, row)

    def do_POST(self):
        if not self.auth():
            return
        if self.path != '/v1/moderation/jobs':
            return self.send(404, {'error': {'code': 'not_found'}})
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            return self.send(415, {'error': {'code': 'use_application_json'}})
        if not self.server.upload_slot.acquire(blocking=False):
            return self.send(429, {'error': {'code': 'busy'}}, **{'Retry-After': '10'})
        try:
            return self.accept_job()
        finally:
            self.server.upload_slot.release()

    def accept_job(self):
        try:
            if self.headers.get('Transfer-Encoding'):
                raise ValueError('Content-Length required')
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0 or length > MAX_BODY:
                return self.send(413, {'error': {'code': 'request_too_large'}})
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError('Incomplete request')
            payload = json.loads(raw)
            if not isinstance(payload, dict) or set(payload) != {'image_base64'}:
                raise ValueError('Provide exactly image_base64; URLs and metadata are not accepted')
            idempotency = self.headers.get('Idempotency-Key')
            if idempotency and (len(idempotency) > 128 or not idempotency.isascii()):
                raise ValueError('Invalid Idempotency-Key')
            image, original_hash, normalized_hash = normalize_image(payload['image_base64'])
        except (ValueError, TypeError, RecursionError):
            return self.send(400, {'error': {'code': 'invalid_image_request'}})
        job_id, error = self.server.jobs.submit(image, original_hash, normalized_hash, idempotency)
        if error == 'conflict':
            return self.send(409, {'error': {'code': 'idempotency_conflict'}})
        if error:
            return self.send(429, {'error': {'code': 'busy', 'message': 'Retry later; keep human review pending.'}}, **{'Retry-After': '10'})
        return self.send(202, {'id': job_id, 'status_url': '/v1/moderation/jobs/' + job_id,
                               'review_required': True}, Location='/v1/moderation/jobs/' + job_id)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, address, api_key, jobs=None):
        self.api_key = api_key
        self.jobs = jobs or Jobs()
        self.slots = threading.BoundedSemaphore(8)
        self.upload_slot = threading.BoundedSemaphore(1)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


if __name__ == '__main__':
    key = os.environ['CAMERA_MODERATION_API_KEY']
    if len(key) < 32:
        raise RuntimeError('A dedicated strong API key is required')
    Server(('127.0.0.1', 8089), key).serve_forever()
