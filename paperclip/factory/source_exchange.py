"""Opt-in exchange hooks inside existing factory transactions and coordination turns."""
import importlib
import json
import logging
import os
import stat
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime,timezone


def modules():
 root=Path(os.environ.get('SOURCE_EXCHANGE_MODULES',str(Path(__file__).resolve().parent.parent/'integration')))
 if str(root) not in sys.path:sys.path.insert(0,str(root))
 return importlib.import_module('exchange.factory')


def require_native_catalog_writer(config,issue):
 settings=config.get('source_exchange',{})
 handoffs=settings.get('destination_handoffs',{})
 if not isinstance(handoffs,dict):raise ValueError('Catalog handoff configuration requires review')
 project=issue.get('projectId')
 if project not in handoffs:return
 handoff=handoffs[project];scope=settings.get('projects',{}).get(project)
 if (not isinstance(handoff,dict) or scope is None or handoff.get('scope')!=scope
     or scope.get('application')!='classscout' or handoff.get('writer')!='openclaw'
     or type(handoff.get('writer_epoch')) is not int or handoff['writer_epoch']<1
     or not isinstance(handoff.get('review_ref'),str) or not 1<=len(handoff['review_ref'])<=200):
  raise ValueError('Catalog handoff does not match the reviewed project authority')
 raise ValueError('Catalog writes are delegated to the assigned external writer. Preserve existing packets and reconcile uncertain effects before changing authority.')


def save_offer(db,config,issue,page,facts):
 settings=config.get('source_exchange',{})
 if not settings.get('offers_enabled'):return None
 scope=settings.get('projects',{}).get(issue.get('projectId'))
 if scope is None:return None
 module=modules()
 from exchange.contract import ExchangeError
 try:return discovery_offer(db,module,scope,issue,page,facts,settings['policy_revision'])
 except (ValueError,ExchangeError) as error:
  logging.warning('source_offer_held type=%s application=%s client=%s',type(error).__name__,scope['application'],scope['client'])
  return None


