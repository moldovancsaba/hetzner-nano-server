#!/usr/bin/env python3
"""Sequential synthetic smoke benchmark, not a load test or product-quality evaluation."""
import argparse
from datetime import datetime, timezone
import json
import math
import statistics
import sys
from client import ROOT, MODEL, request, key_for

p = argparse.ArgumentParser()
p.add_argument('--project', choices=['habigoal', 'classscout'], required=True)
p.add_argument('--runs', type=int, default=5)
a = p.parse_args()
if not 1 <= a.runs <= 50:
    p.error('--runs must be between 1 and 50; avoid accidental load')
key = key_for(a.project)
tests = [
 ('classification', 'Return JSON only with category. Allowed categories are learning, fitness, other. Task: study Spanish vocabulary.', lambda d: d.get('category') == 'learning'),
 ('extraction', 'Return JSON only with minutes as an integer. Text: Practice piano for 15 minutes.', lambda d: type(d.get('minutes')) is int and d['minutes'] == 15),
 ('arithmetic', 'Return JSON only with total as an integer. There are 2 morning classes and 3 evening classes. How many classes?', lambda d: type(d.get('total')) is int and d['total'] == 5),
 ('classification', 'Return JSON only with category. Allowed categories are learning, fitness, other. Task: walk outside for exercise.', lambda d: d.get('category') == 'fitness'),
 ('extraction', 'Return JSON only with language as a lowercase string. Text: I want to learn French.', lambda d: d.get('language') == 'french'),
]
rows=[]
for i in range(a.runs):
    name, prompt, validate = tests[i % len(tests)]
    payload={'model':MODEL,'messages':[{'role':'user','content':prompt}], 'reasoning_effort':'none',
             'response_format':{'type':'json_object'},'temperature':0,'max_tokens':96,'stream':False}
    status, data, seconds = request('/chat/completions', key, payload)
    content = data.get('choices',[{}])[0].get('message',{}).get('content','')
    valid=False; passed=False
    try:
        decoded=json.loads(content); valid=True; passed=isinstance(decoded,dict) and validate(decoded)
    except (ValueError,TypeError):
        pass
    rows.append({'test':name,'iteration':i+1,'http_status':status,'seconds':seconds,'json_valid':valid,
                 'passed':status==200 and passed,'response':content,'usage':data.get('usage',{}),
                 'error_type':data.get('error_type')})
latencies=sorted(r['seconds'] for r in rows if r['http_status']==200)
report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'project':a.project,'model':MODEL,
        'method':'sequential synthetic smoke tests; cache/load state uncontrolled; not production accuracy',
        'runs':rows,'summary':{'count':len(rows),'passed':sum(r['passed'] for r in rows),
        'json_valid':sum(r['json_valid'] for r in rows),'p50_seconds':statistics.median(latencies) if latencies else None,
        'p95_seconds_nearest_rank':latencies[math.ceil(.95*len(latencies))-1] if latencies else None}}
path=ROOT/'results'/('benchmark-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'file':str(path),'summary':report['summary']},indent=2))
sys.exit(0 if all(r['passed'] for r in rows) else 1)
