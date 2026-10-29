"""Scheduled company recovery: durable handoffs, bounded successors, no write replay."""
import json,time
import catalog,company_ops,publishing
READ_ROLES={'source_research':'research','source_quality':'quality','verify_catalog':'support','engine_candidate':'support'}
# A released parser contract may earn one recheck per lineage, never one per tick.
CONTRACTS={'source_research':('literal-identity-v1',('no source-supported fields','no source-backed draft')),'engine_candidate':('venue-links-v2',('does not uniquely establish',))}
TERMINAL_RUNS={'failed','cancelled','timed_out','succeeded'}

def initialize(database):
 company_ops.initialize(database)
 with database() as db:db.executescript('''
 CREATE TABLE IF NOT EXISTS autonomous_recovery(request_key TEXT PRIMARY KEY,root_issue TEXT,source_issue TEXT,condition_hash TEXT,input_hash TEXT,body_json TEXT,status TEXT,target_issue TEXT,created_at REAL,next_at REAL,attempts INTEGER,error_category TEXT);
 CREATE TABLE IF NOT EXISTS autonomy_ticks(id TEXT PRIMARY KEY,report_json TEXT,created_at REAL);
 ''')

def protected(database,issue):
 with database() as db:
  for table in ['publication_packets','refresh_packets','program_packets','engine_packets','slg_packets']:
   if db.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone() and db.execute('SELECT 1 FROM '+table+' WHERE issue_id=?',(issue['id'],)).fetchone():return True
 return False

def snapshot(issue):return publishing.sha({'description':issue.get('description'),'title':issue['title'],'project':issue['projectId']})
def eligible(issue,config):
 kind=catalog.field(issue,'Factory workflow');brand=config.get('projects',{}).get(issue.get('projectId'))
 return (issue.get('companyId')==config['company_id'] and issue.get('status')=='blocked' and not issue.get('title','').startswith('[Factory test]')
  and ((brand=='ClassScout' and kind in {'source_research','source_quality','verify_catalog'}) or (brand in {'Padel Africa','Sportolok'} and kind=='engine_candidate')))

def stopped(issue,board,database):
 """A reported blocker alone never proves the provider is stopped."""
 with database() as db:
  if db.execute("SELECT 1 FROM runs WHERE issue_id=? AND status='running'",(issue['id'],)).fetchone():return False
 run_id=(issue.get('executionBlocker') or {}).get('runId') or issue.get('executionRunId')
 if run_id:
  run=board.call('/heartbeat-runs/'+run_id)
  if run.get('companyId')!=issue['companyId'] or run.get('status') not in TERMINAL_RUNS:return False
 return True

def root_for(issue,database):
 with database() as db:
  row=db.execute('SELECT root_issue FROM autonomous_recovery WHERE target_issue=? ORDER BY created_at LIMIT 1',(issue['id'],)).fetchone()
 return row['root_issue'] if row else issue['id']

def condition(issue,database):
 kind=catalog.field(issue,'Factory workflow')
 with database() as db:r=db.execute('SELECT status,error,result FROM runs WHERE issue_id=? ORDER BY started_at DESC LIMIT 1',(issue['id'],)).fetchone()
 message=((r['error'] or json.loads(r['result'] or '{}').get('summary','')) if r else '').casefold()
 contract=CONTRACTS.get(kind)
 if kind=='engine_candidate' and catalog.field(issue,'Branch depth','0')!='0':contract=None
 if contract and any(term in message for term in contract[1]):return {'kind':'parser_contract','version':contract[0]}
 blocker=issue.get('executionBlocker') or {}
 # Evidence failure, human rejection, source restrictions and model waits do not
 # become transport failures just because an execution was stopped afterwards.
 if r and r['status']=='blocked':return None
 if blocker and blocker.get('runStatus') in TERMINAL_RUNS:return {'kind':'stopped_execution','cause':blocker.get('cause','stopped')}
 return None

