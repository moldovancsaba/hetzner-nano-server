"""Opt-in exchange hooks inside existing factory transactions and coordination turns."""
import importlib
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def modules():
 root=Path(os.environ.get('SOURCE_EXCHANGE_MODULES',str(Path(__file__).resolve().parent.parent/'integration')))
 if str(root) not in sys.path:sys.path.insert(0,str(root))
 return importlib.import_module('exchange.factory')


def save_offer(db,config,issue,page,facts):
 settings=config.get('source_exchange',{})
 if not settings.get('offers_enabled'):return None
 scope=settings.get('projects',{}).get(issue.get('projectId'))
 if scope is None:return None
 module=modules()
 from exchange.contract import ExchangeError
 try:return module.offer(db,scope,issue['id'],page,facts,settings['policy_revision'],source_kind='directory_lead',reuse_unchanged=True)
 except (ValueError,ExchangeError) as error:
  logging.warning('source_offer_held type=%s application=%s client=%s',type(error).__name__,scope['application'],scope['client'])
  return None


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


def transport(settings,method,route,body=None,operation=None):
 if not route.startswith('/') or '?' in route or '..' in route:raise ValueError('Invalid exchange route')
 path=Path(settings['token_file'])
 if path.stat().st_mode & 0o077:raise ValueError('Exchange credential must be private')
 token=path.read_text().strip()
 if len(token)<32:raise ValueError('Invalid exchange credential')
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
