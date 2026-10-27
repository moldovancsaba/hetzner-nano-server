"""Small standard-library API client; credentials never appear in output."""
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get('LOCAL_AI_BASE_URL', 'https://chatbotapi.haho.ai/v1').rstrip('/')
MODEL = os.environ.get('LOCAL_AI_MODEL', 'granite4:1b-h')

def key_for(project):
    # Explicit project selection always uses its own credential, not an ambiguous shell key.
    return json.loads((ROOT / 'private/api-keys.json').read_text())[project]

def request(path, key=None, payload=None):
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    req = urllib.request.Request(BASE + path, headers=headers,
        data=None if payload is None else json.dumps(payload).encode())
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return response.status, json.load(response), round(time.monotonic()-started, 4)
    except urllib.error.HTTPError as exc:
        return exc.code, {}, round(time.monotonic()-started, 4)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return 0, {'error_type': type(exc).__name__}, round(time.monotonic()-started, 4)