def plan(tasks,board,config,database,clock=time.time):
 initialize(database);now=clock();planned=[];skipped={}
 for issue in sorted(tasks,key=lambda x:x.get('updatedAt') or ''):
  if len(planned)>=2:break
  if not eligible(issue,config):continue
  if protected(database,issue):skipped[issue['id']]='protected_packet';continue
  why=condition(issue,database)
  if not why:continue
  root=root_for(issue,database)
  with database() as db:history=[dict(r) for r in db.execute('SELECT * FROM autonomous_recovery WHERE root_issue=? ORDER BY created_at',(root,))]
  if len(history)>=3 or history and now<history[-1]['created_at']+900:continue
  # Identical parser repair cannot keep earning retries through its descendants.
  cond=publishing.sha(why)
  if why['kind']=='parser_contract' and any(h['condition_hash']==cond for h in history):continue
  if any(h['source_issue']==issue['id'] for h in history):continue
  if not stopped(issue,board,database):skipped[issue['id']]='execution_active';continue
  fresh=board.call('/issues/'+issue['id'])
  if not eligible(fresh,config) or snapshot(fresh)!=snapshot(issue):continue
  kind=catalog.field(fresh,'Factory workflow');agent=company_ops.role(config,READ_ROLES[kind]);key='auto-recovery-'+publishing.sha({'root':root,'source':issue['id'],'condition':cond})
  body={'idempotencyKey':key,'title':'Automatic evidence recovery: '+fresh['title'][-105:],'description':fresh.get('description','')+'\nAutomatic recovery root: '+root+'\nRecovery of: '+fresh['id'],'projectId':fresh['projectId'],'status':'todo','assigneeAgentId':agent,'reviewPolicy':fresh.get('reviewPolicy') or 'anyone'}
  with database() as db:
   db.execute('BEGIN IMMEDIATE')
   if db.execute('SELECT count(*) FROM autonomous_recovery WHERE root_issue=?',(root,)).fetchone()[0]>=3:continue
   changed=db.execute('INSERT OR IGNORE INTO autonomous_recovery VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(key,root,fresh['id'],cond,snapshot(fresh),json.dumps(body),'queued',None,now,now,0,None)).rowcount
  if changed:planned.append({'source':issue.get('identifier'),'condition':why['kind'],'request_key':key})
 return {'planned':planned,'skipped':skipped}

def deliver(board,config,database,clock=time.time):
 initialize(database);now=clock();delivered=[];held=[]
 with database() as db:requests=[dict(r) for r in db.execute("SELECT * FROM autonomous_recovery WHERE status IN ('queued','creating','delivered') AND next_at<=? ORDER BY created_at LIMIT 4",(now,))]
 for request in requests:
  try:
   source=board.call('/issues/'+request['source_issue'])
   if not eligible(source,config) or snapshot(source)!=request['input_hash'] or protected(database,source) or not stopped(source,board,database):
    with database() as db:db.execute("UPDATE autonomous_recovery SET status='held',error_category='changed_or_protected' WHERE request_key=?",(request['request_key'],))
    held.append(request['source_issue']);continue
   body=json.loads(request['body_json'])
   if request['target_issue']:
    child=board.call('/issues/'+request['target_issue'])
   else:
    with database() as db:db.execute("UPDATE autonomous_recovery SET status='creating' WHERE request_key=?",(request['request_key'],))
    # Native task creation is idempotent: a lost reply retries only this same key.
    child=board.call('/companies/'+config['company_id']+'/issues',body)
   if child.get('companyId')!=config['company_id'] or child.get('projectId')!=source['projectId'] or not child.get('id'):raise ValueError('Invalid recovery task receipt')
   with database() as db:db.execute("UPDATE autonomous_recovery SET status='delivered',target_issue=?,error_category=NULL WHERE request_key=?",(child['id'],request['request_key']))
   fresh=board.call('/issues/'+source['id'])
   if snapshot(fresh)!=request['input_hash'] or not eligible(fresh,config) or protected(database,fresh) or not stopped(fresh,board,database):raise ValueError('Source changed before recovery handoff')
   # Native blocked-history transitions need resume authority. Retain the
   # original unchanged; the ledger and successor description link the handoff.
   with database() as db:db.execute("UPDATE autonomous_recovery SET status='handed_off' WHERE request_key=?",(request['request_key'],))
   delivered.append({'source':source.get('identifier'),'continuation':child.get('identifier'),'original_retained':True})
  except Exception as error:
   count=request['attempts']+1
   with database() as db:db.execute('UPDATE autonomous_recovery SET attempts=?,next_at=?,status=?,error_category=? WHERE request_key=?',(count,now+[60,300,900][min(count-1,2)],'needs_attention' if count>=3 else ('delivered' if db.execute('SELECT target_issue FROM autonomous_recovery WHERE request_key=?',(request['request_key'],)).fetchone()[0] else 'creating'),type(error).__name__,request['request_key']))
 return {'delivered':delivered,'held':held}

def run(issue,board,config,web,database,execution):
 if not config.get('reliability_enabled') or config['projects'].get(issue.get('projectId'))!='Factory Operations':raise ValueError('Autonomous coordination is not enabled in this project')
 initialize(database)
 handoffs=company_ops.dispatch_pending(board,config,database,limit=10)
 tasks=company_ops.issue_rows(board,config);planning=plan(tasks,board,config,database);delivery=deliver(board,config,database)
 with database() as db:
  queued=db.execute("SELECT count(*) FROM company_dispatch WHERE status='queued'").fetchone()[0]
  oldest=db.execute("SELECT min(created_at) FROM autonomous_recovery WHERE status IN ('queued','creating','delivered')").fetchone()[0]
 report={'checked_at':time.time(),'handoffs_delivered':handoffs,'pending_handoffs':queued,'recovery':planning,'continuations':delivery,'oldest_recovery_wait_seconds':max(0,time.time()-oldest) if oldest else 0,'no_business_write_replay':True}
 with database() as db:db.execute('INSERT OR REPLACE INTO autonomy_ticks VALUES(?,?,?)',(issue['id'],json.dumps(report),time.time()))
 catalog.save_report(database,issue,'autonomous_coordination',report)
 return {'stage':'autonomous_coordination','entities':[],'final_status':'done','automatic_progress':True,'markdown':'Automatic coordination completed. Handoffs delivered: '+str(len(handoffs))+'. Remaining handoffs: '+str(queued)+'. Safe continuations: '+str(len(delivery['delivered']))+'. Evidence holds and all protected write packets remain guarded.'}
