"""Bounded recovery, official-source freshness, Padel discovery and support knowledge."""
import datetime,json,re,time,urllib.parse
import catalog,evidence,issue_pages,publishing,search_workflow
from search_budget import Budget


def initialize(database):
 catalog.initialize(database);search_workflow.initialize(database)
 with database() as db:db.executescript('''
 CREATE TABLE IF NOT EXISTS company_blockers(issue_id TEXT PRIMARY KEY,category TEXT,action TEXT,signature TEXT,attempts INTEGER,next_at REAL,last_progress REAL,continuation_id TEXT);
 CREATE TABLE IF NOT EXISTS company_dispatch(request_key TEXT PRIMARY KEY,source_issue TEXT,input_hash TEXT,payload_json TEXT,status TEXT,target_issue TEXT,attempts INTEGER,next_at REAL);
 CREATE TABLE IF NOT EXISTS blocker_sources(issue_id TEXT PRIMARY KEY,source_hash TEXT,checked_at REAL);
 CREATE TABLE IF NOT EXISTS freshness_checks(provider_id TEXT PRIMARY KEY,checked_at REAL,source_hash TEXT,result_json TEXT);
 CREATE TABLE IF NOT EXISTS support_knowledge(provider_id TEXT,topic TEXT,status TEXT,answer_json TEXT,verified_at REAL,expires_at REAL,PRIMARY KEY(provider_id,topic));
 CREATE TABLE IF NOT EXISTS padel_discovery_cursor(id INTEGER PRIMARY KEY CHECK(id=1),position INTEGER);INSERT OR IGNORE INTO padel_discovery_cursor VALUES(1,0);
 ''')

def role(config,name):return next(k for k,v in config['agents'].items() if v['role']==name)
def project(config,name):return next(k for k,v in config['projects'].items() if v==name)
def issue_rows(board,config):
 return [v for v in issue_pages.fetch(board.call,config['company_id']) if v.get('companyId')==config['company_id'] and not v.get('title','').startswith('[Factory test]')]

def classify(message):
 message=message.casefold()
 for pattern,category,action in [
  (r'(?:uncertain|unresolved|partial) (?:engine )?(?:write|submission|correction|publication|receipt|outcome)|(?:write|submission|receipt).*(?:uncertain|unresolved|partial)','write_verification','Reconcile the saved receipt with private and public records. Never resend an uncertain write.'),
  (r'no source-supported fields|no source-backed draft','source_extraction','Recheck the official page and quoted extraction; do not infer missing facts or repeat the unchanged source.'),
  (r'unambiguous_contacts','contact_conflict','Verify one branch-specific contact set; equivalent formatting is compared canonically.'),
  (r'price|fee|tuition','program_price','Find one official program page with an unambiguous stated fee and unit.'),
  (r'\b(?:age|ages|schedule|duration|timetable)\b','program_schedule','Find the specific program age range, weekday, start time and duration on an official page.'),
  (r'\b(?:identity|street|address|name)\b','branch_identity','Find an official location page naming this provider and exact physical branch.'),
  (r'image|media','official_image','Find an eligible image on the official program page.'),
  (r'403|robots|fetch|source|unavailable','source_access','Use an accessible official source; preserve robots and access restrictions.'),
  (r'delivery|handoff','handoff','Resume the saved evidence handoff without repeating a search.'),
 ]:
  if re.search(pattern,message):return category,action
 return 'input_review','Review the exact held requirement and correct the brief. No facts may be inferred.'

def unresolved(database,issue):
 with database() as db:
  for table in ['publication_packets','refresh_packets','program_packets','engine_packets','slg_packets']:
   if db.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():
    if db.execute('SELECT 1 FROM '+table+" WHERE issue_id=? AND status IN ('prepared','awaiting_approval','publishing','applying','submitting','uncertain','partial','published','applied')",(issue['id'],)).fetchone():return True
 return False

