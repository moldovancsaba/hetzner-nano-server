"""Reviewed source-only project routing through the existing search lane and allowance."""
import hashlib
import json
import re
import time
import uuid

import catalog
import source_exchange


CLIENTS={'classscout':{'BOS','LA'},'salesleadgenerator':{'cogmap','seyu','dvsc'}}


def project(config,project_id):
 settings=config.get('source_exchange',{});plans=settings.get('source_only_projects',{})
 if not isinstance(plans,dict) or len(plans)>5:raise ValueError('Bounded source-only project configuration required')
 if project_id not in plans:
  scope=settings.get('projects',{}).get(project_id,{})
  if isinstance(scope,dict) and scope.get('client') in CLIENTS.get(scope.get('application'),set()):raise ValueError('Enrolled source-only project runtime is missing')
  return None
 plan=plans[project_id];scope=settings.get('projects',{}).get(project_id)
 if settings.get('offers_enabled') is not True or settings.get('events_enabled') is not True:raise ValueError('Source-only project transport is paused')
 if (not isinstance(plan,dict) or not isinstance(scope,dict) or set(scope)!={'application','client'}
     or scope.get('application') not in CLIENTS or scope.get('client') not in CLIENTS[scope['application']]
     or plan.get('scope')!=scope or plan.get('mode')!='source-only'
     or config.get('projects',{}).get(project_id)!='Sources: '+scope['application']+'/'+scope['client']):raise ValueError('Exact source-only project and scope required')
 if list(settings.get('projects',{}).values()).count(scope)!=1:raise ValueError('Source-only scope has ambiguous producer projects')
 reference=source_exchange.project_policy(settings,project_id,scope)
 source_exchange.scoped_credentials(settings,scope)
 if plan.get('review_ref')!=reference or not re.fullmatch('[a-f0-9]{64}',str(plan.get('query_policy_sha256',''))):raise ValueError('Source query policy needs its exact independent review')
 receipts=settings.get('source_enrollments',{}).values()
 if not any(row.get('scope')==scope and row.get('review_ref')==reference and re.fullmatch('[a-f0-9]{64}',str(row.get('manifest_sha256',''))) for row in receipts):raise ValueError('Source-only project enrollment receipt required')
 queries=plan.get('queries')
 if not isinstance(queries,list) or not 1<=len(queries)<=24 or any(not isinstance(q,str) for q in queries) or len(set(queries))!=len(queries):raise ValueError('Bounded unique source-only queries required')
 import search_workflow
 from brave import Brave
 if (plan.get('country'),plan.get('language')) not in {('US','en'),('ZA','en'),('ALL','hu')}:raise ValueError('Reviewed source locale required')
 Brave(None,country=plan['country'],language=plan['language'])
 for query in queries:
  search_workflow.parse({'description':'Search purpose: discovery\nSearch query: '+query})
 if type(plan.get('minimum_interval_seconds')) is not int or not 86400<=plan['minimum_interval_seconds']<=7*86400:raise ValueError('Reviewed source dispatch interval required')
 return dict(plan)


def require_search_issue(config,issue,role):
 plan=project(config,issue.get('projectId'))
 if plan is None:return None
 if role!='search' or catalog.field(issue,'Factory workflow')!='exchange_source_search':raise ValueError('Source-only projects cannot enter native business workflows')
 if catalog.field(issue,'Source policy ref')!=plan['review_ref'] or catalog.field(issue,'Source scope')!=plan['scope']['application']+'/'+plan['scope']['client']:raise ValueError('Original source task policy/scope changed')
 import search_workflow
 spec=search_workflow.parse(issue)
 if spec['kind']!='discovery' or spec['host'] or spec['parent'] or spec['parent_hash'] or len(spec['queries'])!=1 or spec['queries'][0] not in plan['queries']:raise ValueError('Source task differs from the reviewed query plan')
 return plan


def body(config,project_id,plan,query,identity):
 agent=next((key for key,value in config['agents'].items() if value['role']=='search'),None)
 if not agent:raise ValueError('Existing search role required')
 scope=plan['scope']
 return {'idempotencyKey':identity,'allowDuplicate':True,'title':'Find public source evidence: '+scope['application']+'/'+scope['client'],'projectId':project_id,'status':'todo','assigneeAgentId':agent,'reviewPolicy':'human_only','description':'Factory workflow: exchange_source_search\nSource scope: '+scope['application']+'/'+scope['client']+'\nSource policy ref: '+plan['review_ref']+'\nSearch purpose: discovery\nSearch query: '+query+'\n\nFetch public pages independently. Search terms are discovery intent, never provider facts. Export bounded non-contact evidence only. Native publication and CRM writes are forbidden; OpenClaw performs application qualification.'}


