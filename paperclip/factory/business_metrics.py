"""Read-only business funnel; no source snippets, credentials or customer questions."""
import collections,datetime,json,time,urllib.request,statistics
from pathlib import Path
from zoneinfo import ZoneInfo
import publishing,catalog
from search_budget import Budget

def snapshot(database,config,tasks=None,agents=None):
 live=tasks is None
 catalog.initialize(database)
 if tasks is None:
  url='http://127.0.0.1:3100/api/companies/'+config['company_id']+'/issues'
  with urllib.request.urlopen(url,timeout=20) as r:tasks=json.load(r)
  tasks=tasks if isinstance(tasks,list) else tasks.get('issues',[])
 tasks={r['id']:r for r in tasks if r.get('companyId')==config['company_id'] and '[Factory test]' not in r.get('title','')}
 def count(db,table,column='status'):
  if not db.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():return {}
  return dict(collections.Counter(r[0] for r in db.execute('SELECT '+column+' FROM '+table)))
 with database() as db:
  known={r['provider_id']:json.loads(r['result_json']).get('provider',{}) for r in db.execute('SELECT provider_id,result_json FROM catalog_checks')};entities=[dict(r) for r in db.execute('SELECT * FROM entities') if r['issue_id'] in tasks];groups={};states=collections.Counter(e['status'] for e in entities)
  for e in entities:
   issue=tasks[e['issue_id']];target=known.get(catalog.field(issue,'Catalog provider'),{});borough=catalog.field(issue,'Borough') or catalog.field(issue,'Discovery borough') or target.get('borough') or 'Unclassified';activity=catalog.field(issue,'Activity') or catalog.field(issue,'Discovery activity') or ', '.join(target.get('activityTypes',[])) or 'Unclassified';key=(borough,activity)
   row=groups.setdefault(key,{'borough':borough,'activity':activity,'research_drafts':0,'source_checked':0,'published':0});row['research_drafts']+=1;row['source_checked']+=e['status']=='ready_for_human_review'
  packets=[]
  if db.execute("SELECT 1 FROM sqlite_master WHERE name='publication_packets'").fetchone():packets=[dict(r) for r in db.execute('SELECT status,proof_json,issue_id FROM publication_packets') if r['issue_id'] in tasks]
  for p in packets:
   n=json.loads(p['proof_json']).get('normalized',{});key=(n.get('boroughRaw','Unclassified'),', '.join(n.get('activityTypesRaw',[])) or 'Unclassified');row=groups.setdefault(key,{'borough':key[0],'activity':key[1],'research_drafts':0,'source_checked':0,'published':0});row['published']+=p['status']=='published'
  published=sum(p['status']=='published' for p in packets);updates=count(db,'refresh_packets');program_updates=count(db,'program_packets');updates['applied']=updates.get('applied',0)+program_updates.get('applied',0);searches=count(db,'search_attempts');recovery=[]
  if db.execute("SELECT 1 FROM sqlite_master WHERE name='evidence_recovery'").fetchone():recovery=[json.loads(r[0]) for r in db.execute('SELECT result_json FROM evidence_recovery')]
  padel_report=db.execute("SELECT result_json FROM workflow_reports WHERE kind IN ('padel_maintenance','engine_padel-africa') ORDER BY created_at DESC LIMIT 1").fetchone()
  now=datetime.datetime.now(datetime.timezone.utc);since=(now-datetime.timedelta(hours=24)).isoformat();runs=dict(collections.Counter(r[0] for r in db.execute('SELECT status FROM runs WHERE started_at>?',(since,))))
  attempts=db.execute('SELECT count(*) FROM automatic_decisions WHERE submitted_at IS NOT NULL').fetchone()[0] if db.execute("SELECT 1 FROM sqlite_master WHERE name='automatic_decisions'").fetchone() else 0
 operations=operating_snapshot(database,config,list(tasks.values()),agents,live)
 delivery=delivery_snapshot(database,config,tasks)
 blocked=[{'identifier':r['identifier'],'title':r['title'],'url':'https://paperclip.haho.ai/NAR/issues/'+r['identifier']} for r in tasks.values() if r['status']=='blocked']
 return {**operations,'delivery':delivery,'updated_at':publishing.stamp(),'timezone':'Europe/Budapest','mode':'Growth mode' if config.get('growth_mode',{}).get('enabled') else 'Standard','funnel':{'research_drafts':len(entities),'source_checked':states['ready_for_human_review'],'needs_evidence':states['needs_more_evidence'],'published':published,'updates_verified':updates.get('applied',0),'writes_uncertain':updates.get('uncertain',0)+program_updates.get('uncertain',0)+program_updates.get('partial',0)+sum(p['status'] in {'uncertain','partial','publishing'} for p in packets),'write_attempts_total':attempts},'source_states':dict(states),'updates':updates,'last_24h_runs':runs,'by_market':list(groups.values()),'blocked':blocked[:30],'search_budget':Budget(database).status(),'daily_write_limit':config.get('automatic_quality_gate',{}).get('daily_write_limit',0),'recovery':{'attempts':len(recovery),'fields_recovered':sum(len(r.get('recovered_fields',r.get('added_fields',[]))) for r in recovery)},'padel':json.loads(padel_report[0]) if padel_report else {'tenant_verified':False,'status':'No connection run yet'},'definitions':{'published':'Confirmed ClassScout private save and matching core public catalog read.','source_checked':'Name/address evidence passed; this does not establish complete publication readiness.','by_market':'Research intent groups; source claims are separately checked.','write_attempts_total':'Reservations across catalog writes and evidence intake, including uncertain replies.','model_usage':'Free local model usage; token counts cover recorded successful extraction calls only. Hosting is separate.'}}