def reliability(issue,board,config,web,database):
 initialize(database)
 from portfolio import recover_legacy
 legacy=recover_legacy(board,config,database);dispatched=dispatch_pending(board,config,database);tasks=issue_rows(board,config);actions=[]
 for task in [t for t in tasks if t['status']=='blocked'][:30]:
  with database() as db:
   run=db.execute('SELECT error,result FROM runs WHERE issue_id=? ORDER BY started_at DESC LIMIT 1',(task['id'],)).fetchone()
   old=db.execute('SELECT * FROM company_blockers WHERE issue_id=?',(task['id'],)).fetchone()
  message=(run['error'] or json.loads(run['result'] or '{}').get('summary','')) if run else ''
  category,action=classify(message);signature=publishing.sha({'brief':task.get('description'),'category':category})
  if old and old['signature']==signature:continue
  # A changed brief may earn a fresh attempt; a repeated unchanged blocker does not.
  attempts=old['attempts'] if old else 0;next_at=time.time()+[86400,2*86400,7*86400][min(attempts,2)]
  with database() as db:db.execute('INSERT INTO company_blockers VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(issue_id) DO UPDATE SET category=excluded.category,action=excluded.action,signature=excluded.signature,next_at=excluded.next_at',(task['id'],category,action,signature,attempts,next_at,time.time(),None))
  board.call('/issues/'+task['id']+'/comments',{'body':'Recovery check: '+category.replace('_',' ')+'.\n\nRequired evidence/action: '+action+'\n\nRecheck after: '+search_workflow.local_time(next_at)+'. The unchanged brief is not automatically rerun. Saved source changes or a corrected brief are required. At most three changed-evidence recovery attempts per held task; unresolved writes require receipt reconciliation.'})
  actions.append(task.get('identifier'))
 # Publish continuation reconciliation is read-only except closing the superseded original.
 with database() as db:jobs=[dict(r) for r in db.execute("SELECT * FROM search_jobs WHERE status='completed' AND parent_publication<>''")]
 closed=[]
 for job in jobs:
  result=json.loads(job['outcome_json']);cid=result.get('continuation_id')
  if not cid:continue
  child=next((t for t in tasks if t['id']==cid),None);parent=next((t for t in tasks if t['id']==job['parent_publication']),None)
  if not child or child['status']!='done' or not parent or parent['status']!='blocked':continue
  # Do not mistake a manual close for a verified publication result.
  with database() as db:verified=db.execute("SELECT 1 FROM runs WHERE issue_id=? AND status='completed' AND json_extract(result,'$.stage') IN ('published','publication_published','refresh_applied','refresh_no_change')",(cid,)).fetchone()
  if verified:
   board.call('/issues/'+parent['id']+'/comments',{'body':'Completed through verified continuation '+child['identifier']+'. Original evidence and run history retained.'})
   board.call('/issues/'+parent['id'],{'status':'done'},'PATCH');closed.append(parent.get('identifier'))
 rechecks=recheck_blocked(tasks,board,config,web,database)
 report={'saved_drafts_recovered':legacy,'dispatched':dispatched,'source_rechecks':rechecks,'blockers_documented':actions,'original_tasks_reconciled':closed,'unchanged_blind_retries':False}
 return finish(issue,database,'reliability_round',report,'Recovery policies checked. Actionable blockers: '+str(len(actions))+'. No unchanged blind replay was requested.')