def coordinate(database,config,board,*,budget=None,clock=time.time,deadline=None):
 settings=config.get('source_exchange',{});plans=settings.get('source_only_projects',{})
 if not plans:return {'state':'disabled'}
 if deadline is not None and deadline-time.monotonic()<26:return {'state':'source-project-turn-budget-hold'}
 if not isinstance(plans,dict) or len(plans)>5:raise ValueError('Bounded reviewed source projects required')
 import search_workflow
 from search_budget import Budget
 with database() as db:source_exchange.modules().initialize(db)
 search_workflow.initialize(database);now=clock();budget=budget or Budget(database);status=budget.status()
 if now<status['next_search_at'] or status['used_today']>=status['daily_limit'] or status['used_this_window']>=status['automatic_limit'] or status['estimated_account_remaining']<=status['reserve']:return {'state':'shared-search-allowance-hold'}
 with database() as db:
  if db.execute("SELECT count(*) FROM search_jobs WHERE status IN ('queued','running','delivery_pending')").fetchone()[0]>=2:return {'state':'search-backlog-hold'}
  last=db.execute("SELECT value FROM exchange_selection_cursor WHERE key='source_project_cursor'").fetchone()
 projects=sorted(plans);last=last[0] if last else ''
 projects=[p for p in projects if p>last]+[p for p in projects if p<=last]
 for project_id in projects:
  plan=project(config,project_id);key='source_project_dispatch:'+project_id
  with database() as db:saved=db.execute('SELECT value FROM exchange_selection_cursor WHERE key=?',(key,)).fetchone()
  saved=json.loads(saved[0]) if saved else None
  if saved and saved.get('delivered_at') and now-saved['delivered_at']<plan['minimum_interval_seconds']:continue
  if saved and saved.get('task_id') and not saved.get('task_completed'):
   task=board.call('/issues/'+saved['task_id'])
   if task.get('companyId')!=config['company_id'] or task.get('projectId')!=project_id:raise ValueError('Source task readback scope mismatch')
   saved['task_completed']=task.get('status') in {'done','cancelled'}
   with database() as db:
    db.execute('INSERT OR REPLACE INTO exchange_selection_cursor VALUES(?,?)',(key,json.dumps(saved)))
    db.execute("INSERT OR REPLACE INTO exchange_selection_cursor VALUES('source_project_cursor',?)",(project_id,))
   return {'state':'prior-source-task-complete' if saved['task_completed'] else 'prior-source-task-active','scope':plan['scope']}
  query=plan['queries'][int(now//plan['minimum_interval_seconds'])%len(plan['queries'])]
  identity=saved['operation'] if saved and not saved.get('task_id') else str(uuid.uuid5(uuid.NAMESPACE_URL,'source-project:'+project_id+':'+plan['review_ref']+':'+str(int(now//(7*86400)))+':'+hashlib.sha256(query.encode()).hexdigest()))
  with database() as db:
   receipt_key='source_project_receipt:'+identity
   if db.execute('SELECT 1 FROM exchange_selection_cursor WHERE key=?',(receipt_key,)).fetchone():continue
   original=db.execute('SELECT * FROM exchange_native_intents WHERE id=?',(identity,)).fetchone()
   request=json.loads(original['body']) if original else body(config,project_id,plan,query,identity)
   require_search_issue(config,request,'search')
   if original and original['next_at']>now:continue
   db.execute('INSERT OR IGNORE INTO exchange_native_intents(id,body) VALUES(?,?)',(identity,json.dumps(request,separators=(',',':')).encode()))
   db.execute('INSERT OR REPLACE INTO exchange_selection_cursor VALUES(?,?)',(key,json.dumps({'operation':identity})))
  try:
   result=board.call('/companies/'+config['company_id']+'/issues',request)
   if (result.get('companyId')!=config['company_id'] or result.get('projectId')!=project_id or result.get('description')!=request['description'] or result.get('title')!=request['title'] or result.get('assigneeAgentId')!=request['assigneeAgentId'] or not isinstance(result.get('id'),str) or not 1<=len(result['id'])<=128):raise ValueError('Source task receipt differs from original intent')
   with database() as db:
    db.execute('INSERT INTO exchange_selection_cursor VALUES(?,?)',(receipt_key,json.dumps({'scope':plan['scope'],'operation':identity,'task_id':result['id'],'delivered_at':now})))
    db.execute('INSERT OR REPLACE INTO exchange_selection_cursor VALUES(?,?)',(key,json.dumps({'operation':identity,'task_id':result['id'],'delivered_at':now})))
    db.execute("INSERT OR REPLACE INTO exchange_selection_cursor VALUES('source_project_cursor',?)",(project_id,))
   return {'state':'source-task-enqueued','scope':plan['scope'],'native_business_writes':False}
  except (OSError,ValueError,RuntimeError):
   with database() as db:db.execute('UPDATE exchange_native_intents SET attempts=attempts+1,next_at=? WHERE id=?',(now+300,identity))
   return {'state':'original-task-intent-uncertain','scope':plan['scope']}
 return {'state':'source-projects-current'}
