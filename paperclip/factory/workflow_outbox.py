"""Durable bounded producer spool; acknowledgements never overwrite source events."""
import hashlib,json,os,sqlite3,time
from contextlib import contextmanager
from pathlib import Path

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
class OutboxConflict(Exception):pass
class OutboxCapacity(Exception):pass

class WorkflowOutbox:
    def __init__(self,path,*,max_pending=20000,max_bytes=128*1024*1024):
        self.path=Path(path);self.path.parent.mkdir(parents=True,mode=0o700,exist_ok=True);self.max_pending=max_pending;self.max_bytes=max_bytes
        with self.db() as db:
            db.execute('PRAGMA journal_mode=WAL');db.execute('CREATE TABLE IF NOT EXISTS workflow_outbox(event_id TEXT PRIMARY KEY,payload_hash TEXT,payload TEXT,state TEXT,created REAL,acknowledged REAL,error TEXT)')
        self.path.chmod(0o600)
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=2);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()
    def add(self,event):
        raw=canonical(event);identity=event['event_id'];sha=hashlib.sha256(raw.encode()).hexdigest()
        if len(raw.encode())>65536 or not isinstance(identity,str) or len(identity)>160 or not identity.startswith(str(event.get('client_id'))+':'):raise ValueError('Bounded namespaced event required')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT payload_hash FROM workflow_outbox WHERE event_id=?',(identity,)).fetchone()
            if old:
                if old[0]!=sha:raise OutboxConflict('Event identity changed payload')
                return False
            count,size=db.execute("SELECT COUNT(*),COALESCE(SUM(length(CAST(payload AS BLOB))),0) FROM workflow_outbox WHERE payload IS NOT NULL").fetchone()
            if count>=self.max_pending or size+len(raw.encode())>self.max_bytes:raise OutboxCapacity('Feedback outbox full; source checkpoint must not advance')
            db.execute('INSERT INTO workflow_outbox VALUES(?,?,?,?,?,NULL,NULL)',(identity,sha,raw,'pending',time.time()))
        return True
    def flush(self,send,*,max_batches=5):
        result={'acknowledged':0,'conflicts':0,'invalid':0,'batches':0}
        for _ in range(max_batches):
            with self.db() as db:rows=db.execute("SELECT * FROM workflow_outbox WHERE state='pending' ORDER BY created,event_id LIMIT 200").fetchall()
            batch=[];size=64
            for r in rows:
                if size+len(r['payload'].encode())+1>1024*1024:break
                batch.append(json.loads(r['payload']));size+=len(r['payload'].encode())+1
            if not batch:break
            response=send(batch);receipts=response.get('receipts',[]);expected={e['event_id'] for e in batch}
            if response.get('schema_version')!='1' or len(receipts)!=len(expected) or {r.get('event_id') for r in receipts}!=expected:raise ValueError('Incomplete feedback receipt; retain batch')
            if any(r.get('state') not in ('stored','replayed','conflict','invalid') for r in receipts):raise ValueError('Unknown feedback state; retain batch')
            with self.db() as db:
                for receipt in receipts:
                    state=receipt['state'];identity=receipt['event_id']
                    if state in ('stored','replayed'):
                        changed=db.execute("UPDATE workflow_outbox SET payload=NULL,state='acknowledged',acknowledged=? WHERE event_id=? AND state='pending'",(time.time(),identity)).rowcount;result['acknowledged']+=changed
                    else:
                        changed=db.execute('UPDATE workflow_outbox SET state=?,error=? WHERE event_id=? AND state=\'pending\'',(state,receipt.get('error_code','RECEIPT_FAILURE'),identity)).rowcount;result['conflicts' if state=='conflict' else 'invalid']+=changed
            result['batches']+=1
        return result
    def status(self):
        with self.db() as db:
            counts={r[0]:r[1] for r in db.execute('SELECT state,COUNT(*) FROM workflow_outbox GROUP BY state')};oldest=db.execute("SELECT MIN(created) FROM workflow_outbox WHERE state='pending'").fetchone()[0]
        return {'counts':counts,'oldest_pending_seconds':max(0,time.time()-oldest) if oldest else None}