def recheck_blocked(tasks,board,config,web,database):
 results=[]
 with database() as db:
  checked={r['issue_id']:r['checked_at'] for r in db.execute('SELECT issue_id,checked_at FROM blocker_sources')}
  due={r['issue_id']:r['next_at'] for r in db.execute('SELECT issue_id,next_at FROM company_blockers')}
 for task in sorted([t for t in tasks if t['status']=='blocked'],key=lambda t:(checked.get(t['id'],0),due.get(t['id'],0))):
  if len(results)>=2:break
  with database() as db:
   policy=db.execute('SELECT * FROM company_blockers WHERE issue_id=?',(task['id'],)).fetchone()
   baseline=db.execute('SELECT * FROM blocker_sources WHERE issue_id=?',(task['id'],)).fetchone()
  if not policy or policy['category']=='write_verification' or unresolved(database,task):continue
  if time.time()<policy['next_at'] or policy['attempts']>=3:continue
  urls=re.findall(r'https://[^\s<>\]\)"`]+',task.get('description') or '')
  if not urls:continue
  try:
   pages=evidence.crawl(urls[0].rstrip('.,;'),web,maximum=3)
   if not pages:raise ValueError('No current official source')
   source_hash=publishing.sha(sorted((p['url'],p['sha256'],json.dumps(p.get('structured',[]),sort_keys=True),json.dumps(p.get('metadata',{}),sort_keys=True)) for p in pages));changed=bool(baseline and source_hash!=baseline['source_hash'])
   if changed:
    # Only source-backed factory work is eligible; untouched policy/receipt holds stay blocked.
    workflow=catalog.field(task,'Factory workflow')
    if catalog.field(task,'Draft reference') and catalog.field(task,'Publication name'):agent=role(config,'publication')
    elif workflow in {'source_research','source_quality'}:agent=role(config,'research' if workflow=='source_research' else 'quality')
    elif workflow=='engine_candidate' and config['projects'].get(task.get('projectId')) in {'Padel Africa','Sportolok'}:agent=role(config,'support')
    else:agent=None
    if agent:
     child=board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':'changed-evidence-'+task['id']+'-'+source_hash,'title':'Recover changed evidence: '+task['title'][:110],'projectId':task['projectId'],'description':(task.get('description') or '')+'\nRecovery of: '+task['id'],'status':'todo','assigneeAgentId':agent,'reviewPolicy':'anyone'})
     with database() as db:db.execute('UPDATE company_blockers SET attempts=attempts+1,last_progress=?,continuation_id=? WHERE issue_id=?',(time.time(),child['id'],task['id']))
   with database() as db:
    db.execute('INSERT INTO blocker_sources VALUES(?,?,?) ON CONFLICT(issue_id) DO UPDATE SET source_hash=excluded.source_hash,checked_at=excluded.checked_at',(task['id'],source_hash,time.time()))
    attempts=policy['attempts']+int(changed)
    db.execute('UPDATE company_blockers SET next_at=? WHERE issue_id=?',(time.time()+[86400,2*86400,7*86400][min(attempts,2)],task['id']))
   results.append({'task':task.get('identifier'),'source_changed':changed,'baseline_recorded':not baseline})
  except Exception as error:
   with database() as db:db.execute('UPDATE company_blockers SET next_at=? WHERE issue_id=?',(time.time()+86400,task['id']))
   results.append({'task':task.get('identifier'),'status':'source_unavailable','category':type(error).__name__})
 return results

def freshness(issue,board,config,web,database,client=None):
 initialize(database);client=client or catalog.Catalog();now=time.time()
 with database() as db:
  rows=[dict(r) for r in db.execute('SELECT c.* FROM catalog_checks c LEFT JOIN freshness_checks f ON c.provider_id=f.provider_id WHERE f.checked_at IS NULL OR f.checked_at<? ORDER BY coalesce(f.checked_at,0),c.checked_at LIMIT 3',(now-86400,))]
 results=[]
 for stored in rows:
  id=stored['provider_id']
  try:
   row=client.get(id)
   if row['owner_managed']:
    result={'provider_id':id,'status':'owner_managed'}
    with database() as db:db.execute('INSERT INTO freshness_checks VALUES(?,?,?,?) ON CONFLICT(provider_id) DO UPDATE SET checked_at=excluded.checked_at,result_json=excluded.result_json',(id,now,'',json.dumps(result)))
    results.append(result);continue
   program_urls=[]
   with database() as db:
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='publication_packets'").fetchone():
     for packet in db.execute("SELECT proof_json FROM publication_packets WHERE status='published'"):
      proof=json.loads(packet[0]);normalized=proof.get('normalized',{})
      if publishing.norm(normalized.get('title'))==publishing.norm(row['name']) and evidence.address_matches(row.get('address'),normalized.get('addressRaw','')):program_urls.extend(v['url'] for v in proof.get('sources',[]) if evidence.host(v['url'])==evidence.host(row['website']))
   pages=evidence.crawl(row['website'],web,extra=list(dict.fromkeys(program_urls))[:3],maximum=4)
   if not pages:raise ValueError('No accessible official pages')
   signature=publishing.sha(sorted((p['url'],p['sha256']) for p in pages))
   with database() as db:prior=db.execute('SELECT * FROM freshness_checks WHERE provider_id=?',(id,)).fetchone()
   changed=bool(prior and prior['source_hash'] and prior['source_hash']!=signature)
   result={'provider_id':id,'status':'changed' if changed else 'baseline_recorded' if not prior else 'unchanged','sources':[{'url':p['url'],'sha256':p['sha256']} for p in pages],'checked_at':now}
   if changed:
    # Existing refresh adapter safely updates contacts and supported descriptions. Program changes remain explicit review findings.
    child=board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':'freshness-'+id+'-'+signature,'title':'Recheck changed official content: '+row['name'][:100],'projectId':project(config,'ClassScout'),'status':'todo','assigneeAgentId':role(config,'research'),'reviewPolicy':'anyone','description':'Factory workflow: source_research\nCatalog provider: '+id+'\nFreshness source hash: '+signature+'\n\n'+pages[0]['url']+'\n\nCheck exact branch and current contacts/content. Program prices and schedules require their canonical program contract; never overwrite them via contact fields.'})
    result['task']=child['identifier']
   with database() as db:db.execute('INSERT INTO freshness_checks VALUES(?,?,?,?) ON CONFLICT(provider_id) DO UPDATE SET checked_at=excluded.checked_at,source_hash=excluded.source_hash,result_json=excluded.result_json',(id,now,signature,json.dumps(result)))
  except Exception as error:
   result={'provider_id':id,'status':'source_unavailable','error_category':type(error).__name__}
   with database() as db:
    previous=db.execute('SELECT source_hash FROM freshness_checks WHERE provider_id=?',(id,)).fetchone()
    db.execute('INSERT INTO freshness_checks VALUES(?,?,?,?) ON CONFLICT(provider_id) DO UPDATE SET checked_at=excluded.checked_at,result_json=excluded.result_json',(id,now,previous[0] if previous else '',json.dumps(result)))
  results.append(result)
 # Scan dated published evidence for expired camps without silently deleting public data.
 expired=[]
 with database() as db:
  if db.execute("SELECT 1 FROM sqlite_master WHERE name='publication_packets'").fetchone():
   for p in db.execute("SELECT issue_id,proof_json FROM publication_packets WHERE status='published'"):
    proof=json.loads(p['proof_json']);ends=[v['endDate'] for v in proof.get('schedules',[]) if v.get('endDate')]
    if ends and max(ends)<datetime.datetime.now(datetime.timezone.utc).date().isoformat():expired.append(p['issue_id'])
 report={'checked':results,'expired_camp_issues':expired,'program_price_schedule_updates':'Held for program-specific canonical revalidation; not written through contact patches.'}
 return finish(issue,database,'freshness_round',report,'Official-source freshness check completed for '+str(len(results))+' providers. Changed evidence uses the existing independent research, quality and update gates.')

