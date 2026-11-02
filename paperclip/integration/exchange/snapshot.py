"""Bounded aggregate evidence, never raw source bodies or private contact values."""
import json
from .contract import iso


def snapshot(store, principal, window=86400):
    now=store.clock();rows=[]
    with store.connection() as db:
        for scope in principal['clients']:
            app,client=scope['application'],scope['client']
            offered=db.execute("SELECT count(*) FROM messages WHERE kind='source_offer' AND application=? AND client=? AND created>=?",(app,client,now-window)).fetchone()[0]
            deliveries=db.execute("SELECT count(*),min(m.created) FROM messages m WHERE m.kind='source_offer' AND m.application=? AND m.client=? AND m.processed=0",(app,client)).fetchone()
            messages=[json.loads(r[0]) for r in db.execute("SELECT body FROM messages WHERE kind='event' AND application=? AND client=? AND created>=?",(app,client,now-window))]
            evaluations={};confirmed=set();published=set();accepted=set();qualified=set();reasons={}
            measured_qualification=False
            for event in messages:
                payload=event['payload'];evaluation=event['evaluation_id']
                if evaluation not in evaluations or event['revision']>evaluations[evaluation]['revision']:evaluations[evaluation]=event
                operation=payload.get('destination_operation_id')
                if payload.get('state')=='submission_accepted' and operation:accepted.add(operation)
                if 'qualified' in payload and payload['qualified'] is not None:
                    measured_qualification=True
                    if payload['qualified']:qualified.add(payload.get('candidate_ref',evaluation))
                if payload['event_type']=='delivery_readback':
                    readback=payload['readback']
                    identity=(operation,readback['destination_type'],readback['destination_id'])
                    if readback['result']=='found_matching' and readback['checked_fields']:confirmed.add(identity)
                    if readback['result']=='found_matching' and readback['publication']=='public' and readback['destination_type'] in ('provider','listing'):published.add((readback['destination_type'],readback['destination_id']))
                if payload.get('state')=='rejected':
                    code=payload.get('reason_code','unspecified');reasons[code]=reasons.get(code,0)+1
            latest=max((e['occurred_at'] for e in messages),default=None)
            rows.append({'scope':scope,'paperclip':{'source_offers':offered,'research_examinations':None,'coverage':'source-offers-only'},
                         'exchange':{'unprocessed':deliveries[0],'oldest_pending_seconds':None if deliveries[1] is None else max(0,int(now-deliveries[1]))},
                         'openclaw':{'qualified':len(qualified) if measured_qualification else None,'accepted_operations':len(accepted),
                                     'destination_confirmed':len(confirmed),'public_listings':len(published),
                                     'uncertain_evaluations':sum(e['payload'].get('state')=='uncertain' for e in evaluations.values()),
                                     'rejections':dict(sorted(reasons.items(),key=lambda kv:(-kv[1],kv[0]))[:10]),
                                     'observed_through':latest,'coverage':'events-only' if messages else 'not_measured'},
                         'spend':{'gbp':None,'basis':'not_measured'},'next_action':None})
    return {'schema_version':'1.1','as_of':iso(now),'observed_through':iso(now),'window_seconds':window,
            'coverage':'partial','clients':rows,'status':store.status(principal)}
