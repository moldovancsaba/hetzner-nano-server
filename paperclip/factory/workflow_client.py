"""Portable standard-library workflow SDK. Estimates only; client gates are external."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import TypedDict, Literal
import hashlib,json,math,re,time,urllib.request,urllib.error,urllib.parse

PROFILE='quote-support-conditional-v1'
class EvidenceRequest(TypedDict):
    schema_version: Literal['1']
    client_id: Literal['openclaw','paperclip']
    task_profile: Literal['quote-support-conditional-v1']
    client_request_id: str
    evidence_id: str
    source_version: str
    evidence_sha256: str
    claim: str
    quote: str
    language: Literal['en']
    source_retrieved_at: str

class WorkflowUnavailable(Exception):
    def __init__(self,code,retryable=False):
        super().__init__(code);self.code=code;self.retryable=retryable

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def sha(value):return hashlib.sha256(value.encode()).hexdigest()
def instant(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('Aware timestamp required')
    return dt.astimezone(timezone.utc)

def validate_score(result,request,now=None):
    now=now or datetime.now(timezone.utc)
    required={'schema_version','request_id','client_id','client_request_id','evidence_id','source_version','task_profile','probabilities','outcome_space','conditional_on_observed_classes','unavailable_outcomes','probability_kind','calibration_status','model_version','artifact_digest','rubric_version','scoring_contract_digest','evidence_sha256','claim_sha256','input_sha256','scored_at','valid_until','client_decides'}
    if not isinstance(result,dict) or set(result)!=required:raise ValueError('Unexpected score fields')
    for key in ('client_id','client_request_id','evidence_id','source_version','task_profile','evidence_sha256'):
        if result[key]!=request[key]:raise ValueError('Receipt/request mismatch')
    normalized=dict(request);normalized['source_retrieved_at']=instant(request['source_retrieved_at']).isoformat().replace('+00:00','Z')
    if result['input_sha256']!=sha(canonical(normalized)) or result['claim_sha256']!=sha(request['claim']) or request['evidence_sha256']!=sha(request['quote']):raise ValueError('Receipt/source hash mismatch')
    for key in ('model_version','artifact_digest','scoring_contract_digest','evidence_sha256','claim_sha256','input_sha256'):
        if not isinstance(result[key],str) or not re.fullmatch('[a-f0-9]{64}',result[key]):raise ValueError('Invalid digest')
    if (result['schema_version']!='1' or result['task_profile']!=PROFILE or result['rubric_version']!='evidence-relation-v2'
        or result['conditional_on_observed_classes'] is not True or result['client_decides'] is not True
        or result['outcome_space']!=['SUPPORTED','UNKNOWN'] or result['unavailable_outcomes']!=['UNSUPPORTED']
        or result['probability_kind']!='experimental_conditional_classifier_scores' or result['calibration_status'] not in ('uncalibrated','experimental_temperature_scaled')):raise ValueError('Unsupported probability scope')
    p=result['probabilities']
    if not isinstance(p,dict) or set(p)!={'SUPPORTED','UNKNOWN'} or not all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=1 for v in p.values()) or abs(sum(p.values())-1)>1e-6:raise ValueError('Invalid probability distribution')
    scored=instant(result['scored_at']);expires=instant(result['valid_until'])
    if expires<=scored or now>=expires or scored>now+timedelta(seconds=30):raise ValueError('Expired/future receipt')
    return result

def event_fingerprint(event):
    value=json.loads(canonical(event))
    if value.get('kind') in ('observation','operational_failure'):
        value={'entity_id':None,'packet_id':None,'gate_findings':{},'evidence':None,'score_receipt':None,'test_only':False,**value}
    else:
        value={'expected_review_id':None,**value}
        if isinstance(value.get('rationale'),str):value['rationale']=value['rationale'].strip()
    def normalize(item):
        if isinstance(item,dict):
            return {k:(instant(v).isoformat().replace('+00:00','Z') if k in ('occurred_at','retrieved_at','reviewed_at','scored_at','valid_until') and isinstance(v,str) else normalize(v)) for k,v in item.items()}
        if isinstance(item,list):return [normalize(v) for v in item]
        return item
    return sha(canonical(normalize(value)))

class WorkflowClient:
    def __init__(self,base_url,client_id,token_file,timeout=2.,expected_model=None,request_purpose="workflow"):
        u=urllib.parse.urlsplit(base_url)
        if (u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.query or u.fragment
            or (u.scheme=='http' and u.hostname not in ('localhost','127.0.0.1','::1')) or u.path.rstrip('/') not in ('','/jev')):raise ValueError('HTTPS or loopback origin required')
        if client_id not in ('openclaw','paperclip') or not .05<=timeout<=2.:raise ValueError('Invalid client or deadline')
        if request_purpose not in ('workflow','test'):raise ValueError('Invalid request purpose')
        self.request_purpose=request_purpose
        self.base_url=base_url.rstrip('/');self.client_id=client_id;self.token_file=Path(token_file);self.timeout=timeout;self.expected_model=expected_model
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args):return None
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def _request(self,path,payload=None):
        try:
            if self.token_file.stat().st_mode&0o077:raise ValueError('Token file must be private')
            token=self.token_file.read_text().strip()
            if not 32<=len(token)<=512 or any(c.isspace() for c in token):raise ValueError('Invalid token')
        except (OSError,ValueError):raise WorkflowUnavailable('TOKEN_UNAVAILABLE') from None
        raw=canonical(payload).encode() if payload is not None else None
        if raw is not None and len(raw)>(65536 if path.endswith('/score') else 1048576):raise WorkflowUnavailable('PAYLOAD_TOO_LARGE')
        deadline=time.monotonic()+self.timeout
        for attempt in range(2):
            remaining=deadline-time.monotonic()
            if remaining<=0:raise WorkflowUnavailable('DEADLINE_EXCEEDED',True)
            req=urllib.request.Request(self.base_url+path,data=raw,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json','X-Request-Purpose':self.request_purpose})
            try:
                with self.opener.open(req,timeout=remaining) as response:
                    parts=[];size=0
                    while True:
                        if time.monotonic()>=deadline:raise WorkflowUnavailable('DEADLINE_EXCEEDED',True)
                        try:response.fp.raw._sock.settimeout(max(.001,deadline-time.monotonic()))
                        except AttributeError:pass
                        chunk=response.read1(min(65536,1048577-size))
                        if not chunk:break
                        parts.append(chunk);size+=len(chunk)
                        if size>1048576:raise WorkflowUnavailable('INVALID_RESPONSE')
                    data=b''.join(parts)
                    result=json.loads(data)
                if not isinstance(result,dict):raise WorkflowUnavailable('INVALID_RESPONSE')
                return result
            except urllib.error.HTTPError as e:
                if path=='/v1/workflow-events' and e.code==409:
                    try:
                        body=e.read(1048577)
                        if len(body)>1048576:raise ValueError('Oversized conflict receipt')
                        return json.loads(body)
                    except (ValueError,TypeError):raise WorkflowUnavailable('INVALID_RESPONSE') from None
                retryable=e.code in (429,502,503,504);retry_after=e.headers.get('Retry-After','0.05')
                try:delay=max(.05,float(retry_after))
                except ValueError:delay=1.
                if retryable and attempt==0 and time.monotonic()+delay<deadline:
                    time.sleep(delay);continue
                raise WorkflowUnavailable('HTTP_'+str(e.code),retryable) from None
            except (TimeoutError,OSError,urllib.error.URLError):
                if attempt==0 and time.monotonic()+.05<deadline:time.sleep(.05);continue
                raise WorkflowUnavailable('SERVICE_UNAVAILABLE',True) from None
            except (ValueError,TypeError):raise WorkflowUnavailable('INVALID_RESPONSE') from None
    def score_evidence(self,request:EvidenceRequest):
        if request.get('client_id')!=self.client_id:raise WorkflowUnavailable('CLIENT_MISMATCH')
        result=self._request('/v1/evidence/score',request)
        try:validate_score(result,request)
        except (ValueError,TypeError,KeyError,AttributeError):raise WorkflowUnavailable('INVALID_RESPONSE') from None
        if self.expected_model and result['model_version']!=self.expected_model:raise WorkflowUnavailable('MODEL_MISMATCH')
        return result
    def submit_workflow_events(self,events):
        if any(e.get('client_id')!=self.client_id for e in events):raise WorkflowUnavailable('CLIENT_MISMATCH')
        result=self._request('/v1/workflow-events',{'schema_version':'1','events':events})
        try:
            receipts=result['receipts']
            if set(result)!={'schema_version','receipts'} or result['schema_version']!='1' or not isinstance(receipts,list) or len(receipts)!=len(events) or {r.get('event_id') for r in receipts}!={e['event_id'] for e in events}:raise ValueError('Incomplete event receipt')
            expected={e['event_id']:event_fingerprint(e) for e in events}
            for r in receipts:
                if r['event_sha256']!=expected[r['event_id']]:raise ValueError('Receipt/event hash mismatch')
                if set(r)!={'event_id','event_sha256','state','error_code'} or not re.fullmatch('[a-f0-9]{64}',r['event_sha256']) or r['state'] not in ('stored','replayed','conflict','invalid'):raise ValueError('Invalid event receipt')
        except (ValueError,TypeError,KeyError,AttributeError):raise WorkflowUnavailable('INVALID_RESPONSE') from None
        return result
    def models(self):return self._request('/v1/evidence/models')