def knowledge(issue,board,config,web,database,client=None):
 import support
 initialize(database);client=client or catalog.Catalog();now=time.time()
 with database() as db:rows=[dict(r) for r in db.execute('SELECT c.provider_id FROM catalog_checks c LEFT JOIN (SELECT provider_id,max(verified_at) AS verified_at FROM support_knowledge GROUP BY provider_id) k ON c.provider_id=k.provider_id WHERE k.verified_at IS NULL OR k.verified_at<? ORDER BY coalesce(k.verified_at,0),c.checked_at DESC LIMIT 3',(now-86400,))]
 ready=0;missing=0
 for r in rows:
  id=r['provider_id']
  try:
   row=client.get(id);page,facts,branch=evidence.branch_page(row,row['website'],[],web)
   for topic,question in [('contact','What is the phone and email?'),('address','Where is the address?'),('website','What is the official website?')]:
    response=support.answer(question,row,page,facts);response.update(provider_name=row['name'],source_url=page['url'],source_sha256=page['sha256'],delivered_to_customer=False)
    status='missing_evidence' if response['needs_human'] else 'ready';ready+=status=='ready';missing+=status!='ready'
    with database() as db:db.execute('INSERT INTO support_knowledge VALUES(?,?,?,?,?,?) ON CONFLICT(provider_id,topic) DO UPDATE SET status=excluded.status,answer_json=excluded.answer_json,verified_at=excluded.verified_at,expires_at=excluded.expires_at',(id,topic,status,json.dumps(response),now,now+86400))
  except Exception:
   # Do not let an old answer remain usable after failed revalidation.
   with database() as db:db.execute("UPDATE support_knowledge SET status='source_unavailable',expires_at=? WHERE provider_id=?",(now,id));db.execute('INSERT INTO support_knowledge VALUES(?,?,?,?,?,?) ON CONFLICT(provider_id,topic) DO UPDATE SET verified_at=excluded.verified_at,expires_at=excluded.expires_at', (id,'source','source_unavailable','{}',now,now+86400))
   missing+=1
 with database() as db:unanswered=sum(bool(json.loads(r[0]).get('needs_human')) for r in db.execute("SELECT result_json FROM workflow_reports WHERE kind='support_answer'"))
 report={'unanswered_support_cases':unanswered,'providers_checked':len(rows),'ready_answers':ready,'missing_evidence':missing,'customer_messages_sent':0,'expires_after_hours':24}
 return finish(issue,database,'knowledge_round',report,'Support knowledge refreshed: '+str(ready)+' source-grounded reusable answers; '+str(missing)+' gaps. No customer reply was sent.')

