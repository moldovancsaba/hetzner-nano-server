"""Factory transactional source outbox and causal outcome/gap projector; no catalog writes."""
import hashlib
import json
import re
import time
import uuid
from .contract import Contract, encode, iso, timestamp


def initialize(db, *, create=False):
    required={'exchange_source_outbox','exchange_event_inbox','exchange_projection','exchange_gap_intents','exchange_source_selection','exchange_selection_cursor','exchange_event_requests','exchange_native_intents'}
    present={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if required<=present:return
    if not create:raise ValueError('Factory exchange state is missing; initialize once or recover explicitly')
    if required&present:raise ValueError('Factory exchange state is partial; refusing implicit recreation')
    if not db.in_transaction:db.execute('BEGIN IMMEDIATE')
    # The caller commits the explicit schema installation transaction.
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
    db.execute('''CREATE TABLE IF NOT EXISTS exchange_source_selection(
        packet TEXT PRIMARY KEY,application TEXT NOT NULL,client TEXT NOT NULL,family TEXT NOT NULL,
        mode TEXT NOT NULL,score REAL NOT NULL,features BLOB NOT NULL,selected REAL NOT NULL)''')
    db.execute('CREATE TABLE IF NOT EXISTS exchange_selection_cursor(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
    db.execute('''CREATE TABLE exchange_event_requests(
        id TEXT PRIMARY KEY,route TEXT NOT NULL,body BLOB NOT NULL,state TEXT NOT NULL,
        next_at REAL NOT NULL DEFAULT 0,attempts INTEGER NOT NULL DEFAULT 0,error TEXT)''')
    db.execute('''CREATE TABLE exchange_native_intents(
        id TEXT PRIMARY KEY,body BLOB NOT NULL,next_at REAL NOT NULL DEFAULT 0,attempts INTEGER NOT NULL DEFAULT 0)''')
    db.execute("CREATE INDEX IF NOT EXISTS exchange_pending_scope ON exchange_source_outbox(state,json_extract(body,'$.scope.application'),json_extract(body,'$.scope.client'),next_at)")


def offer(db, scope, task, page, facts, policy_revision, *, source_kind='directory_lead', now=None,reuse_unchanged=False):
    initialize(db)
    if not db.in_transaction:db.execute('BEGIN IMMEDIATE')
    now = time.time() if now is None else now
    observed = page['fetched_at']
    observed = float(observed) if isinstance(observed, (int,float)) else timestamp(observed)
    if observed > now + 300 or observed + 7*86400 <= now:
        raise ValueError('Source observation is not current')
    if not policy_revision:raise ValueError('Reviewed source policy revision required')
    text_hash = hashlib.sha256(page['text'].encode()).hexdigest()
    if page['sha256'] != text_hash:raise ValueError('Source hash recipe mismatch')
    gap=db.execute('SELECT gap,candidate FROM exchange_gap_intents WHERE native_task=? AND application=? AND client=? ORDER BY created DESC LIMIT 1',(task,scope['application'],scope['client'])).fetchone()
    contract=Contract()
    public_pattern=contract.spec['components']['schemas']['PublicClaim']['properties']['quote']['pattern']
    claims=[]
    for fact in facts:
        if fact['field'] in {'name','address','ages','price','schedule','activity','program_url'}:
            if fact['value'] not in fact['quote'] or fact['quote'] not in page['text']:
                raise ValueError('Claim does not match independent source text')
            value=fact['value']
            if len(value)>240 or not re.fullmatch(public_pattern,value):continue
            excerpt=fact['quote']
            if len(excerpt)>240 or not re.fullmatch(public_pattern,excerpt):excerpt=value
            claims.append({'field':fact['field'],'value':value,'quote':excerpt,'source_url':page['url'],'page_sha256':text_hash})
    value={'schema_version':'1.1','scope':scope,'source_url':page['url'],
           'source_kind':source_kind,'fetched_at':iso(observed),'expires_at':iso(observed+7*86400),
           'page_sha256':text_hash,'extraction_recipe_id':'factory-visible-text-v1',
           'digest_kind':'visible_text_sha256','policy_review_ref':policy_revision,
           'producer_task_ref':task,'gap_fields':gap[0].split(',') if gap else [],'claims':claims[:10]}
    name=next((f['value'] for f in facts if f['field']=='name'),None)
    if name and len(name)<=200 and re.fullmatch(public_pattern,name):value['provider_name_hint']=name
    if gap:value['gap_root_ref']=gap[1]
    packet=str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps(['source-offer-v2',value],sort_keys=True,separators=(',',':'))))
    value['packet_id']=packet
    contract.validate('SourceOffer',value)
    raw=encode(value)
    prior=db.execute('SELECT body FROM exchange_source_outbox WHERE packet=?',(packet,)).fetchone()
    if prior and bytes(prior[0])!=raw:raise ValueError('Offer changed under a stable identity')
    if prior:return packet
    if reuse_unchanged:
        recent=db.execute("SELECT packet,body FROM exchange_source_outbox WHERE json_extract(body,'$.scope.application')=? AND json_extract(body,'$.scope.client')=? AND json_extract(body,'$.producer_task_ref')=? AND json_extract(body,'$.source_url')=? ORDER BY rowid DESC LIMIT 20",(scope['application'],scope['client'],task,page['url']))
        material=lambda candidate:{key:item for key,item in candidate.items() if key not in {'packet_id','fetched_at','expires_at'}}
        for prior_packet,prior_body in recent:
            previous=json.loads(prior_body)
            if timestamp(previous['expires_at'])>now and material(previous)==material(value):return prior_packet
    pending=db.execute("SELECT count(*) FROM exchange_source_outbox WHERE state IN ('pending','held') AND json_extract(body,'$.scope.application')=? AND json_extract(body,'$.scope.client')=? AND json_extract(body,'$.expires_at')>?",(scope['application'],scope['client'],iso(now))).fetchone()[0]
    quota_key='offer_quota:'+scope['application']+':'+scope['client']
    quota=db.execute('SELECT value FROM exchange_selection_cursor WHERE key=?',(quota_key,)).fetchone()
    day=iso(now)[:10];usage=json.loads(quota[0]) if quota else {'day':day,'count':0}
    count=usage['count'] if usage['day']==day else 0
    if pending>=20 or count>=20:
        db.execute("INSERT INTO exchange_selection_cursor VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",('offer_hold:'+scope['application']+':'+scope['client'],json.dumps({'at':iso(now),'reason':'local-capacity' if pending>=20 else 'daily-offer-cap'})))
        return None
    db.execute('INSERT OR IGNORE INTO exchange_source_outbox(packet,operation,body) VALUES(?,?,?)',(packet,str(uuid.uuid4()),raw))
    db.execute('INSERT INTO exchange_selection_cursor VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(quota_key,json.dumps({'day':day,'count':count+1})))
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


def select_offers(db,limit=2,now=None):
    """Allocate four ranked offers and one exploration offer per scope, fairly across clients."""
    from urllib.parse import urlsplit
    initialize(db)
    now=time.time() if now is None else now
    if not isinstance(limit,int) or not 0<=limit<=10:raise ValueError('Selection limit exceeds turn bound')
    selected=[]
    for _ in range(limit):
        scopes=list(db.execute("SELECT DISTINCT json_extract(body,'$.scope.application'),json_extract(body,'$.scope.client') FROM exchange_source_outbox WHERE state='pending' AND next_at<=? ORDER BY 1,2 LIMIT 8",(now,)))
        if not scopes:break
        last=db.execute("SELECT value FROM exchange_selection_cursor WHERE key='last_scope'").fetchone()
        keys=[json.dumps(list(scope),separators=(',',':')) for scope in scopes]
        position=(keys.index(last[0])+1)%len(keys) if last and last[0] in keys else 0
        app,client=scopes[position];scope_key=keys[position]
        cursor=db.execute('SELECT value FROM exchange_selection_cursor WHERE key=?',(scope_key,)).fetchone()
        count=int(cursor[0]) if cursor else 0
        mode='explore' if count%5==4 else 'ranked'
        cursor_rows=db.execute("SELECT rowid,* FROM exchange_source_outbox WHERE state='pending' AND next_at<=? AND json_extract(body,'$.scope.application')=? AND json_extract(body,'$.scope.client')=? ORDER BY rowid LIMIT 64",(now,app,client))
        names=[column[0] for column in cursor_rows.description]
        candidates=[]
        for values in cursor_rows:
            row=dict(zip(names,values));packet=json.loads(row['body'])
            if any(chosen['packet']==row['packet'] for chosen in selected):continue
            if timestamp(packet['expires_at'])<=now:
                db.execute("UPDATE exchange_source_outbox SET state='held' WHERE packet=?",(row['packet'],));continue
            Contract().validate('SourceOffer',packet)
            previous=db.execute('SELECT mode,score,features,family FROM exchange_source_selection WHERE packet=?',(row['packet'],)).fetchone()
            family=urlsplit(packet['source_url']).hostname
            # Unknown novelty, coverage and yield receive no credit; model confidence never enters selection.
            features={'eligible':True,'official':int(packet['source_kind'] in ('official_branch','official_program')),
                      'gap':int(bool(packet['gap_fields'])),'fresh':min(1,max(0,1-(now-timestamp(packet['fetched_at']))/(7*86400))),
                      'new_branch':0,'undercovered':0,'yield':0}
            score=rank(features)
            family_count=db.execute('SELECT count(*) FROM exchange_source_selection WHERE application=? AND client=? AND family=?',(app,client,family)).fetchone()[0]
            candidates.append((previous is not None,score,family_count,row['rowid'],row,features,family,previous))
        if not candidates:
            # No eligible row in the bounded scope window; rotate without allocating or spending.
            db.execute('INSERT OR REPLACE INTO exchange_selection_cursor VALUES(?,?)',('last_scope',scope_key))
            continue
        retries=[row for row in candidates if row[0]]
        chosen=min(retries,key=lambda row:row[3]) if retries else min(candidates,key=(lambda row:(row[2],row[3])) if mode=='explore' else (lambda row:(-row[1],row[3])))
        _,score,_,_,row,features,family,previous=chosen
        if not previous:
            db.execute('INSERT INTO exchange_source_selection VALUES(?,?,?,?,?,?,?,?)',(row['packet'],app,client,family,mode,score,encode(features),now))
            db.execute('INSERT OR REPLACE INTO exchange_selection_cursor VALUES(?,?)',(scope_key,str(count+1)))
        db.execute('INSERT OR REPLACE INTO exchange_selection_cursor VALUES(?,?)',('last_scope',scope_key))
        row['selection_mode']=previous[0] if previous else mode
        row['selection_score']=previous[1] if previous else score
        selected.append(row)
    return selected
