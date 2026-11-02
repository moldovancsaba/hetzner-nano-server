"""Bounded aggregate evidence and causal delivery history, without source or contact bodies."""
import json
import hashlib
from .contract import iso, timestamp

EVENT_JOIN = """FROM messages m LEFT JOIN projection p ON p.application=m.application AND p.client=m.client
 AND p.evaluation=json_extract(m.body,'$.evaluation_id')
 WHERE m.kind='event' AND m.application=? AND m.client=? AND m.created>=?"""
APPLIED = " AND json_extract(m.body,'$.revision')<=coalesce(p.revision,0)"


def timeline(db, app, client, since):
    rows=[]
    for row in db.execute("SELECT id,identity,created FROM messages WHERE kind='source_offer' AND application=? AND client=? AND created>=? ORDER BY created DESC,id LIMIT 20",(app,client,since)):
        rows.append({'id':'offer:'+row['id'],'occurred_at':iso(row['created']),'phase':'source_offered','reference':row['identity'],'reason_code':None,'qualified':None,'publication':None,'readback_result':None})
    for row in db.execute("SELECT m.id,m.identity,max(d.acked) AS acked FROM messages m JOIN deliveries d ON d.message=m.id WHERE m.kind='source_offer' AND m.application=? AND m.client=? AND d.acked>=? GROUP BY m.id ORDER BY acked DESC,m.id LIMIT 20",(app,client,since)):
        rows.append({'id':'intake:'+row['id'],'occurred_at':iso(row['acked']),'phase':'intake_received','reference':row['identity'],'reason_code':None,'qualified':None,'publication':None,'readback_result':None})
    query="SELECT m.id,m.body,p.revision AS applied_revision "+EVENT_JOIN+" ORDER BY m.created DESC,m.id LIMIT 20"
    for row in db.execute(query,(app,client,since)):
        event=json.loads(row['body']);payload=event['payload'];applied=event['revision']<=(row['applied_revision'] or 0)
        phase=payload.get('state',payload['event_type']) if applied else 'feedback_waiting'
        rows.append({'id':'event:'+row['id'],'occurred_at':event['occurred_at'],'phase':phase,
                     'reference':payload.get('packet_id') or 'ref:'+hashlib.sha256(payload.get('candidate_ref',event['evaluation_id']).encode()).hexdigest(),
                     'reason_code':payload.get('reason_code') if applied else 'awaiting_predecessor',
                     'qualified':payload.get('qualified') if applied else None,
                     'publication':payload.get('readback',{}).get('publication') if applied else None,
                     'readback_result':payload.get('readback',{}).get('result') if applied else None})
    return sorted(rows,key=lambda row:(timestamp(row['occurred_at']),row['id']),reverse=True)[:20]


def snapshot(store, principal, window=86400):
    now=store.clock();rows=[]
    with store.connection() as db:
        for scope in principal['clients']:
            app,client=scope['application'],scope['client'];since=now-window
            offered=db.execute("SELECT count(*) FROM messages WHERE kind='source_offer' AND application=? AND client=? AND created>=?",(app,client,since)).fetchone()[0]
            deliveries=db.execute("SELECT count(*),min(m.created) FROM messages m WHERE m.kind='source_offer' AND m.application=? AND m.client=? AND m.processed=0",(app,client)).fetchone()
            waiting=db.execute("SELECT count(*) "+EVENT_JOIN+" AND json_extract(m.body,'$.revision')>coalesce(p.revision,0)",(app,client,since)).fetchone()[0]
            events=db.execute("SELECT m.body "+EVENT_JOIN+APPLIED+" ORDER BY json_extract(m.body,'$.evaluation_id'),json_extract(m.body,'$.revision')",(app,client,since))
            evaluations={};confirmed=set();published=set();accepted=set();qualified=set();reasons={}
            measured_qualification=False;measured_processing=False;latest=None
            for row in events:
                event=json.loads(row[0]);payload=event['payload'];evaluation=event['evaluation_id']
                measured_processing=True
                if latest is None or timestamp(event['occurred_at'])>timestamp(latest):latest=event['occurred_at']
                evaluations.setdefault(evaluation,False)
                if payload.get('state')=='uncertain':evaluations[evaluation]=True
                operation=payload.get('destination_operation_id')
                if payload.get('state')=='submission_accepted' and operation:accepted.add(operation)
                if payload.get('qualified') is not None:
                    measured_qualification=True
                    if payload['qualified']:qualified.add(payload.get('candidate_ref',evaluation))
                if payload['event_type']=='delivery_readback':
                    readback=payload['readback']
                    evaluations[evaluation]=not (readback['result']=='found_matching' and readback['checked_fields'] and readback['content_revision'])
                    identity=(operation,readback['destination_type'],readback['destination_id'])
                    if readback['result']=='found_matching' and readback['checked_fields'] and readback['content_revision']:confirmed.add(identity)
                    if readback['result']=='found_matching' and readback['content_revision'] and readback['publication']=='public' and readback['destination_type'] in ('provider','listing'):published.add((readback['destination_type'],readback['destination_id']))
                if payload.get('state')=='rejected':
                    code=payload.get('reason_code','unspecified');reasons[code]=reasons.get(code,0)+1
            rows.append({'scope':scope,'paperclip':{'source_offers':offered,'research_examinations':None,'coverage':'source-offers-only'},
                         'exchange':{'unprocessed':deliveries[0],'oldest_pending_seconds':None if deliveries[1] is None else max(0,int(now-deliveries[1])),'events_waiting':waiting},
                         'openclaw':{'qualified':len(qualified) if measured_qualification else None,'accepted_operations':len(accepted),
                                     'destination_confirmed':len(confirmed),'public_listings':len(published),
                                     'uncertain_evaluations':sum(bool(state) for state in evaluations.values()),
                                     'rejections':dict(sorted(reasons.items(),key=lambda kv:(-kv[1],kv[0]))[:10]),
                                     'observed_through':latest,'coverage':'events-only' if measured_processing else 'not_measured'},
                         'spend':{'gbp':None,'basis':'not_measured'},'next_action':'Reconcile feedback awaiting its predecessor' if waiting else None,
                         'timeline':timeline(db,app,client,since)})
    return {'schema_version':'1.1','as_of':iso(now),'observed_through':iso(now),'window_seconds':window,
            'coverage':'partial','clients':rows,'status':store.status(principal)}