def queue_padel_candidate(issue,page,board,config):
 city=catalog.field(issue,'Padel city')
 if not city:raise ValueError('Padel discovery needs an exact configured city')
 return board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':'padel-candidate-'+publishing.sha({'url':page['url'],'city':city}),'title':'Verify Padel source: '+page['title'][:110],'projectId':project(config,'Padel Africa'),'status':'todo','assigneeAgentId':role(config,'support'),'reviewPolicy':'anyone','description':'Factory workflow: padel_candidate\nPadel city: '+city+'\nOfficial source URL: '+page['url']+'\n\nValidate literal official name and one street address before evidence intake. Search titles/snippets are not facts.'})

# padel_discovery and padel_candidate are the older Padel path. operational.run sends both kinds to engine_ops when
# engine_clients['padel-africa'] is set (it is in production); these versions run only when that flag is off.
def padel_discovery(issue,board,config,web,database,client=None):
 import padel
 initialize(database)
 if not config.get('padel_discovery_enabled'):raise ValueError('Padel discovery is disabled')
 client=client or padel.Client();value=client.catalog();cities=value['vertical'].get('discovery',{}).get('localities',[])
 if not cities:raise ValueError('No canonical Padel discovery localities')
 with database() as db:position=db.execute('SELECT position FROM padel_discovery_cursor WHERE id=1').fetchone()[0];pending=db.execute("SELECT count(*) FROM search_jobs WHERE kind='padel' AND status IN ('queued','running','delivery_pending')").fetchone()[0]
 if pending:return finish(issue,database,'padel_discovery',{'waiting':True},'An existing Padel discovery intent is still pending; no extra task was added.')
 city=cities[position%len(cities)];query='padel club '+city+' official courts contact street address';day=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
 child=board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':'padel-discovery-'+day+'-'+city,'title':'Discover official Padel clubs in '+city,'projectId':project(config,'Padel Africa'),'status':'todo','assigneeAgentId':role(config,'search'),'reviewPolicy':'anyone','description':'Search purpose: padel\nPadel city: '+city+'\nSearch query: '+query+'\n\nUse the shared Brave budget. Verify official sources, exact city and one branch. Source intake is distinct from publication.'})
 with database() as db:db.execute('UPDATE padel_discovery_cursor SET position=? WHERE id=1',((position+1)%len(cities),))
 return finish(issue,database,'padel_discovery',{'task':child['identifier'],'city':city},'Queued '+child['identifier']+' using the same shared search broker and reserve.')

def padel_candidate(issue,board,config,web,database,execution,client=None):
 import padel
 initialize(database);client=client or padel.Client();value=client.catalog();city=catalog.field(issue,'Padel city');url=catalog.field(issue,'Official source URL')
 if city not in value['vertical'].get('discovery',{}).get('localities',[]):raise ValueError('Padel city is outside canonical scope')
 pages=evidence.crawl(url,web,maximum=3);names={(n,p['url']) for p in pages for n in evidence.names(p)};unique={n for n,u in names};addresses={m.group(0) for p in pages for m in evidence.STREET.finditer(p['text']) if publishing.norm(city) in publishing.norm(p['text'])}
 if len(unique)!=1 or len(addresses)!=1:raise ValueError('Padel source needs a unique official provider name, literal configured city and one street address; multi-branch or uncertain sources are held')
 name=next(iter(unique));address=next(iter(addresses))
 if any(re.search(r'[\r\n<>]',v) for v in [name,city,address]):raise ValueError('Padel literal fields must be single-line public identity values')
 page=next((p for p in pages if all(publishing.norm(x) in publishing.norm(p['text']) for x in [name,city,address]) and re.search(r'\bpadel\b',p['text'],re.I)),None)
 if not page:raise ValueError('Padel identity fields must occur together on one official page')
 # Reuse the source-intake form as an independent job, preserving its full receipt/tenant gate.
 child=board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':'padel-verified-'+publishing.sha({'url':page['url'],'name':name,'city':city,'address':address}),'title':'Submit verified Padel source: '+name[:100],'projectId':project(config,'Padel Africa'),'status':'todo','assigneeAgentId':role(config,'support'),'reviewPolicy':'anyone','description':'Factory workflow: padel_intake\nProvider name: '+name+'\nCity: '+city+'\nStreet address: '+address+'\nOfficial source URL: '+page['url']})
 return finish(issue,database,'padel_candidate',{'intake_task':child['identifier']},'Literal source evidence queued for independently rechecked intake: '+child['identifier']+'. No public publication is claimed.')

