#!/usr/bin/env python3
import argparse
import json
import sys
from client import request, key_for

p = argparse.ArgumentParser(description='Read-only public API health/auth checks; no generation.')
p.add_argument('--project', choices=['habigoal', 'classscout'], required=True)
a = p.parse_args()
checks = []
for label, key, expected in [('missing_key', None, 401), ('invalid_key', 'invalid-test-key', 401), (a.project, key_for(a.project), 200)]:
    status, data, seconds = request('/models', key)
    checks.append({'check': label, 'status': status, 'expected': expected, 'seconds': seconds,
                   'passed': status == expected, 'models': [x.get('id') for x in data.get('data', [])]})
print(json.dumps(checks, indent=2))
sys.exit(0 if all(c['passed'] for c in checks) else 1)