def epoch(value):
 try:return datetime.datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
 except (ValueError,TypeError,AttributeError):return None

def next_schedule(cron,now):
 """Next configured minute/hour occurrence; unsupported expressions stay unknown."""
 fields=cron.split()
 if len(fields)!=5 or fields[2:]!=['*','*','*']:return None
 def matches(value,field):
  if field=='*':return True
  if field.startswith('*/'):return value%int(field[2:])==0
  return value in [int(x) for x in field.split(',')]
 try:
  for offset in range(1,24*60+1):
   stamp=(int(now)//60+offset)*60
   local=datetime.datetime.fromtimestamp(stamp,ZoneInfo('Europe/Budapest'))
   if matches(local.minute,fields[0]) and matches(local.hour,fields[1]):return stamp
 except (ValueError,ZeroDivisionError):pass
 return None

def operating_snapshot(database,config,tasks,agents=None,live=False,clock=time.time):
 now=clock();since=now-86400;today=datetime.datetime.fromtimestamp(now,ZoneInfo('Europe/Budapest')).date().isoformat()
 available=True
 if agents is None:
  agents=[]
  if live:
   try:
    with urllib.request.urlopen('http://127.0.0.1:3100/api/companies/'+config['company_id']+'/agents',timeout=5) as response:agents=json.load(response)
   except (OSError,ValueError):available=False
 by_id={t['id']:t for t in tasks};active={'todo','in_progress','in_review','blocked'}
 def link(t):return {'identifier':t.get('identifier',''),'title':t.get('title',''),'status':t.get('status'),'url':'/NAR/issues/'+t.get('identifier','')}
 with database() as db:
  rows=[dict(r) for r in db.execute('SELECT id,issue_id,agent_id,role,status,result,started_at,finished_at FROM runs') if r['issue_id'] in by_id]
  recent=[r for r in rows if (epoch(r['started_at']) or 0)>=since]
  waits=[dict(r) for r in db.execute('SELECT issue_id,next_at FROM model_waits') if r['issue_id'] in by_id]
  writes_today=0
  if db.execute("SELECT 1 FROM sqlite_master WHERE name='automatic_decisions'").fetchone():
   writes_today=sum(datetime.datetime.fromtimestamp(r[0],ZoneInfo('Europe/Budapest')).date().isoformat()==today for r in db.execute('SELECT submitted_at FROM automatic_decisions WHERE submitted_at IS NOT NULL'))
 tokens=0;calls=0;models=set();contexts=set();durations=[]
 for r in recent:
  if r['status']=='completed' and epoch(r['finished_at']) is not None:
   durations.append(max(0,epoch(r['finished_at'])-(epoch(r['started_at']) or epoch(r['finished_at']))))
  try:result=json.loads(r['result'] or '{}')
  except ValueError:continue
  for m in result.get('model_metrics',result.get('metrics',[])) or []:
   if not isinstance(m,dict):continue
   usage=m.get('usage') or {}
   if usage.get('total_tokens') is not None:tokens+=usage['total_tokens'];calls+=1
   if m.get('model'):models.add(m['model'])
   if m.get('context'):contexts.add(m['context'])
 team=[]
 for a in agents:
  assigned=[t for t in tasks if t.get('assigneeAgentId')==a['id'] and t.get('status') in active]
  history=sorted([r for r in rows if r['agent_id']==a['id']],key=lambda r:r['started_at'],reverse=True)
  last=history[0] if history else None
  team.append({'name':a.get('name','Agent'),'status':a.get('status','unknown'),'url':'/NAR/agents/'+a['id'],'assigned':len(assigned),'blocked':sum(t['status']=='blocked' for t in assigned),'completed_24h':sum(r['agent_id']==a['id'] and r['status']=='completed' for r in recent),'last_run_at':last['finished_at'] or last['started_at'] if last else None,'last_outcome':last['status'] if last else None,'tasks':[link(t) for t in assigned[:3]]})
 projects=[]
 for id,name in config.get('projects',{}).items():
  selected=[t for t in tasks if t.get('projectId')==id];counts=collections.Counter(t['status'] for t in selected)
  projects.append({'name':name,'url':'/NAR/projects/'+id,'queued':counts['todo'],'working':counts['in_progress'],'review':counts['in_review'],'blocked':counts['blocked'],'done_24h':sum(t['status']=='done' and (epoch(t.get('completedAt') or t.get('updatedAt')) or 0)>=since for t in selected),'mode':'Automatic research and publishing' if name=='ClassScout' else 'Discovery, verified source intake and daily checks' if name=='Padel Africa' and config.get('padel_discovery_enabled') else 'Daily catalog checks; source intake on demand' if name=='Padel Africa' and config.get('padel_enabled') else 'Shared engine oversight · Padel Africa + Sportolok' if name=='Management' and config.get('engine_clients') else 'Engine discovery + maintenance · Hungarian source text' if name=='Sportolok' and config.get('engine_clients',{}).get('sportolok') else 'Company operations' if name=='Factory Operations' else 'Workspace and scoped key required' if name=='Sales Lead Generator' and not config.get('sales',{}).get('brands') else 'Workspace-scoped pipeline and sales preparation' if name=='Sales Lead Generator' else 'Not activated'})
 try:routines=json.loads(Path(__file__).with_name('workflows.json').read_text()).get('routines',[])
 except (OSError,ValueError):routines=[]
 upcoming=[{'title':r['title'],'url':'/NAR/routines/'+r['id'],'next_at':next_schedule(r['cron'],now),'timezone':'Europe/Budapest'} for r in routines if r.get('enabled') and r.get('cron')]
 upcoming.sort(key=lambda r:r['next_at'] or float('inf'))
 activity=[]
 for r in sorted(rows,key=lambda r:r['finished_at'] or r['started_at'],reverse=True)[:12]:
  activity.append({**link(by_id[r['issue_id']]),'outcome':r['status'],'role':r['role'],'at':r['finished_at'] or r['started_at']})
 outcomes=collections.Counter(r['status'] for r in recent);finished=sum(outcomes[k] for k in ['completed','failed','blocked'])
 return {'operations':{'task_counts':dict(collections.Counter(t['status'] for t in tasks)),'runs_24h':dict(outcomes),'completion_rate_24h':round(100*outcomes['completed']/finished) if finished else None,'median_run_seconds_24h':round(statistics.median(durations),1) if durations else None,'model_waits':len(waits),'writes_today':writes_today,'team_available':available,'team':team,'projects':projects,'activity':activity,'upcoming':upcoming[:7]},'inference':{'billing':'Free local models','tokens_24h':tokens,'recorded_calls_24h':calls,'models':sorted(models),'contexts':sorted(contexts),'generation_slots':1,'coverage':'Recorded successful extraction calls only; other work and failed calls may not report tokens.'}}


def delivery_snapshot(database,config,tasks,clock=time.time):
 now=clock();blocked=[];times=[];repeats=0;knowledge={};freshness={};intake={};verified=0;searches=0
 def exists(db,name):return db.execute('SELECT 1 FROM sqlite_master WHERE name=?',(name,)).fetchone()
 with database() as db:
  continued={r['source_issue']:r['target_issue'] for r in db.execute("SELECT source_issue,target_issue FROM autonomous_recovery WHERE status='handed_off'")} if exists(db,'autonomous_recovery') else {}
  policies={r['issue_id']:dict(r) for r in db.execute('SELECT * FROM company_blockers')} if exists(db,'company_blockers') else {}
  for task in tasks.values():
   if task['status']!='blocked':continue
   last=db.execute("SELECT finished_at,status,error,result FROM runs WHERE issue_id=? ORDER BY started_at DESC LIMIT 1",(task['id'],)).fetchone()
   at=epoch(task.get('blockedTransitionAt')) or (epoch(last[0]) if last else epoch(task.get('updatedAt')));policy=policies.get(task['id'],{})
   import company_ops
   message=(last['error'] or json.loads(last['result'] or '{}').get('summary','')) if last else ''
   category,action=company_ops.classify(message)
   needs_owner=category in {'write_verification','input_review'} or bool(last and last['status']=='failed')
   blocked.append({'identifier':task.get('identifier'),'category':category,'action':action,'needs_owner':needs_owner,'continuation_url':('/NAR/issues/'+continued[task['id']]) if task['id'] in continued else None,'age_hours':round(max(0,now-at)/3600,1) if at else None,'age_basis':'blocked transition' if task.get('blockedTransitionAt') else 'last blocked worker run' if last else 'last task update','next_check_at':policy.get('next_at'),'recovery_attempts':policy.get('attempts',0)})
  if exists(db,'publication_packets'):
   for p in db.execute("SELECT issue_id,updated_at FROM publication_packets WHERE status='published'"):
    if p['issue_id'] not in tasks:continue
    verified+=1;t=tasks[p['issue_id']];start=epoch(t.get('createdAt'));seen=set()
    while t.get('parentId') in tasks and t['parentId'] not in seen:
     seen.add(t['parentId']);t=tasks[t['parentId']];candidate=epoch(t.get('createdAt'))
     if candidate is not None:start=min(start or candidate,candidate)
    end=epoch(p['updated_at'])
    if start is not None and end is not None and end>=start:times.append((end-start)/3600)
  if exists(db,'refresh_packets'):verified+=sum(r['issue_id'] in tasks for r in db.execute("SELECT issue_id FROM refresh_packets WHERE status='applied'"))
  if exists(db,'program_packets'):verified+=sum(r['issue_id'] in tasks for r in db.execute("SELECT issue_id FROM program_packets WHERE status='applied'"))
  if exists(db,'search_attempts'):searches=db.execute('SELECT count(*) FROM search_attempts').fetchone()[0]
  signatures=collections.Counter()
  for r in db.execute('SELECT issue_id,result,started_at FROM runs WHERE result IS NOT NULL'):
   if r['issue_id'] not in tasks or (epoch(r['started_at']) or 0)<now-86400:continue
   v=json.loads(r['result']);stage=v.get('stage','');status=v.get('status')
   if status in {'blocked','in_review'}:signatures[(r['issue_id'],stage,status)]+=1
  repeats=sum(max(0,n-1) for n in signatures.values())
  if exists(db,'support_knowledge'):
   knowledge=dict(collections.Counter(('expired' if r['expires_at']<=now else r['status']) for r in db.execute('SELECT status,expires_at FROM support_knowledge')))
  if exists(db,'freshness_checks'):freshness=dict(collections.Counter(json.loads(r[0]).get('status') for r in db.execute('SELECT result_json FROM freshness_checks')))
  if exists(db,'padel_packets'):intake=dict(collections.Counter(r[0] for r in db.execute('SELECT status FROM padel_packets')))
 blocked.sort(key=lambda r:-(r['age_hours'] or 0))
 with database() as db:
  unanswered=sum(bool(json.loads(r[0]).get('needs_human')) for r in db.execute("SELECT result_json FROM workflow_reports WHERE kind='support_answer'")) if exists(db,'workflow_reports') else 0
  coordination=dict(collections.Counter(r[0] for r in db.execute('SELECT status FROM company_dispatch'))) if exists(db,'company_dispatch') else {}
 engines={}
 with database() as db:
  if exists(db,'workflow_reports'):
   for slug in ['padel-africa','sportolok']:
    r=db.execute('SELECT result_json FROM workflow_reports WHERE kind=? ORDER BY created_at DESC LIMIT 1',('engine_'+slug,)).fetchone()
    if r:engines[slug]=json.loads(r[0])
 with database() as db:programs=dict(collections.Counter(r[0] for r in db.execute('SELECT status FROM program_packets'))) if exists(db,'program_packets') else {}
 try:backup=json.loads(Path(__file__).with_name('backup-status.json').read_text())
 except (OSError,ValueError):backup={'status':'Not configured'}
 try:restore=json.loads(Path(__file__).with_name('restore-drill-latest.json').read_text());backup['restore_status']=restore.get('status','Unknown');backup['restore_completed_at']=restore.get('completed_at')
 except (OSError,ValueError):pass
 sales={'status':'Awaiting workspace and scoped key','delivery':'Not configured','tool_count':6}
 with database() as db:
  if exists(db,'workflow_reports'):
   r=db.execute("SELECT result_json FROM workflow_reports WHERE kind='sales_connection' ORDER BY created_at DESC LIMIT 1").fetchone()
   if r:
    v=json.loads(r[0]);sales.update(status=v.get('status','Unknown'),brand=v.get('brand'),checked_at=v.get('checked_at'))
  if exists(db,'slg_packets'):sales['crm_writes']=dict(collections.Counter(r[0] for r in db.execute('SELECT status FROM slg_packets')))
 automation={'status':'Awaiting first scheduled run','pending_handoffs':coordination.get('queued',0)}
 with database() as db:
  if exists(db,'autonomy_ticks'):
   r=db.execute('SELECT report_json,created_at FROM autonomy_ticks ORDER BY created_at DESC LIMIT 1').fetchone()
   if r:
    v=json.loads(r['report_json']);automation.update(status='Running' if now-r['created_at']<900 else 'Check overdue',last_checked_at=r['created_at'],handoffs_delivered_last_run=len(v.get('handoffs_delivered',[])),continuations_last_run=len(v.get('continuations',{}).get('delivered',[])))
  if exists(db,'autonomous_recovery'):automation['recovery_states']=dict(collections.Counter(r[0] for r in db.execute('SELECT status FROM autonomous_recovery')))
 return {'automation':automation,'sales':sales,'engines':engines,'program_updates':programs,'backup':backup,'coordination':coordination,'unanswered_support_cases':unanswered,'blocked_details':blocked,'waiting_evidence_count':sum(not r['needs_owner'] for r in blocked),'owner_attention_count':sum(r['needs_owner'] for r in blocked),'continued_history_count':sum(bool(r.get('continuation_url')) for r in blocked),'median_hours_to_publication':round(statistics.median(times),2) if times else None,'publication_timing_samples':len(times),'verified_results_per_search':round(verified/searches,2) if searches else None,'verified_results':verified,'search_requests':searches,'repeated_wait_or_hold_runs_24h':repeats,'knowledge':knowledge,'freshness':freshness,'padel_intake':intake,'definitions':{'timing':'First linked ancestor task creation to confirmed publication; only available linked histories.','search_yield':'Cumulative verified publications plus verified updates divided by shared search attempts; not causal attribution.','repeats':'Repeated recorded waiting/held stages on the same task in 24h; can include legitimate cooldown checks.'}}
