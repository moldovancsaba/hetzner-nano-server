"""Quota-controlled source discovery, native Paperclip scheduling and verified-page handoff."""
import datetime,hashlib,json,os,re,time,urllib.parse
from zoneinfo import ZoneInfo
from net import canonical_url
from search_budget import Budget,BudgetWait
from brave import Brave,SearchError

# Only the keys are used (the purpose check in parse). The real priority order is the SQL CASE in queued_issue and in run:
# publishing first, then discovery (and padel/sportolok once an hour old), then everything else. The numbers are unused.
RANK={'publishing':0,'discovery':1,'support':2,'padel':3,'sportolok':3}
TERMINAL={'done','cancelled'}
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def fingerprint(query):return hashlib.sha256((' '.join(query.casefold().split())+'|US|en|strict|web|20').encode()).hexdigest()
def local_time(epoch):return datetime.datetime.fromtimestamp(epoch,ZoneInfo('Europe/Budapest')).strftime('%Y-%m-%d %H:%M %Z')
def initialize(database):
 with database() as db:
  db.execute('''CREATE TABLE IF NOT EXISTS search_jobs(issue_id TEXT PRIMARY KEY,project_id TEXT,kind TEXT,queries_json TEXT,status TEXT,source_host TEXT,parent_publication TEXT,parent_input_hash TEXT,attempts INTEGER,run_id TEXT,outcome_json TEXT,error TEXT,notice_hash TEXT,created_at REAL,updated_at REAL)''')
  db.execute('CREATE TABLE IF NOT EXISTS source_attempts(project_id TEXT,url TEXT,source_hash TEXT,target_issue TEXT,created_at REAL,PRIMARY KEY(project_id,url,source_hash))')
  cols={r[1] for r in db.execute('PRAGMA table_info(search_jobs)')}
  for name,typ in [('delivery_attempts','INTEGER NOT NULL DEFAULT 0'),('next_delivery_at','REAL NOT NULL DEFAULT 0')]:
   if name not in cols:db.execute('ALTER TABLE search_jobs ADD COLUMN '+name+' '+typ)

def parse(issue):
 text=issue.get('description') or '';queries=re.findall(r'^Search query:\s*(.+?)\s*$',text,re.M)
 if not 1<=len(queries)<=3:raise ValueError('Add one to three public Search query: lines; a burst uses future search slots')
 for q in queries:
  if not 5<=len(q)<=240 or re.search(r'[\r\n]|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?\d[\s()-]*){8,}|BSAp-|api[_ -]?key|password|bearer\s|access[_ -]?token',q,re.I):raise ValueError('Search queries must contain only public provider/location/activity terms, without contact identifiers or credentials')
 def field(name,default=''):
  m=re.search(r'^'+re.escape(name)+r':\s*(.+?)\s*$',text,re.M);return m[1].strip() if m else default
 kind=field('Search purpose','discovery').lower()
 if kind not in RANK:raise ValueError('Search purpose must be publishing, discovery, support, padel or sportolok')
 host=field('Source host').lower().removeprefix('www.')
 if host:
  safe=canonical_url('https://'+host+'/')
  if urllib.parse.urlsplit(safe).hostname!=host:raise ValueError('Invalid source host')
 parent=field('Publication task');parent_hash=field('Publication input hash')
 if parent and not re.fullmatch(r'[a-f0-9-]{36}',parent):raise ValueError('Invalid publication task reference')
 if parent_hash and not re.fullmatch(r'[a-f0-9]{64}',parent_hash):raise ValueError('Invalid publication input reference')
 return {'queries':list(dict.fromkeys(queries)),'kind':kind,'host':host,'parent':parent,'parent_hash':parent_hash}

