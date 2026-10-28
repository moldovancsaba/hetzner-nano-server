"""Failure/recovery emails to the configured operator, with stable retry keys."""
import datetime
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo


def email_payload(changes, settings):
    lines = ['Haho inference API operational alert', '']
    for change in changes:
        when = datetime.datetime.fromtimestamp(change['at'], ZoneInfo('Europe/Budapest')).isoformat()
        lines += [when+' — '+change['state'].upper()+' — '+change['severity'], change['message'], '']
    lines += ['Inspect the authenticated service queue and private server watchdog before recovery.',
              'This message contains operational metadata only; no request content or credentials.']
    recovery = all(change['state']=='recovered' for change in changes)
    return {'from': settings['MONITOR_EMAIL_FROM'], 'to':[settings['MONITOR_EMAIL_TO']],
            'subject':'[Haho API] '+('Recovered' if recovery else 'Operational failure')+' — '+settings['MONITOR_INSTANCE'],
            'text':'\n'.join(lines)}


def send_email(payload, key, idempotency_key):
    request = urllib.request.Request('https://api.resend.com/emails', data=json.dumps(payload).encode(),
        headers={'Content-Type':'application/json','Authorization':'Bearer '+key,
                 'Idempotency-Key':idempotency_key,'User-Agent':'Haho-Operational-Monitor/1.0'})
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.load(response)
        if not isinstance(result.get('id'),str):
            raise ValueError('Email provider did not confirm acceptance')


def deliver_pending(state, previous, settings=None, sender=send_email, now=None):
    settings = os.environ if settings is None else settings
    now = time.time() if now is None else now
    notification = dict(previous.get('notification', {}))
    state['notification'] = notification
    if settings.get('MONITOR_EMAIL_ENABLED', 'false').lower() != 'true':
        notification.update(configured=False, enabled=False, last_error=None)
        return
    notification['enabled'] = True
    required = ['MONITOR_EMAIL_TO','MONITOR_EMAIL_FROM','MONITOR_EMAIL_KEY','MONITOR_INSTANCE']
    notification['configured'] = all(settings.get(name) for name in required)
    changes = [change for change in state['changes'] if change['revision']>notification.get('delivered_through',0)]
    if not changes or now < notification.get('retry_at',0):
        return
    if not notification['configured']:
        notification['last_error']='email_not_configured'
        return
    payload = email_payload(changes, settings)
    identity = 'haho-monitor-'+hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    try:
        sender(payload, settings['MONITOR_EMAIL_KEY'], identity)
        notification.update(delivered_through=max(change['revision'] for change in changes),
                            last_accepted_at=now,last_error=None,retry_at=0,attempts=0)
    except Exception as error:
        attempts = notification.get('attempts',0)+1
        code = 'http_'+str(error.code) if isinstance(error, urllib.error.HTTPError) else type(error).__name__
        notification.update(last_error=code,attempts=attempts,retry_at=now+min(1800,30*2**min(attempts-1,6)))