def finish(issue,database,kind,report,text):
 catalog.save_report(database,issue,kind,report)
 return {'stage':kind+'_completed','entities':[],'final_status':'done','automatic_progress':True,'markdown':'## Company operations\n\n'+text,'report':report}

def run(issue,board,config,web,database,execution):
 kind=catalog.field(issue,'Factory workflow');brand=config['projects'].get(issue.get('projectId'))
 if not config.get('reliability_enabled'):raise ValueError('Company improvements are disabled')
 if kind.startswith('padel_'):
  if brand!='Padel Africa' or not config.get('padel_enabled'):raise ValueError('Padel workflow assigned outside its brand')
  return padel_candidate(issue,board,config,web,database,execution) if kind=='padel_candidate' else padel_discovery(issue,board,config,web,database)
 if kind in {'freshness_round','knowledge_round'} and brand!='ClassScout':raise ValueError('ClassScout source workflows require the ClassScout project')
 return {'reliability_round':reliability,'freshness_round':freshness,'knowledge_round':knowledge}[kind](issue,board,config,web,database)


def queue_dispatch(database,key,source,body):
 initialize(database)
 signature=publishing.sha({'description':source.get('description'),'title':source['title'],'project':source['projectId']})
 body={k:v for k,v in body.items() if k!='parentId'}
 with database() as db:db.execute('INSERT OR IGNORE INTO company_dispatch VALUES(?,?,?,?,?,?,?,?)',(key,source['id'],signature,json.dumps(body),'queued',None,0,0))
 return key

def dispatch_pending(board,config,database,limit=3):
 results=[]
 with database() as db:requests=[dict(r) for r in db.execute("SELECT * FROM company_dispatch WHERE status='queued' AND next_at<=? ORDER BY next_at,rowid LIMIT ?",(time.time(),min(10,max(1,int(limit)))))]
 for request in requests:
  try:
   source=board.call('/issues/'+request['source_issue']);body=json.loads(request['payload_json']);current=publishing.sha({'description':source.get('description'),'title':source['title'],'project':source['projectId']})
   if current!=request['input_hash'] or source.get('companyId')!=config['company_id'] or config['projects'].get(source.get('projectId')) not in {'ClassScout','Padel Africa','Sportolok'} or source.get('status')=='cancelled' or unresolved(database,source):
    with database() as db:db.execute("UPDATE company_dispatch SET status='cancelled' WHERE request_key=?",(request['request_key'],))
    continue
   if body.get('assigneeAgentId') not in {k for k,v in config['agents'].items() if v['role'] in {'publication','search','quality','support'}} or body.get('projectId')!=source['projectId'] or body.get('status')!='todo' or 'parentId' in body:raise ValueError('Invalid company dispatch request')
   if config['agents'].get(body.get('assigneeAgentId'),{}).get('role')=='support' and (catalog.field(body,'Factory workflow')!='engine_candidate' or config['projects'].get(source['projectId']) not in {'Padel Africa','Sportolok'}):raise ValueError('Unsupported engine coordination request')
   body.setdefault('idempotencyKey',request['request_key'])
   child=board.call('/companies/'+config['company_id']+'/issues',body)
   with database() as db:
    db.execute("UPDATE company_dispatch SET status='delivered',target_issue=? WHERE request_key=?",(child['id'],request['request_key']))
    # Update the source search receipt with the actual continuation reference.
    for job in db.execute("SELECT issue_id,outcome_json FROM search_jobs WHERE parent_publication=?",(source['id'],)).fetchall():
     outcome=json.loads(job['outcome_json'])
     if outcome.get('continuation_request')==request['request_key']:
      outcome.update(continuation_id=child['id'],publication_resumed=child['identifier']);db.execute('UPDATE search_jobs SET outcome_json=? WHERE issue_id=?',(json.dumps(outcome),job['issue_id']))
   results.append(child['identifier'])
  except Exception:
   attempts=request['attempts']+1
   with database() as db:db.execute('UPDATE company_dispatch SET attempts=?,next_at=?,status=? WHERE request_key=?',(attempts,time.time()+[60,300,900][min(attempts-1,2)],'needs_attention' if attempts>=3 else 'queued',request['request_key']))
 return results
