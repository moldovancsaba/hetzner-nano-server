"""Bounded production commissioning and recurring discovery, sharing existing quotas."""
import json,re,time,urllib.parse,urllib.request
import catalog,publishing,search_workflow
from search_budget import Budget
BOROUGHS=['Brooklyn','Manhattan','Queens','Bronx','Staten Island']
ACTIVITIES=['Music','Art','STEM','Dance','Swimming','Gymnastics','Soccer','Basketball','Tennis','Martial Arts','Theater','Coding']
ANGLES=['official program registration ages schedule tuition price','weekly classes per class pricing','after school classes timetable','weekend classes ages tuition','drop in class duration price','official children program ages timetable fees registration']
LOCATION_CACHE=None

def intents():
 # Interleave activities and boroughs before trying a different search angle.
 return [{'format':'Classes','borough':b,'activity':a,'query':'kids '+a+' classes '+b+' NYC '+angle} for angle in ANGLES for a in ACTIVITIES for b in BOROUGHS]+[{'format':'Camps','borough':b,'activity':a,'query':'kids '+a+' camp '+b+' NYC dates schedule weekly tuition official'} for a in ACTIVITIES for b in BOROUGHS]

def initialize(database):
 with database() as db:db.executescript('''CREATE TABLE IF NOT EXISTS growth_cursor(id INTEGER PRIMARY KEY CHECK(id=1),position INTEGER); INSERT OR IGNORE INTO growth_cursor VALUES(1,0); CREATE TABLE IF NOT EXISTS commissioning_checks(entity_id TEXT PRIMARY KEY,checked_at REAL,result_json TEXT);''')