def enqueue(issue,database):
 initialize(database);spec=parse(issue);now=time.time();duplicates=[]
 with database() as db:
  db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT * FROM search_jobs WHERE issue_id=?',(issue['id'],)).fetchone()
  if old:
   if json.loads(old['outcome_json']).get('requested_queries',json.loads(old['queries_json']))!=spec['queries'] or old['kind']!=spec['kind'] or old['source_host']!=spec['host'] or old['parent_publication']!=spec['parent'] or old['parent_input_hash']!=spec['parent_hash']:raise ValueError('This search task already has a durable intent. Create a new task for a changed query.')
   return dict(old)
  recent=db.execute("SELECT issue_id,queries_json FROM search_jobs WHERE created_at>? AND status<>'cancelled'",(now-7*86400,)).fetchall();seen={fingerprint(q):r['issue_id'] for r in recent for q in json.loads(r['queries_json'])};queries=[]
  for q in spec['queries']:
   if fingerprint(q) in seen:duplicates.append(seen[fingerprint(q)])
   else:queries.append(q)
  status='queued' if queries else 'deduplicated';outcome={'requested_queries':spec['queries'],'duplicate_tasks':list(dict.fromkeys(duplicates)),'source_pages':[],'research_tasks':[]}
  db.execute('INSERT INTO search_jobs(issue_id,project_id,kind,queries_json,status,source_host,parent_publication,parent_input_hash,attempts,run_id,outcome_json,error,notice_hash,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(issue['id'],issue['projectId'],spec['kind'],json.dumps(queries),'queued' if queries else 'deduplicated',spec['host'],spec['parent'],spec['parent_hash'],0,None,json.dumps(outcome),None,None,now,now))
  return dict(db.execute('SELECT * FROM search_jobs WHERE issue_id=?',(issue['id'],)).fetchone())

def queued_issue(board,config,agent,database):
 initialize(database)
 with database() as db:rows=[dict(r) for r in db.execute("SELECT * FROM search_jobs WHERE status IN ('queued','running','delivery_pending') ORDER BY CASE WHEN kind='publishing' THEN 0 WHEN kind='discovery' OR (kind IN ('padel','sportolok') AND created_at<=?) THEN 1 ELSE 2 END,created_at",(time.time()-3600,))]
 if not rows:return None
 paused=research_backlog(board,config,database)>=10
 for row in rows:
  if row['status']=='delivery_pending' and time.time()<row['next_delivery_at']:continue
  if row['kind']=='discovery' and paused:continue
  issue=board.call('/issues/'+row['issue_id'])
  if issue.get('assigneeAgentId')!=agent or issue['status'] in TERMINAL:
   with database() as db:db.execute("UPDATE search_jobs SET status='cancelled',updated_at=? WHERE issue_id=?",(time.time(),row['issue_id']))
   continue
  if row['status']=='running':
   try:prior=board.call('/heartbeat-runs/'+row['run_id'])
   except Exception:prior={'status':'unknown'}
   if prior['status']=='running':continue
   outcome=json.loads(row['outcome_json']);state='delivery_pending' if outcome.get('source_pages') else 'queued' if row['attempts']<2 else 'needs_attention'
   with database() as db:db.execute('UPDATE search_jobs SET status=?,error=?,updated_at=? WHERE issue_id=?',(state,'Previous search execution stopped; reservations retained conservatively',time.time(),row['issue_id']))
   if state=='needs_attention':continue
  return issue
 return None

def research_backlog(board,config,database):
 # One unpaged call: the Paperclip API answers a single default page (500 rows), so this count is a lower bound if more
 # ClassScout tasks than that are active. issue_pages.fetch pages through the whole list but is not used here.
 project=next(k for k,v in config['projects'].items() if v=='ClassScout');rows=board.call('/companies/'+config['company_id']+'/issues?'+urllib.parse.urlencode({'projectId':project,'status':'backlog,todo,in_progress,in_review'}));rows=rows if isinstance(rows,list) else rows.get('issues',[]);active={r['id']:r for r in rows if r['status'] not in {'done','cancelled'} and '[Factory test]' not in r.get('title','')};research=next(k for k,v in config['agents'].items() if v['role']=='research')
 with database() as db:
  ids={r[0] for r in db.execute('SELECT issue_id FROM entities')}|{r[0] for r in db.execute("SELECT issue_id FROM runs WHERE role='research'")}
 ids|={i['id'] for i in rows if i.get('assigneeAgentId')==research}
 return len(ids & set(active))

def active(issue,board,config,execution):
 current=board.call('/issues/'+issue['id']);run=board.call('/heartbeat-runs/'+execution['run_id'])
 if current['companyId']!=config['company_id'] or current['status']!='in_progress' or current.get('assigneeAgentId')!=execution['agent_id'] or run['status']!='running':raise ValueError('Search task stopped or changed ownership')
 if current.get('description')!=issue.get('description'):raise ValueError('Search brief changed while executing')

def notice(database,job,text):
 digest=hashlib.sha256(text.encode()).hexdigest()
 with database() as db:
  old=db.execute('SELECT notice_hash FROM search_jobs WHERE issue_id=?',(job['issue_id'],)).fetchone()
  if old and old[0]==digest:return None
  db.execute('UPDATE search_jobs SET notice_hash=? WHERE issue_id=?',(digest,job['issue_id']))
 return text

def persist_outcome(database,job,outcome):
 with database() as db:db.execute('UPDATE search_jobs SET outcome_json=?,updated_at=? WHERE issue_id=?',(json.dumps(outcome),time.time(),job['issue_id']))

def verified_pages(rows,job,web,database,maximum):
 pages=[];attempted=0;seen=set();blocked={'classscout.ai','getyourfield.com','facebook.com','instagram.com','yelp.com','reddit.com','youtube.com','mommypoppins.com','mommynearest.com','classpass.com'}
 with database() as db:known={canonical_url(r[0]).replace('://www.','://').rstrip('/') for r in db.execute('SELECT source_url FROM entities')}
 rows=sorted(rows,key=lambda r:0 if re.search(r'program|class|register|tuition|pricing|schedule|camp',urllib.parse.urlsplit(r.get('url','')).path,re.I) else 1)
 for row in rows:
  if len(pages)>=maximum or attempted>=8:break
  try:
   url=canonical_url(row.get('url',''));host=urllib.parse.urlsplit(url).hostname.removeprefix('www.');path=urllib.parse.urlsplit(url).path
   if row.get('family_friendly') is False or host in blocked or any(host.endswith('.'+h) for h in blocked):continue
   if job['kind'] in {'padel','sportolok'}:
    import venue_identity
    if not venue_identity.provider_host(host):continue
   if job['source_host'] and host!=job['source_host']:continue
   if re.search(r'\.(pdf|docx?|zip|jpe?g|png)(?:$|\?)|/search(?:/|$)|/directory(?:/|$)|porn|casino|betting',path,re.I):continue
   key=url.replace('://www.','://').rstrip('/')
   if key in seen or (job['kind']=='discovery' and key in known):continue
   seen.add(key);attempted+=1;page=web.page(url);final_host=urllib.parse.urlsplit(page['url']).hostname.removeprefix('www.')
   if job['kind'] in {'padel','sportolok'}:
    if not venue_identity.provider_host(final_host):continue
   if job['kind']=='discovery':
    initialize(database)
    with database() as db:prior=db.execute('SELECT 1 FROM source_attempts WHERE project_id=? AND url=? AND source_hash=? AND created_at>?',(job.get('project_id',''),canonical_url(page['url']).replace('://www.','://').rstrip('/'),page['sha256'],time.time()-7*86400)).fetchone()
    if prior:continue
   if job['source_host'] and final_host!=job['source_host']:continue
   if job['kind']=='sportolok':pass
   elif job['kind']=='padel':
    if not re.search(r'\bpadel\b',page['text'],re.I):continue
   elif not re.search(r'kids?|children|famil(?:y|ies)|ages?|tuition|classes',page['text'],re.I):continue
   pages.append({'url':page['url'],'title':page['title'][:160],'sha256':page['sha256'],'fetched_at':page['fetched_at']})
  except Exception:continue
 return pages

def discovery_metadata(issue):
 import catalog
 return '\n'.join(k+': '+catalog.field(issue,k) for k in ['Discovery borough','Discovery activity','Discovery campaign','Discovery format'] if catalog.field(issue,k))

def deliver(issue,board,config,job,outcome,database,execution):
 research=next(k for k,v in config['agents'].items() if v['role']=='research')
 for page in ([] if job.get('kind')=='publishing' and job.get('parent_publication') else outcome.get('source_pages',[])):
  if page.get('research_id'):continue
  active(issue,board,config,execution)
  if job['kind'] in {'padel','sportolok'}:
   if config.get('engine_clients'):
    from portfolio import queue_engine_candidate
    child=queue_engine_candidate(issue,page,board,config)
    page['research_id']=child['id'];page['research_identifier']=child['identifier'];outcome['research_tasks'].append(child['identifier']);persist_outcome(database,job,outcome);continue
   from company_ops import queue_padel_candidate
   child=queue_padel_candidate(issue,page,board,config)
   page['research_id']=child['id'];page['research_identifier']=child['identifier'];outcome['research_tasks'].append(child['identifier']);persist_outcome(database,job,outcome);continue
  key=hashlib.sha256((issue['projectId']+'|'+canonical_url(page['url']).replace('://www.','://').rstrip('/')+'|'+page['sha256']+'|'+str(issue['title'].startswith('[Factory test]'))).encode()).hexdigest()
  child=board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':'brave-source-'+key,'title':('[Factory test] ' if issue['title'].startswith('[Factory test]') else '')+'Research candidate: '+page['title'][:140],'projectId':issue['projectId'],'parentId':issue['id'],'status':'todo','assigneeAgentId':research,'reviewPolicy':'human_only','description':'Factory workflow: source_research\n'+discovery_metadata(issue)+'\nSearch origin: '+issue['id']+'\n\nResearch this directly fetched source page: '+page['url']+'\n\nConfirm provider identity and physical location; a search hit is not proof of officialness. Capture only source-supported facts and exact quotes. Keep missing facts unknown. Prepare a draft for review, not publication. This source URL/title were independently obtained by fetching the webpage; no Brave snippets are retained.'})
  with database() as db:db.execute('INSERT OR IGNORE INTO source_attempts VALUES(?,?,?,?,?)',(issue['projectId'],canonical_url(page['url']).replace('://www.','://').rstrip('/'),page['sha256'],child['id'],time.time()))
  page['research_id']=child['id'];page['research_identifier']=child['identifier'];outcome['research_tasks'].append(child['identifier']);persist_outcome(database,job,outcome)
 # Additional sources can restart only a still-blocked, unchanged, unapproved parent.
 if job['parent_publication'] and outcome.get('source_pages') and not outcome.get('publication_resumed'):
  import publishing
  parent=board.call('/issues/'+job['parent_publication'])
  with database() as db:
   exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='publication_packets'").fetchone();hold=db.execute("SELECT 1 FROM publication_packets WHERE issue_id=? AND status IN ('prepared','awaiting_approval','publishing','uncertain','partial','published')",(parent['id'],)).fetchone() if exists else None
  current_hash=publishing.sha({'description':parent.get('description'),'title':parent['title'],'project':parent['projectId']})
  if parent['status']=='blocked' and parent['companyId']==config['company_id'] and parent['projectId']==issue['projectId'] and current_hash==job['parent_input_hash'] and not hold:
   brief=publishing.parse_brief(parent);extra=[p['url'] for p in outcome['source_pages'] if p['url'] not in brief['urls']][:4-len(brief['urls'])]
   if extra:
    publisher=next(k for k,v in config['agents'].items() if v['role']=='publication');description=parent['description']+'\n\nAdditional verified source pages from search:\n'+'\n'.join(extra)
    if config.get('reliability_enabled'):
     # An independent continuation avoids a Search -> Publication ancestor delegation cycle.
     from company_ops import queue_dispatch
     key='source-continuation-'+job['issue_id']+'-'+current_hash
     queue_dispatch(database,key,parent,{'idempotencyKey':key,'title':prefix_title(parent)+'Recheck complete sources: '+brief['Publication name'],'description':description+'\nRecovery of: '+parent['id'],'projectId':parent['projectId'],'status':'todo','assigneeAgentId':publisher,'reviewPolicy':'anyone'})
     outcome['continuation_request']=key
    else:
     board.call('/issues/'+parent['id'],{'description':description,'status':'todo','assigneeAgentId':publisher,'assigneeUserId':None},'PATCH');outcome['publication_resumed']=parent.get('identifier')
    persist_outcome(database,job,outcome)
 return outcome

def prefix_title(issue):return '[Factory test] ' if issue['title'].startswith('[Factory test]') else ''

def budget_markdown(budget):
 s=budget.status();return 'Search budget: '+str(s['used_this_window'])+'/'+str(s['automatic_limit'])+' this allowance period; '+str(s['used_today'])+'/'+str(s['daily_limit'])+' today. Next shared search slot: '+local_time(s['next_search_at'])+'.'

def run(issue,board,config,web,database,execution,client=None,budget=None):
 if not config.get('search_enabled'):raise ValueError('Brave Search is disabled')
 if not os.environ.get('BRAVE_SEARCH_API_KEY') and client is None:raise ValueError('Brave connection is not configured')
 budget=budget or Budget(database);job=enqueue(issue,database);outcome=json.loads(job['outcome_json']);locale=('HU','hu') if job['kind']=='sportolok' else ('ZA','en') if job['kind']=='padel' else ('US','en');client=client or Brave(budget,country=locale[0],language=locale[1])
 brand=config.get('projects',{}).get(issue.get('projectId'))
 if (job['kind']=='padel' and (brand!='Padel Africa' or not config.get('padel_discovery_enabled'))) or (job['kind']=='sportolok' and (brand!='Sportolok' or not config.get('engine_clients',{}).get('sportolok'))) or (job['kind'] not in {'padel','sportolok'} and brand!='ClassScout'):raise ValueError('Search purpose does not match the configured brand')
 if job['status']=='deduplicated':return {'stage':'search_completed','markdown':'This query was already queued or processed within seven days. No additional Brave request was made. Related search task IDs: '+', '.join(outcome['duplicate_tasks'])+'\n\n'+budget_markdown(budget),'entities':[]}
 if job['status']=='completed':return {'stage':'search_completed','markdown':None,'entities':[]}
 if job['status']=='delivery_pending' and time.time()<job['next_delivery_at']:
  return {'stage':'search_waiting','markdown':None,'entities':[],'wake_at':job['next_delivery_at']}
 if job['status']=='needs_attention':raise ValueError('Search exhausted its two conservative attempts; inspect the connection or change the query before creating a fresh intent')
 backlog=research_backlog(board,config,database)
 with database() as db:head=db.execute("SELECT issue_id FROM search_jobs WHERE status IN ('queued','running','delivery_pending') AND (status<>'delivery_pending' OR next_delivery_at<=?) AND (?<10 OR kind<>'discovery') ORDER BY CASE WHEN kind='publishing' THEN 0 WHEN kind='discovery' OR (kind IN ('padel','sportolok') AND created_at<=?) THEN 1 ELSE 2 END,created_at LIMIT 1",(time.time(),backlog,time.time()-3600)).fetchone()
 if head and head[0]!=issue['id']:
  text='Waiting behind a higher-priority or older search task.\n\n'+budget_markdown(budget);return {'stage':'search_waiting','markdown':notice(database,job,text),'entities':[]}
 capacity=max(0,10-backlog) if job['kind']=='discovery' else 5
 if job['kind']=='discovery' and capacity==0:
  text='New discovery is paused: ten research drafts/tasks already await work or review. Publishing blockers can still be searched.\n\n'+budget_markdown(budget);return {'stage':'search_waiting','markdown':notice(database,job,text),'entities':[]}
 if not outcome.get('source_pages'):
  queries=json.loads(job['queries_json'])
  try:tokens=budget.reserve(issue['id'],len(queries))
  except BudgetWait as error:
   text=error.reason+'. Next eligible check: '+local_time(error.until)+'. No Brave request was sent.\n\n'+budget_markdown(budget);return {'stage':'search_waiting','markdown':notice(database,job,text),'entities':[],'wake_at':error.until+2}
  with database() as db:db.execute("UPDATE search_jobs SET status='running',run_id=?,attempts=attempts+1,updated_at=? WHERE issue_id=?",(execution['run_id'],time.time(),issue['id']))
  rows=[];errors=[];retryable=False
  for q,token in zip(queries,tokens):
   active(issue,board,config,execution)
   try:rows.extend(client.search(q,token))
   except (SearchError,BudgetWait) as error:errors.append(str(error));retryable=getattr(error,'retryable',False);break
  outcome['result_count']=len(rows);outcome['source_pages']=verified_pages(rows,job,web,database,min(5,max(1,int(config.get('search_candidate_limit',3))),capacity));outcome['errors']=errors;persist_outcome(database,job,outcome)
  if errors and not outcome['source_pages']:
   state='queued' if retryable and job['attempts']+1<2 else 'needs_attention'
   with database() as db:db.execute('UPDATE search_jobs SET status=?,error=?,updated_at=? WHERE issue_id=?',(state,'; '.join(errors),time.time(),issue['id']))
   text='Search did not complete: '+'; '.join(errors)+'. Attempts were counted conservatively.\n\n'+budget_markdown(budget)
   return {'stage':'search_waiting' if state=='queued' else 'search_failed','markdown':notice(database,job,text),'entities':[]}
 try:outcome=deliver(issue,board,config,job,outcome,database,execution)
 except Exception as error:
  attempts=job['delivery_attempts']+1;due=time.time()+min(3600,300*2**(attempts-1));state='needs_attention' if attempts>=3 else 'delivery_pending'
  # Store a category only: no provider diagnostic, tokens, or source body.
  with database() as db:db.execute('UPDATE search_jobs SET status=?,delivery_attempts=?,next_delivery_at=?,error=?,updated_at=? WHERE issue_id=?',(state,attempts,due,'Source delivery '+type(error).__name__+'; receipts retained; no repeated Brave request',time.time(),issue['id']))
  return {'stage':'search_failed' if state=='needs_attention' else 'search_waiting','markdown':notice(database,job,'Verified-source delivery attempt '+str(attempts)+'/3 did not complete. Saved pages are retained; no new Brave request. '+('Automatic retries stopped; the recovery coordinator will expose this blocker.' if state=='needs_attention' else 'Other searches can proceed while delivery waits.')),'entities':[],'wake_at':due,'final_status':'blocked' if state=='needs_attention' else 'in_review'}
 with database() as db:db.execute("UPDATE search_jobs SET status='completed',error=NULL,updated_at=? WHERE issue_id=?",(time.time(),issue['id']))
 lines=['## Search completed','','Independently checked source pages: '+str(len(outcome['source_pages']))+'. Research tasks: '+(', '.join(outcome['research_tasks']) or 'none; no eligible source page passed checks')+'.','']
 for p in outcome['source_pages']:lines.append('- '+p['title']+': '+p['url'])
 if outcome.get('publication_resumed'):lines+=['','Publication preparation resumed in '+outcome['publication_resumed']+'. It must still pass the configured fresh-source publication gate.']
 lines+=['',budget_markdown(budget),'','Search snippets are not listing evidence. Source research, quality review and the configured automatic catalog gate remain required.']
 return {'stage':'search_completed','markdown':'\n'.join(lines),'entities':[],'final_status':'done','automatic_progress':config.get('growth_mode',{}).get('enabled',False)}

def request_gap_search(issue,board,config,message,database=None):
 # Matches the wording of the ValueErrors raised by formats.py and publishing.py. 'Missing official source image' is no
 # longer raised (a missing image does not block publication); that alternative is harmless and unused.
 if not config.get('search_enabled') or not re.search(r'Missing explicit|Missing or ambiguous|Missing official source image',message,re.I):return None
 import publishing
 try:brief=publishing.parse_brief(issue)
 except ValueError:return None
 if len(brief['urls'])>=4:return None
 host=urllib.parse.urlsplit(brief['urls'][0]).hostname.removeprefix('www.');query='site:'+host+' "'+brief['Publication name'].replace('"','')+'" kids classes schedule tuition ages';query=query[:240]
 input_hash=publishing.sha({'description':issue.get('description'),'title':issue['title'],'project':issue['projectId']});agent=next((k for k,v in config['agents'].items() if v['role']=='search'),None)
 if not agent:return None
 body={'idempotencyKey':'brave-gap-'+issue['id']+'-'+input_hash,'title':'Find missing source pages for '+brief['Publication name'],'projectId':issue['projectId'],'parentId':issue['id'],'status':'todo','assigneeAgentId':agent,'reviewPolicy':'human_only','description':'Search purpose: publishing\nSearch query: '+query+'\nSource host: '+host+'\nPublication task: '+issue['id']+'\nPublication input hash: '+input_hash+'\n\nFind official source pages for the missing program requirements. Do not infer facts from snippets or publish a listing.'}
 if config.get('reliability_enabled') and database is not None:
  from company_ops import queue_dispatch
  queue_dispatch(database,body['idempotencyKey'],issue,body)
  return {'identifier':'the company recovery queue','queued':True}
 return board.call('/companies/'+config['company_id']+'/issues',body)

def quality_for_search_source(issue,result,board,config,run_id):
 if not config.get('search_enabled') or not re.search(r'^Search origin: [a-f0-9-]{36}$',issue.get('description') or '',re.M):return
 agent=next(k for k,v in config['agents'].items() if v['role']=='quality')
 for entity in result.get('entities',[]):board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':'source-quality-'+run_id+'-'+entity,'title':'Verify evidence: '+issue['title'][:140],'projectId':issue['projectId'],'parentId':issue['id'],'status':'todo','assigneeAgentId':agent,'reviewPolicy':'human_only','description':'Draft reference: '+entity+'. Re-fetch the source and verify every stored quote and required identity fields. A search result is not publication evidence. Return to human review.'})
