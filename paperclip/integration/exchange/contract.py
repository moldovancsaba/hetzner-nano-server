"""Validate bounded exchange messages against the single canonical wire schema."""
import hashlib
import ipaddress
import json
import re
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from jsonschema import Draft202012Validator, FormatChecker

SPEC_PATH = Path(__file__).resolve().parent.parent / 'openapi.json'
MAX_REQUEST = 65536
MAX_RESPONSE = 262144
CLIENTS = {'classscout': {'NYC', 'BOS', 'LA'}, 'management': {'padel-africa', 'sportolok'},
           'salesleadgenerator': {'cogmap', 'seyu', 'dvsc'}}


class ExchangeError(Exception):
    def __init__(self, code, status=422, retryable=False, retry_after=0):
        super().__init__(code)
        self.code, self.status = code, status
        self.retryable, self.retry_after = retryable, retry_after


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone required')
    return result.timestamp()


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')


def public_url(value):
    try:
        p = urllib.parse.urlsplit(value)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
            return False
        if any(ord(c) < 33 or ord(c) == 127 for c in value) or '\\' in value:
            return False
        host = p.hostname.rstrip('.').encode('idna').decode().lower()
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
            return False
        try:
            address = ipaddress.ip_address(host)
            if not address.is_global or address.is_multicast or address.is_reserved:
                return False
        except ValueError:
            if '.' not in host:
                return False
        for key, _ in urllib.parse.parse_qsl(p.query):
            if re.search(r'token|password|secret|api.?key|signature|authorization', key, re.I):
                return False
        return True
    except (ValueError, UnicodeError):
        return False


class Contract:
    def __init__(self, path=SPEC_PATH):
        self.spec = json.loads(Path(path).read_text())
        self.version = self.spec['components']['schemas']['SourceOffer']['properties']['schema_version']['const']
        components = self.spec['components']
        self.validators = {name: Draft202012Validator(
            {'$ref': '#/components/schemas/' + name, 'components': components},
            format_checker=FormatChecker()) for name in components['schemas']}

    def parse(self, raw):
        if not isinstance(raw, bytes) or len(raw) > MAX_REQUEST:
            raise ExchangeError('invalid_request', 413)
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError('Duplicate key')
                value[key] = item
            return value
        try:
            result = json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except (ValueError, UnicodeError, RecursionError):
            raise ExchangeError('invalid_request') from None

    def validate(self, name, value):
        if 'schema_version' in value and value['schema_version'] != self.version:
            raise ExchangeError('unsupported_version')
        try:
            self.validators[name].validate(value)
            scope = value.get('scope')
            if scope and scope['client'] not in CLIENTS.get(scope['application'], set()):
                raise ValueError()
            if name == 'SourceOffer':
                start, end = timestamp(value['fetched_at']), timestamp(value['expires_at'])
                recipes = {'factory-visible-text-v1': 'visible_text_sha256', 'raw-http-body-v1': 'raw_body_sha256'}
                if recipes.get(value['extraction_recipe_id']) != value['digest_kind']:
                    raise ValueError()
                if end <= start or end - start > 7 * 86400 or not public_url(value['source_url']):
                    raise ValueError()
                for claim in value['claims']:
                    if not public_url(claim['source_url']):
                        raise ValueError()
            if name == 'OutcomeEvent' and value['payload']['event_type'] == 'delivery_readback':
                r = value['payload']['readback']
                if r['result']=='found_matching' and (not r['checked_fields'] or not r['content_revision']):raise ValueError()
                if r['publication'] == 'public' and (r['destination_type'] not in {'provider', 'listing'} or r['result'] != 'found_matching'):
                    raise ValueError()
        except Exception as exc:
            if isinstance(exc, ExchangeError):
                raise
            raise ExchangeError('invalid_request') from None
        return value
