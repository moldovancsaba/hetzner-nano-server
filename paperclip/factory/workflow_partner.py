"""Portable client-owned evidence policy and durable outcome recording."""
import hashlib,json,os,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from workflow_client import WorkflowClient,WorkflowUnavailable
from workflow_outbox import WorkflowOutbox

def sha(text):return hashlib.sha256(text.encode()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()

class WorkflowPartner:
    def __init__(self,config,*,client=None):
        self.config=config;self.mode=config.get('mode','off')
        if self.mode not in ('off','shadow','assist'):raise ValueError('Invalid JEV mode')
        self.client=client
        if self.mode!='off':
            self.root=Path(config['state_root']);self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
            self.outbox=WorkflowOutbox(self.root/'outbox.sqlite3')
            with self.outbox.db() as db:db.execute('CREATE TABLE IF NOT EXISTS score_circuit(id INTEGER PRIMARY KEY,failures INTEGER,blocked_until REAL)')
            self.client=client or WorkflowClient(config['base_url'],config['client_id'],config['token_file'],request_purpose=config.get('purpose','workflow'))
        threshold=config.get('minimum_support',.2)
        if type(threshold) not in (int,float) or not 0<=threshold<=1:raise ValueError('Invalid client threshold')
        self.threshold=threshold
    def assess(self,*,operation,reference,url,quote,claim,retrieved_at,source_version,training_allowed=True):
        if self.mode=='off':return {'state':'off','additional_evidence':False}
        case=sha(json.dumps([operation,reference,url,source_version,quote,claim],ensure_ascii=False))
        evidence={'evidence_id':'field:'+sha(url+'\n'+claim),'source_version':source_version,'source_url':url,'quote':quote,'claim':claim,'language':'en','retrieved_at':retrieved_at,'evidence_sha256':sha(quote),'claim_sha256':sha(claim),'data_classification':'public_source_quote','training_use_authorized':training_allowed}
        request={'schema_version':'1','client_id':self.config['client_id'],'task_profile':'quote-support-conditional-v1','client_request_id':'field:'+case+':'+uuid.uuid4().hex,'evidence_id':evidence['evidence_id'],'source_version':source_version,'evidence_sha256':sha(quote),'claim':claim,'quote':quote,'language':'en','source_retrieved_at':retrieved_at}
        result={'state':'not_checked','additional_evidence':self.mode=='assist','policy_version':self.config['policy_version'],'operation':operation,'case':case,'reference_hash':sha(str(reference)),'evidence':evidence}
        if not isinstance(quote,str) or not 1<=len(quote)<=8000 or not isinstance(claim,str) or not 1<=len(claim)<=2000:
            result['error']='EVIDENCE_BOUNDS'
        else:
            try:
                with self.outbox.db() as db:
                    circuit=db.execute('SELECT failures,blocked_until FROM score_circuit WHERE id=1').fetchone()
                if circuit and circuit[1]>time.time():raise WorkflowUnavailable('CIRCUIT_OPEN',True)
                receipt=self.client.score_evidence(request)
                with self.outbox.db() as db:db.execute('INSERT OR REPLACE INTO score_circuit VALUES(1,0,0)')
                result.update(state='scored',receipt=receipt,additional_evidence=self.mode=='assist' and receipt['probabilities']['SUPPORTED']<self.threshold)
            except WorkflowUnavailable as e:
                result['error']=e.code
                if e.code!='CIRCUIT_OPEN':
                    with self.outbox.db() as db:
                        db.execute('INSERT INTO score_circuit VALUES(1,1,0) ON CONFLICT(id) DO UPDATE SET failures=failures+1')
                        failures=db.execute('SELECT failures FROM score_circuit WHERE id=1').fetchone()[0]
                        if failures>=3:db.execute('UPDATE score_circuit SET blocked_until=? WHERE id=1',(time.time()+60,))
        self.record(result,'additional_evidence_required' if result['additional_evidence'] else 'evidence_scored' if result['state']=='scored' else 'score_not_checked')
        return result
    def record(self,case,outcome):
        if self.mode=='off' or case.get('state')=='off':return
        stamp=now();event={'kind':'observation','event_id':self.config['client_id']+':'+uuid.uuid4().hex,'client_id':self.config['client_id'],'operation':case['operation'],'run_id':case['reference_hash'],'occurred_at':stamp,'client_policy_version':self.config['policy_version'],'outcome':outcome,'test_only':self.config.get('purpose')=='test'}
        # Invalid input cannot masquerade as a valid source snapshot.
        if case.get('error')!='EVIDENCE_BOUNDS':event['evidence']=case['evidence']
        if case.get('receipt'):event['score_receipt']=case['receipt']
        self.outbox.add(event)
        try:
            if not case.get('error'):self.outbox.flush(self.client.submit_workflow_events,max_batches=1)
        except (WorkflowUnavailable,OSError,ValueError):pass
        self._status(case)
    def _status(self,case):
        status={'at':now(),'mode':self.mode,'policy_version':self.config['policy_version'],'last_state':case['state'],'additional_evidence':case['additional_evidence'],'model_version':case.get('receipt',{}).get('model_version'),'outbox':self.outbox.status()}
        path=self.root/'status.json';temp=path.with_suffix('.'+uuid.uuid4().hex+'.tmp');temp.write_text(json.dumps(status));temp.chmod(0o600);temp.replace(path)
    def flush(self):
        if self.mode=='off':return {'state':'off'}
        return self.outbox.flush(self.client.submit_workflow_events)