def discovery_offer(db,module,scope,issue,page,facts,policy):
 """Preserve the total allowance while reserving ClassScout discovery capacity for complete identity evidence."""
 module.initialize(db)
 if not db.in_transaction:db.execute('BEGIN IMMEDIATE')
 before=db.execute('SELECT coalesce(max(rowid),0) FROM exchange_source_outbox').fetchone()[0]
 db.execute('SAVEPOINT source_export_admission')
 try:
  packet=module.offer(db,scope,issue['id'],page,facts,policy,source_kind='directory_lead',reuse_unchanged=True)
  row=db.execute('SELECT rowid,body FROM exchange_source_outbox WHERE packet=?',(packet,)).fetchone() if packet else None
  value=json.loads(row[1]) if row else {}
  partial=(scope['application']=='classscout' and row and row[0]>before and not value.get('gap_root_ref')
           and (not value.get('provider_name_hint') or not any(claim['field']=='address' for claim in value['claims'])))
  if partial:
   key='partial_discovery_quota:'+scope['application']+':'+scope['client'];day=datetime.now(timezone.utc).strftime('%Y-%m-%d')
   saved=db.execute('SELECT value FROM exchange_selection_cursor WHERE key=?',(key,)).fetchone()
   usage=json.loads(saved[0]) if saved else None
   legacy=db.execute("SELECT count(*) FROM exchange_source_outbox o WHERE rowid<=? AND json_extract(body,'$.scope.application')=? AND json_extract(body,'$.scope.client')=? AND json_extract(body,'$.gap_root_ref') IS NULL AND (json_extract(body,'$.provider_name_hint') IS NULL OR NOT EXISTS(SELECT 1 FROM json_each(o.body,'$.claims') c WHERE json_extract(c.value,'$.field')='address'))",(before,scope['application'],scope['client'])).fetchone()[0] if usage is None else 0
   count=(usage['count'] if usage['day']==day else 0) if usage else min(4,legacy)
   if count>=4:
    db.execute('ROLLBACK TO source_export_admission');db.execute('RELEASE source_export_admission')
    db.execute('INSERT INTO exchange_selection_cursor VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps({'day':day,'count':count})))
    db.execute('INSERT INTO exchange_selection_cursor VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('offer_hold:'+scope['application']+':'+scope['client'],json.dumps({'at':datetime.now(timezone.utc).isoformat(),'reason':'discovery-identity-exploration-cap'})))
    return None
   db.execute('INSERT INTO exchange_selection_cursor VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps({'day':day,'count':count+1})))
  db.execute('RELEASE source_export_admission')
  return packet
 except BaseException:
  db.execute('ROLLBACK TO source_export_admission');db.execute('RELEASE source_export_admission');raise


def save_verified_page(database,job,page):
 path=Path(os.environ.get('FACTORY_CONFIG','/opt/narimato-factory/factory.json'))
 config=json.loads(path.read_text()) if path.is_file() else {}
 if not config.get('source_exchange',{}).get('offers_enabled'):return None
 if job.get('project_id') not in config['source_exchange'].get('projects',{}):return None
 # The page was already independently fetched by the normal search workflow; no search response is exported.
 import evidence
 facts=evidence.literal_facts(page)
 with database() as db:
  try:
   return save_offer(db,config,{'id':job['issue_id'],'projectId':job['project_id']},page,facts)
  except (ValueError,importlib.import_module('exchange.contract').ExchangeError):
   # Nontransferable evidence does not invalidate the native verified-page handoff.
   db.execute("INSERT INTO exchange_selection_cursor VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",('verified_page_export_hold',json.dumps({'at':time.time(),'reason':'public-contract-refused'})))
   return None


def credential_token(settings):
 path=Path(settings['token_file'])
 directory=os.environ.get('CREDENTIALS_DIRECTORY')
 managed=bool(directory and path.parent.resolve()==Path(directory).resolve())
 if not stat.S_ISREG(path.lstat().st_mode):raise ValueError('Exchange credential must be a regular file')
 fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
 try:
  info=os.fstat(fd)
  if not stat.S_ISREG(info.st_mode):raise ValueError('Exchange credential must be a regular file')
  if managed:
   parent=path.parent.stat()
   if info.st_uid not in {0,os.geteuid()} or parent.st_uid not in {0,os.geteuid()} or stat.S_IMODE(info.st_mode) not in {0o400,0o440,0o600} or parent.st_mode&0o027:raise ValueError('Managed exchange credential is not protected')
  elif info.st_mode&0o077:raise ValueError('Exchange credential must be private')
  with os.fdopen(fd,'r',encoding='ascii') as source:
   fd=None;token=source.read(513).strip()
 finally:
  if fd is not None:os.close(fd)
 if not 32<=len(token)<=512 or any(ord(char)<33 or ord(char)>126 for char in token):raise ValueError('Invalid exchange credential')
 return token


def transport(settings,method,route,body=None,operation=None):
 if not route.startswith('/') or '?' in route or '..' in route:raise ValueError('Invalid exchange route')
 token=credential_token(settings)
 request=urllib.request.Request('http://127.0.0.1:9091/integrations/v1'+route,data=body,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json',**({'Idempotency-Key':operation} if operation else {})})
 remaining=settings.get('_deadline',time.monotonic()+10)-time.monotonic()
 if remaining<=0:raise TimeoutError('Exchange turn budget exhausted')
 with urllib.request.urlopen(request,timeout=min(10,remaining)) as response:
  raw=response.read(262145)
  if len(raw)>262144:raise ValueError('Exchange response too large')
  return json.loads(raw)


def sync_offers(database,settings,limit=2):
 if not settings.get('offers_enabled'):return {'state':'disabled'}
 module=modules()
 with database() as db:
  module.initialize(db)
  rows=module.select_offers(db,limit=limit)
 sent=0
 for row in rows:
  if settings.get('_deadline',time.monotonic()+10)-time.monotonic()<1:break
  try:
   response=transport(settings,'POST','/source-offers',bytes(row['body']),row['operation'])
   if response.get('operation_id')!=row['operation'] or response.get('state')!='broker_saved':raise ValueError('Invalid exchange receipt')
   with database() as db:db.execute("UPDATE exchange_source_outbox SET state='done',receipt=? WHERE packet=?",(json.dumps(response).encode(),row['packet']))
   sent+=1
  except urllib.error.HTTPError as error:
   with database() as db:db.execute('UPDATE exchange_source_outbox SET state=?,attempts=attempts+1,next_at=? WHERE packet=?',('held' if error.code in {400,401,403,409,413,415,422} else 'pending',time.time()+min(900,2**min(row['attempts']+1,10)),row['packet']))
  except (OSError,ValueError):
   with database() as db:db.execute('UPDATE exchange_source_outbox SET attempts=attempts+1,next_at=? WHERE packet=?',(time.time()+min(900,2**min(row['attempts']+1,10)),row['packet']))
 return {'sent':sent,'examined':len(rows)}


def dashboard_snapshot(config):
 settings=config.get('source_exchange',{})
 if not settings.get('dashboard_enabled'):raise ValueError('Exchange dashboard is not commissioned')
 return transport(settings,'GET','/snapshot')


def event_turn(database,settings,limit=8):
 if not settings.get('events_enabled'):return {'state':'disabled'}
 import uuid,datetime
 scopes=settings.get('event_scopes') or [settings['event_scope']]
 if not isinstance(limit,int) or not 0<=limit<=8:raise ValueError('Event turn exceeds request bound')
 if not isinstance(scopes,list) or not 1<=len(scopes)<=8 or any(not isinstance(scope,dict) or set(scope)!={'application','client'} or scope['application'] not in {'classscout','management','salesleadgenerator'} or not isinstance(scope['client'],str) or not 1<=len(scope['client'])<=80 for scope in scopes) or len({json.dumps(scope,sort_keys=True) for scope in scopes})!=len(scopes):raise ValueError('Bounded unique event scopes required')
 module=modules()
 with database() as db:
  module.initialize(db)
 completed=0
 for turn in range(limit):
  if settings.get('_deadline',time.monotonic()+10)-time.monotonic()<1:break
  with database() as db:
   request=db.execute("SELECT * FROM exchange_event_requests WHERE state='pending' AND next_at<=? ORDER BY CASE WHEN route LIKE '%/receipt' THEN 0 ELSE 1 END,rowid LIMIT 1",(time.time(),)).fetchone()
   request=dict(request) if request else None
  if not request:
   with database() as db:
    cursor=db.execute("SELECT value FROM exchange_selection_cursor WHERE key='event_scope_cursor'").fetchone()
    index=int(cursor[0])%len(scopes) if cursor else 0
    scope=scopes[index]
    pending=db.execute("SELECT 1 FROM exchange_event_requests WHERE route='/events/claim' AND state IN ('pending','held') AND json_extract(body,'$.scope.application')=? AND json_extract(body,'$.scope.client')=? LIMIT 1",(scope['application'],scope['client'])).fetchone()
    db.execute("INSERT INTO exchange_selection_cursor VALUES('event_scope_cursor',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str((index+1)%len(scopes)),))
    if pending:continue
   status=transport(settings,'GET','/status')
   body={'scope':scope,'inbox_id':settings['event_inbox_id'],'broker_generation':status['broker_generation'],'limit':min(5,max(1,limit-turn-2)),'lease_seconds':300}
   with database() as db:db.execute("INSERT INTO exchange_event_requests(id,route,body,state) VALUES(?,'/events/claim',?,'pending')",(str(uuid.uuid4()),json.dumps(body,separators=(',',':')).encode()))
   continue
  claim=json.loads(request['body']) if request['route']=='/events/claim' else None
  if claim and (claim['scope'] not in scopes):
   with database() as db:db.execute("UPDATE exchange_event_requests SET state='held',error='scope-no-longer-enrolled' WHERE id=?",(request['id'],))
   continue
  if claim and limit-turn<1+claim['limit']:break
  try:
   response=transport(settings,'POST',request['route'],bytes(request['body']),request['id'])
   if request['route']=='/events/claim':
    if not isinstance(response.get('items'),list) or len(response['items'])>claim['limit']:raise ValueError('Invalid event claim')
    with database() as db:
     for item in response['items']:
      event=item['event']
      if event['scope']!=claim['scope']:raise ValueError('Event belongs to another scope')
      expires=datetime.datetime.fromisoformat(item['lease_expires_at'].replace('Z','+00:00')).timestamp()
      if expires<=time.time():continue
      module.project(db,event)
      receipt={'scope':event['scope'],'inbox_id':settings['event_inbox_id'],'broker_generation':item['broker_generation'],'lease_token':item['lease_token'],'local_receipt_id':str(uuid.uuid5(uuid.UUID(settings['event_inbox_id']),event['event_id'])),'disposition':'received','reason_code':'event_projection_committed','local_reference':event['event_id']}
      # Receipt intent and causal projection commit together before broker acknowledgement.
      operation=str(uuid.uuid5(uuid.UUID(settings['event_inbox_id']),item['delivery_id']+item['lease_token']))
      db.execute("INSERT OR IGNORE INTO exchange_event_requests(id,route,body,state) VALUES(?,?,?,'pending')",(operation,'/events/'+item['delivery_id']+'/receipt',json.dumps(receipt,separators=(',',':')).encode()))
     for row in db.execute("SELECT e.body FROM exchange_event_inbox e JOIN exchange_projection p ON p.application=e.application AND p.client=e.client AND p.evaluation=e.evaluation WHERE e.revision<=p.revision AND json_extract(e.body,'$.payload.event_type')='gap_report'").fetchall():module.gap_intent(db,json.loads(row[0]))
     db.execute("UPDATE exchange_event_requests SET state='done' WHERE id=?",(request['id'],))
   else:
    if response.get('operation_id')!=request['id'] or response.get('state')!='acknowledged' or response.get('delivery_id')!=request['route'].split('/')[2]:raise ValueError('Invalid event acknowledgement')
    with database() as db:db.execute("UPDATE exchange_event_requests SET state='done' WHERE id=?",(request['id'],))
   completed+=1
  except urllib.error.HTTPError as error:
   code=None
   if error.code==409:
    try:code=json.loads(error.read(4096)).get('code')
    except (ValueError,OSError):pass
   state='stale' if code=='stale_lease' and request['route'].endswith('/receipt') else 'held' if error.code in {400,401,403,409,413,415,422} else 'pending'
   with database() as db:db.execute('UPDATE exchange_event_requests SET state=?,attempts=attempts+1,next_at=?,error=? WHERE id=?',(state,time.time()+min(900,2**min(request['attempts']+1,10)),'http-'+str(error.code),request['id']))
  except (ValueError,KeyError,TypeError):
   with database() as db:db.execute("UPDATE exchange_event_requests SET state='held',error='invalid-response' WHERE id=?",(request['id'],))
  except OSError:
   with database() as db:db.execute('UPDATE exchange_event_requests SET attempts=attempts+1,next_at=?,error=? WHERE id=?',(time.time()+60,'transport-unavailable',request['id']))
 return {'completed':completed}


def deliver_gaps(database,settings,board,config,limit=2):
 if not settings.get('gap_tasks_enabled'):return {'state':'disabled'}
 module=modules()
 from urllib.parse import urlsplit
 with database() as db:
  module.initialize(db)
  rows=[dict(r) for r in db.execute("SELECT * FROM exchange_gap_intents WHERE state='pending' ORDER BY created LIMIT ?",(limit,))]
 delivered=0
 for row in rows:
  if settings.get('_deadline',time.monotonic()+30)-time.monotonic()<26:break
  project=next((p for p,s in settings.get('projects',{}).items() if s=={'application':row['application'],'client':row['client']}),None)
  agent=next((k for k,v in config['agents'].items() if v['role']=='research'),None)
  with database() as db:
   saved=db.execute('SELECT * FROM exchange_native_intents WHERE id=?',(row['id'],)).fetchone()
   event=db.execute("SELECT e.body FROM exchange_event_inbox e JOIN exchange_projection p ON p.application=e.application AND p.client=e.client AND p.evaluation=e.evaluation WHERE e.revision<=p.revision AND e.application=? AND e.client=? AND json_extract(e.body,'$.payload.candidate_ref')=? AND json_extract(e.body,'$.payload.evidence_fingerprint')=? ORDER BY e.revision DESC LIMIT 1",(row['application'],row['client'],row['candidate'],row['fingerprint'])).fetchone()
  if not project or not agent or not event:continue
  if saved and saved['next_at']>time.time():continue
  value=json.loads(event[0]);url=value['payload'].get('source_url')
  if not url or urlsplit(url).scheme!='https':continue
  body=json.loads(saved['body']) if saved else {'idempotencyKey':row['id'],'allowDuplicate':True,'title':'Resolve evidence gap: '+row['client']+' '+row['gap'],'projectId':project,'status':'todo','assigneeAgentId':agent,'reviewPolicy':'anyone','description':'Factory workflow: source_research\nOpenClaw gap request: '+row['id']+'\nMissing evidence fields: '+row['gap']+'\n\n'+url+'\n\nFind independent official evidence for the stated fields. Source ownership, branch and client rules remain mandatory. No catalog mutation or customer message is permitted.'}
  with database() as db:db.execute('INSERT OR IGNORE INTO exchange_native_intents(id,body) VALUES(?,?)',(row['id'],json.dumps(body,separators=(',',':')).encode()))
  try:
   result=board.call('/companies/'+config['company_id']+'/issues',body)
   if result.get('companyId')!=config['company_id'] or result.get('projectId')!=project or result.get('description')!=body['description'] or result.get('title')!=body['title'] or not isinstance(result.get('id'),str) or not 1<=len(result['id'])<=128:raise ValueError('Native receipt does not match intent')
   with database() as db:db.execute("UPDATE exchange_gap_intents SET state='delivered',native_task=? WHERE id=?",(result['id'],row['id']))
   delivered+=1
  except (ValueError,RuntimeError,OSError):
   with database() as db:db.execute('UPDATE exchange_native_intents SET attempts=attempts+1,next_at=? WHERE id=?',(time.time()+300,row['id']))
 return {'delivered':delivered}


def coordinate(database,settings,board,config):
 if not any(settings.get(key) for key in ['offers_enabled','events_enabled','gap_tasks_enabled']):return {'state':'disabled'}
 settings={**settings,'_deadline':time.monotonic()+30}
 try:
  return {'offers':sync_offers(database,settings),'events':event_turn(database,settings),'gaps':deliver_gaps(database,settings,board,config)}
 except (OSError,ValueError,RuntimeError,KeyError,TypeError) as error:
  # A transport outage cannot prevent the existing native coordination turn.
  return {'state':'held','reason':type(error).__name__}