def run(issue,board,config,web,database,execution,budget=None):
 if not config.get('growth_mode',{}).get('enabled'):raise ValueError('Production growth mode is disabled')
 initialize(database);search_workflow.initialize(database);budget=budget or Budget(database);status=budget.status();backlog=search_workflow.research_backlog(board,config,database);reason=None
 with database() as db:pending=db.execute("SELECT count(*) FROM search_jobs WHERE status IN ('queued','running','delivery_pending')").fetchone()[0]
 if backlog>=10:reason='Production research queue is full; discovery waits for work to drain.'
 elif pending>=2:reason='Existing search intents have priority; no extra search task was created.'
 elif time.time()<status['next_search_at']:reason='Shared Brave cooldown is still active.'
 elif status['used_today']>=status['daily_limit'] or status['used_this_window']>=status['automatic_limit'] or status['estimated_account_remaining']<=status['reserve']:reason='Shared Brave allowance is reserved or exhausted.'
 target=None
 if not reason:
  choices=intents()
  with database() as db:
   position=db.execute('SELECT position FROM growth_cursor WHERE id=1').fetchone()[0]
   recent=[dict(r) for r in db.execute("SELECT issue_id,queries_json FROM search_jobs WHERE created_at>? AND status<>'cancelled'",(time.time()-7*86400,))]
   seen={search_workflow.fingerprint(q) for r in recent for q in json.loads(r['queries_json'])}
  selected=next(((position+n,choices[(position+n)%len(choices)]) for n in range(len(choices)) if search_workflow.fingerprint(choices[(position+n)%len(choices)]['query']) not in seen),None)
  if selected:
   index,item=selected;agent=next(k for k,v in config['agents'].items() if v['role']=='search');week=int(time.time()//(7*86400))
   description='Search purpose: discovery\nSearch query: '+item['query']+'\nDiscovery borough: '+item['borough']+'\nDiscovery activity: '+item['activity']+'\nDiscovery format: '+item['format']+'\nDiscovery campaign: classscout-nyc-v1\n\nFind official children class/program pages. Query terms are research hints, not listing facts. Fetch sources directly and preserve evidence. Shared cooldown and monthly reserve remain mandatory.'
   target=board.call('/companies/'+config['company_id']+'/issues',{'idempotencyKey':'growth-'+str(week)+'-'+search_workflow.fingerprint(item['query']),'projectId':issue['projectId'],'parentId':issue['id'],'title':'Discover '+item['activity']+' '+item['format'].lower()+' in '+item['borough'],'description':description,'status':'todo','assigneeAgentId':agent,'reviewPolicy':'anyone'})
   with database() as db:db.execute('UPDATE growth_cursor SET position=? WHERE id=1',((index+1)%len(choices),))
  else:reason='All campaign intents were covered in the seven-day deduplication window.'
 report={'production_research_backlog':backlog,'pending_search_jobs':pending,'created_task':target.get('identifier') if target else None,'reason':reason,'budget':status};catalog.save_report(database,issue,'growth_dispatch',report)
 return {'stage':'growth_dispatched','entities':[],'markdown':'## Production discovery\n\n'+('Queued '+target['identifier']+'.' if target else reason)+'\n\nBrave remains limited to one request per shared 30-minute slot, 48/day and 1,800 per provider allowance period. Only independently fetched source evidence may advance.','final_status':'done','automatic_progress':True,'report':report}

def locations():
 global LOCATION_CACHE
 if LOCATION_CACHE and time.time()-LOCATION_CACHE[0]<3600:return LOCATION_CACHE[1]
 with urllib.request.build_opener(catalog.NoRedirect).open(publishing.ClassScout.BASE+'/api/public/locations?city=nyc',timeout=25) as r:
  raw=r.read(262145)
  if len(raw)>262144:raise ValueError('Location vocabulary exceeded its response bound')
  value=json.loads(raw)
 if not isinstance(value,dict) or not value or any(b not in BOROUGHS or not isinstance(v,list) or any(not isinstance(n,str) or not 1<len(n)<120 for n in v) for b,v in value.items()):raise ValueError('Canonical location vocabulary is unavailable')
 LOCATION_CACHE=(time.time(),value);return value

def present(value,text):return bool(re.search(r'(?<!\w)'+re.escape(value)+r'(?!\w)',text,re.I))
def infer(issue,row,database,web):
 """Query hints become editorial fields only with current official-page evidence."""
 if catalog.field(issue,'Discovery campaign')!='classscout-nyc-v1':return {}
 initialize(database)
 with database() as db:
  previous=db.execute('SELECT checked_at,result_json FROM commissioning_checks WHERE entity_id=?',(row['id'],)).fetchone()
  facts=[dict(r) for r in db.execute('SELECT f.field,f.value,f.quote,s.url FROM facts f JOIN sources s ON s.id=f.source_id WHERE entity_id=?',(row['id'],))]
 input_hash=publishing.sha({'policy':'verified-existing-branch-v4','facts':facts,'updated_at':row.get('updated_at'),'hints':issue.get('description')})
 if previous and time.time()-previous['checked_at']<3600 and json.loads(previous['result_json']).get('input_hash')==input_hash:
  return json.loads(previous['result_json']).get('brief',{})
 page=web.page(row['source_url']);source_pages={row['source_url']:page}
 for f in facts:
  if f['url'] not in source_pages and len(source_pages)<4 and urllib.parse.urlsplit(f['url']).hostname.removeprefix('www.')==urllib.parse.urlsplit(row['source_url']).hostname.removeprefix('www.'):source_pages[f['url']]=web.page(f['url'])
 combined='\n'.join(p['text'] for p in source_pages.values());values={}
 for key in ['name','address']:
  candidates={f['value'] for f in facts if f['field']==key and publishing.norm(f['value']) in publishing.norm(f['quote']) and publishing.norm(f['quote']) in publishing.norm(source_pages.get(f['url'],{}).get('text',''))}
  if len(candidates)==1:values[key]=next(iter(candidates))
 if set(values)=={'name','address'}:
  import evidence
  catalog.initialize(database)
  with database() as db:known=[json.loads(r[0])['provider'] for r in db.execute('SELECT result_json FROM catalog_checks') if 'provider' in json.loads(r[0])]
  matches=[p for p in known if not p.get('owner_managed') and publishing.norm(p.get('name'))==publishing.norm(values['name']) and evidence.host(p.get('website',''))==evidence.host(row['source_url']) and evidence.address_matches(p.get('address'),values['address'])]
  if len(matches)==1:return {'Catalog provider':matches[0]['id']}
 borough=catalog.field(issue,'Discovery borough');activity=catalog.field(issue,'Discovery activity');kind=catalog.field(issue,'Discovery format','Classes');brief={};reason='Identity, location or activity needs stronger official-page evidence.'
 if set(values)=={'name','address'} and borough in BOROUGHS and activity in ACTIVITIES and all(present(x,combined) for x in [borough,activity]) and kind in {'Classes','Camps'} and re.search(r'\b'+('camps?' if kind=='Camps' else 'classes?')+r'\b',combined,re.I):
  neighborhoods=[n for n in locations().get(borough,[]) if present(n,combined)]
  # Multiple locations on a provider page need a more focused page; never pick the first.
  if len(neighborhoods)==1:
   brief={'Publication name':values['name'],'Borough':borough,'Neighborhood':neighborhoods[0],'Format':kind,'Activity':activity};reason=None
 result={'input_hash':input_hash,'brief':brief,'reason':reason,'source_url':page['url'],'source_sha256':page['sha256']}
 with database() as db:db.execute('INSERT INTO commissioning_checks VALUES(?,?,?) ON CONFLICT(entity_id) DO UPDATE SET checked_at=excluded.checked_at,result_json=excluded.result_json',(row['id'],time.time(),json.dumps(result)))
 return brief
