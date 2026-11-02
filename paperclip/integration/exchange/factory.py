"""Factory transactional source outbox and causal outcome/gap projector; no catalog writes."""
import hashlib
import json
import time
import uuid
from .contract import Contract, encode, iso, timestamp


def initialize(db):
    # The caller owns the transaction containing factory evidence and its outbox.
    db.execute('''CREATE TABLE IF NOT EXISTS exchange_source_outbox(
        packet TEXT PRIMARY KEY,operation TEXT UNIQUE NOT NULL,body BLOB NOT NULL,
        state TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,
        next_at REAL NOT NULL DEFAULT 0,receipt BLOB)''')
    db.execute('''CREATE TABLE IF NOT EXISTS exchange_event_inbox(
        event TEXT PRIMARY KEY,application TEXT NOT NULL,client TEXT NOT NULL,
        evaluation TEXT NOT NULL,revision INTEGER NOT NULL,previous TEXT,body BLOB NOT NULL,
        UNIQUE(application,client,evaluation,revision))''')
    db.execute('''CREATE TABLE IF NOT EXISTS exchange_projection(
        application TEXT NOT NULL,client TEXT NOT NULL,evaluation TEXT NOT NULL,
        revision INTEGER NOT NULL,event TEXT NOT NULL,body BLOB NOT NULL,
        PRIMARY KEY(application,client,evaluation))''')
    db.execute('''CREATE TABLE IF NOT EXISTS exchange_gap_intents(
        id TEXT PRIMARY KEY,application TEXT NOT NULL,client TEXT NOT NULL,
        candidate TEXT NOT NULL,fingerprint TEXT NOT NULL,gap TEXT NOT NULL,
        created REAL NOT NULL,state TEXT NOT NULL DEFAULT 'pending',native_task TEXT)''')


def offer(db, scope, task, page, facts, policy_revision, *, source_kind='directory_lead', now=None):
    initialize(db)
    now = time.time() if now is None else now
    observed = page['fetched_at']
    observed = float(observed) if isinstance(observed, (int,float)) else timestamp(observed)
    if observed > now + 300 or observed + 7*86400 <= now:
        raise ValueError('Source observation is not current')
    if not policy_revision:raise ValueError('Reviewed source policy revision required')
    text_hash = hashlib.sha256(page['text'].encode()).hexdigest()
    if page['sha256'] != text_hash:raise ValueError('Source hash recipe mismatch')
    packet = str(uuid.uuid5(uuid.NAMESPACE_URL, json.dumps([scope,task,page['url'],text_hash],sort_keys=True)))
    claims=[]
    for fact in facts:
        if fact['field'] in {'name','address','ages','price','schedule','activity','program_url'}:
            if fact['value'] not in fact['quote'] or fact['quote'] not in page['text']:
                raise ValueError('Claim does not match independent source text')
            claims.append({'field':fact['field'],'value':fact['value'],'quote':fact['quote'],'source_url':page['url'],'page_sha256':text_hash})
    value={'schema_version':'1.1','packet_id':packet,'scope':scope,'source_url':page['url'],
           'source_kind':source_kind,'fetched_at':iso(observed),'expires_at':iso(observed+7*86400),
           'page_sha256':text_hash,'extraction_recipe_id':'factory-visible-text-v1',
           'digest_kind':'visible_text_sha256','policy_review_ref':policy_revision,
           'producer_task_ref':task,'gap_fields':[],'claims':claims[:10]}
    name=next((f['value'] for f in facts if f['field']=='name'),None)
    if name:value['provider_name_hint']=name[:200]
    Contract().validate('SourceOffer',value)
    raw=encode(value)
    prior=db.execute('SELECT body FROM exchange_source_outbox WHERE packet=?',(packet,)).fetchone()
    if prior and bytes(prior[0])!=raw:raise ValueError('Offer changed under a stable identity')
    db.execute('INSERT OR IGNORE INTO exchange_source_outbox(packet,operation,body) VALUES(?,?,?)',(packet,str(uuid.uuid4()),raw))
    return packet


def project(db, event):
    from .store import Store
    initialize(db)
    Contract().validate('OutcomeEvent',event)
    scope=event['scope'];app,client=scope['application'],scope['client']
    raw=encode(event)
    prior=db.execute('SELECT body FROM exchange_event_inbox WHERE event=?',(event['event_id'],)).fetchone()
    if prior:
        if bytes(prior[0])!=raw:raise ValueError('Event identity changed')
        return False
    db.execute('INSERT INTO exchange_event_inbox VALUES(?,?,?,?,?,?,?)',(event['event_id'],app,client,event['evaluation_id'],event['revision'],event['previous_event_id'],raw))
    current=db.execute('SELECT revision,event,body FROM exchange_projection WHERE application=? AND client=? AND evaluation=?',(app,client,event['evaluation_id'])).fetchone()
    revision,predecessor,display=(current[0],current[1],json.loads(current[2])) if current else (0,None,None)
    while True:
        row=db.execute('SELECT event,previous,body FROM exchange_event_inbox WHERE application=? AND client=? AND evaluation=? AND revision=?',(app,client,event['evaluation_id'],revision+1)).fetchone()
        if not row or row[1]!=predecessor:break
        value=json.loads(row[2]);revision+=1;predecessor=row[0]
        if display is None or Store.rank(value['payload'])>=Store.rank(display['payload']):display=value
        db.execute('INSERT INTO exchange_projection VALUES(?,?,?,?,?,?) ON CONFLICT(application,client,evaluation) DO UPDATE SET revision=excluded.revision,event=excluded.event,body=excluded.body',(app,client,event['evaluation_id'],revision,predecessor,encode(display)))
    return True


def gap_intent(db,event,now=None):
    initialize(db)
    now=time.time() if now is None else now
    payload=event['payload']
    if payload['event_type']!='gap_report':return None
    scope=event['scope'];app,client=scope['application'],scope['client'];candidate=payload['candidate_ref']
    fields=','.join(sorted(payload['gap_fields']));fingerprint=payload['evidence_fingerprint']
    # A changed checker does not reset the unchanged-evidence allowance.
    key=str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps([scope,candidate,fields,fingerprint])))
    existing=db.execute('SELECT id FROM exchange_gap_intents WHERE id=?',(key,)).fetchone()
    if existing:return existing[0]
    if db.execute("SELECT count(*) FROM exchange_gap_intents WHERE application=? AND client=? AND candidate=? AND gap=? AND created>=?",(app,client,candidate,fields,now-72*3600)).fetchone()[0]>=2:return None
    db.execute('INSERT INTO exchange_gap_intents(id,application,client,candidate,fingerprint,gap,created) VALUES(?,?,?,?,?,?,?)',(key,app,client,candidate,fingerprint,fields,now))
    return key


def rank(features):
    weights={'official':25,'gap':20,'fresh':20,'new_branch':15,'undercovered':10,'yield':10}
    if not features.get('eligible'):return None
    values={name:float(features.get(name,0)) for name in weights}
    if any(not 0<=v<=1 for v in values.values()):raise ValueError('Ranking features must be in [0,1]')
    return sum(weights[k]*values[k] for k in weights)
